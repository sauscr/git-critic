"""Бэкенды: system + user промпт → сырой JSON по RESPONSE_SCHEMA.

openai — Chat Completions по API-ключу;
codex  — `codex exec` под входом ChatGPT;
claude — `claude -p` под входом Claude Code.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from gcritic_core.errors import CriticError
from gcritic_core.settings import Settings

from gcritic_critic.config import CLI_PREAMBLE, MAX_RETRIES, RESPONSE_SCHEMA, SCHEMA_NAME

ERROR_TAIL_CHARS = 600


class Backend(Protocol):
    name: str
    hint: str

    def available(self) -> bool: ...

    def complete(self, system: str, user: str) -> str: ...


# ─── openai ───────────────────────────────────────────────────────────────────


class OpenAIBackend:
    name = "openai"
    hint = "API-ключ OPENAI_API_KEY в ~/.gcritic/.env"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def available(self) -> bool:
        return bool(self._settings.openai_api_key)

    def complete(self, system: str, user: str) -> str:
        # Импорт здесь: openai грузится ~1 с, а нужен только на /review.
        import openai

        settings = self._settings
        client = openai.OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.request_timeout_sec,
            max_retries=MAX_RETRIES,
        )
        try:
            completion = client.chat.completions.create(
                model=settings.model,
                temperature=settings.temperature,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": SCHEMA_NAME, "strict": True, "schema": RESPONSE_SCHEMA},
                },
            )
        except openai.AuthenticationError as exc:
            raise CriticError("OpenAI отверг ключ: проверь OPENAI_API_KEY.") from exc
        except openai.RateLimitError as exc:
            raise CriticError("Лимит запросов OpenAI или закончился баланс.") from exc
        except openai.APITimeoutError as exc:
            raise CriticError(f"OpenAI не ответил за {settings.request_timeout_sec} с.") from exc
        except openai.APIConnectionError as exc:
            raise CriticError("Нет связи с OpenAI: проверь интернет, прокси или VPN.") from exc
        except openai.APIStatusError as exc:
            raise CriticError(f"OpenAI вернул ошибку {exc.status_code}: {exc.message}") from exc

        choice = completion.choices[0]
        if choice.message.refusal:
            raise CriticError(f"Модель отказалась отвечать: {choice.message.refusal}")
        if choice.finish_reason == "length" or not choice.message.content:
            raise CriticError("Ответ модели оборвался. Уменьши GCRITIC_MAX_CHARS и повтори.")
        return choice.message.content


# ─── CLI-бэкенды ──────────────────────────────────────────────────────────────


def _tail(text: str) -> str:
    text = text.strip()
    return text[-ERROR_TAIL_CHARS:] if text else "(пусто)"


def _run_cli(
    name: str, args: list[str], stdin: str, cwd: Path, timeout: int
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CriticError(f"{name} не ответил за {timeout} с (GCRITIC_CLI_TIMEOUT).") from exc
    except OSError as exc:
        raise CriticError(f"Не удалось запустить {name}: {exc}") from exc


class CodexBackend:
    name = "codex"
    hint = "вход ChatGPT: `codex login`"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def available(self) -> bool:
        return shutil.which("codex") is not None

    def complete(self, system: str, user: str) -> str:
        exe = shutil.which("codex")
        if exe is None:
            raise CriticError(f"codex не найден в PATH. {self.hint}")
        # Пустая временная папка: агенту нечего читать, всё нужное — в промпте.
        with tempfile.TemporaryDirectory(prefix="gcritic-") as tmp:
            workdir = Path(tmp)
            schema_file = workdir / "schema.json"
            out_file = workdir / "answer.json"
            schema_file.write_text(json.dumps(RESPONSE_SCHEMA, ensure_ascii=False), "utf-8")
            args = [exe, "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only"]
            args += ["--output-schema", str(schema_file), "-o", str(out_file)]
            if self._settings.codex_model:
                args += ["-m", self._settings.codex_model]
            args.append("-")  # промпт из stdin
            prompt = f"{CLI_PREAMBLE}\n\n{system}\n\n{user}"
            result = _run_cli("codex", args, prompt, workdir, self._settings.cli_timeout_sec)
            answer = out_file.read_text("utf-8").strip() if out_file.is_file() else ""
        if result.returncode != 0 or not answer:
            output = result.stderr + result.stdout
            if "login" in output.lower() or "auth" in output.lower():
                raise CriticError(f"codex не авторизован. Выполни `codex login`.\n{_tail(output)}")
            raise CriticError(f"codex упал (код {result.returncode}):\n{_tail(output)}")
        return answer


class ClaudeBackend:
    name = "claude"
    hint = "вход Claude: `claude`, затем /login"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def available(self) -> bool:
        return shutil.which("claude") is not None

    def complete(self, system: str, user: str) -> str:
        exe = shutil.which("claude")
        if exe is None:
            raise CriticError(f"claude не найден в PATH. {self.hint}")
        with tempfile.TemporaryDirectory(prefix="gcritic-") as tmp:
            workdir = Path(tmp)
            system_file = workdir / "system.txt"
            system_file.write_text(f"{CLI_PREAMBLE}\n\n{system}", "utf-8")
            args = [exe, "-p", "--output-format", "json", "--no-session-persistence"]
            args += ["--json-schema", json.dumps(RESPONSE_SCHEMA, ensure_ascii=False)]
            args += ["--system-prompt-file", str(system_file), "--tools", ""]
            args += ["--setting-sources", "", "--model", self._settings.claude_model]
            result = _run_cli("claude", args, user, workdir, self._settings.cli_timeout_sec)
        return parse_claude_output(result.stdout, result.stderr, result.returncode)


def parse_claude_output(stdout: str, stderr: str, returncode: int) -> str:
    """`claude -p --output-format json` → JSON ответа по схеме."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise CriticError(f"claude упал (код {returncode}):\n{_tail(stderr + stdout)}") from exc
    if data.get("is_error") or returncode != 0:
        message = str(data.get("result") or stderr)
        if "login" in message.lower() or "auth" in message.lower():
            raise CriticError(f"claude не авторизован. Войди командой `claude`.\n{_tail(message)}")
        raise CriticError(f"claude вернул ошибку:\n{_tail(message)}")
    structured = data.get("structured_output")
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False)
    return str(data.get("result", ""))
