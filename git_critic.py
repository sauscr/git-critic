#!/usr/bin/env python3
"""git_critic — обзор Git-изменений в стиле StopGame.ru прямо в терминале.

Установка:
    pip install -r requirements.txt          # или: pip install "openai>=1.40" "rich>=13.7"

Запуск (PowerShell):
    $env:OPENAI_API_KEY = "sk-..."
    python git_critic.py [путь_к_репозиторию]

Запуск (bash / Git Bash):
    OPENAI_API_KEY="sk-..." python git_critic.py [путь_к_репозиторию]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

try:
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        OpenAI,
        RateLimitError,
    )
    from rich import box
    from rich.align import Align
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError as import_error:
    sys.exit(
        f"Не хватает зависимости '{import_error.name}'.\n"
        'Установи: pip install "openai>=1.40" "rich>=13.7"'
    )


# ─── Настройки ────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MAX_CHARS = 60_000  # ~15k токенов: дёшево для gpt-4o-mini и влезает в контекст
REQUEST_TIMEOUT_SEC = 90
LOG_COMMITS = 5
WEEK_DAYS = 7
CHART_HEIGHT = 8
CHART_COL_WIDTH = 5
METRIC_SEGMENTS = 10

VERDICTS = ("ИЗУМИТЕЛЬНО", "ПОХВАЛЬНО", "ПРОХОДНЯК", "МУСОР")
METRIC_NAMES = ("Чистота кода", "Архитектура", "Уровень костылей")
INVERTED_METRICS = frozenset({"Уровень костылей"})  # для них больше = хуже
WEEKDAY_NAMES = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

# ─── Палитра Pure Black: чёрный фон, неон только на акцентах ─────────────────

BG = "on #000000"
BASE = f"#d0d0d0 {BG}"
DIM = f"#4a4a4a {BG}"
CYAN = "bold bright_cyan"
GREEN = "bold bright_green"
YELLOW = "bold bright_yellow"
RED = "bold bright_red"

VERDICT_STYLES = {
    "ИЗУМИТЕЛЬНО": GREEN,
    "ПОХВАЛЬНО": CYAN,
    "ПРОХОДНЯК": YELLOW,
    "МУСОР": RED,
}
VERDICT_TAGLINES = {
    "ИЗУМИТЕЛЬНО": "Золотой фонд. Показывать джунам по праздникам.",
    "ПОХВАЛЬНО": "Крепкий середнячок с претензией на GOTY.",
    "ПРОХОДНЯК": "Пройти можно. Перепроходить — нет.",
    "МУСОР": "Рефанд оформлен. Билд отправлен в баг-подвал.",
}

LOGO = (
    " ██████╗ ██╗████████╗    ██████╗██████╗ ██╗████████╗██╗ ██████╗",
    "██╔════╝ ██║╚══██╔══╝   ██╔════╝██╔══██╗██║╚══██╔══╝██║██╔════╝",
    "██║  ███╗██║   ██║      ██║     ██████╔╝██║   ██║   ██║██║",
    "██║   ██║██║   ██║      ██║     ██╔══██╗██║   ██║   ██║██║",
    "╚██████╔╝██║   ██║      ╚██████╗██║  ██║██║   ██║   ██║╚██████╗",
    " ╚═════╝ ╚═╝   ╚═╝       ╚═════╝╚═╝  ╚═╝╚═╝   ╚═╝   ╚═╝ ╚═════╝",
)

# ─── Промпт и схема ответа ────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Ты — ведущий обозреватель StopGame.ru, но вместо игр рецензируешь код из Git-репозитория. \
Пользователь присылает diff или патчи последних коммитов — это «билд», который тебе выдали на обзор.

ГОЛОС И МАНЕРА
- Пиши как автор видеообзоров StopGame: иронично, харизматично, слегка токсично, но остроумно и по делу.
- Сарказм направлен на код и решения, а не на личность автора. Без мата и оскорблений.
- Геймерский сленг вплетай естественно, а не списком: «костыли», «баг-подвал», «графон», «геймплей кода», \
«оптимизация», «патч первого дня», «ранний доступ», «рескин», «гринд», «софтлок», «пасхалка», «DLC», «кранч».
- Проводи параллели с геймдевом: недоделанный релиз, «починим патчами», рескин прошлогодней части, кранч перед дедлайном.
- Обязательно опирайся на конкретику из присланного кода: имена файлов, функций, переменных, конкретные решения. \
Фразы, применимые к любому коду, запрещены.
- Если есть сильные стороны — отметь их; похвала в стиле StopGame звучит сдержанно и с подколкой.

ПОЛЕ "review"
- Русский язык, от 2 до 4 предложений. Без markdown, списков и эмодзи.
- Первое предложение — заход в духе вступления видеообзора.
- Последнее предложение — хлёсткий итог-панчлайн.

ПОЛЕ "verdict" — шкала StopGame, строго одно значение:
- "ИЗУМИТЕЛЬНО" — чистый, продуманный код без явных проблем. Ставится редко.
- "ПОХВАЛЬНО" — добротно, мелкие шероховатости.
- "ПРОХОДНЯК" — работает, но держится на изоленте: костыли, дублирование, сомнительные решения.
- "МУСОР" — баги, дыры безопасности, секреты в коде, хаос, закомментированные трупы кода.

ПОЛЕ "metrics" — целые числа от 1 до 10:
- "Чистота кода": 10 — стерильно, 1 — свалка.
- "Архитектура": 10 — продуманные слои и границы, 1 — спагетти.
- "Уровень костылей": 10 — всё на костылях, 1 — костылей нет. ЧЕМ ВЫШЕ, ТЕМ ХУЖЕ.
Вердикт и метрики должны быть согласованы: у "ИЗУМИТЕЛЬНО" не бывает 8 по костылям, у "МУСОР" — 9 за чистоту.

ОСОБЫЕ СЛУЧАИ
- Если код обрезан — оценивай видимую часть и не выдумывай то, чего не видно.
- Если изменения только в конфигах, документации или ассетах — оцени с иронией \
(«патч, меняющий только README, — это DLC с новыми скинами»).

Отвечай только JSON по заданной схеме."""

SCORE_SCHEMA = {"type": "integer", "enum": list(range(1, 11))}
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "review": {"type": "string"},
        "metrics": {
            "type": "object",
            "properties": {name: SCORE_SCHEMA for name in METRIC_NAMES},
            "required": list(METRIC_NAMES),
            "additionalProperties": False,
        },
    },
    "required": ["verdict", "review", "metrics"],
    "additionalProperties": False,
}


class CriticError(Exception):
    """Ошибка, которую показываем пользователю как есть, без трейсбека."""


@dataclass(frozen=True)
class CodeSample:
    source: str
    text: str
    truncated: bool


@dataclass(frozen=True)
class Review:
    verdict: str
    review: str
    metrics: dict[str, int]


# ─── Git ──────────────────────────────────────────────────────────────────────


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as exc:
        raise CriticError(
            "Git не найден в PATH. Установи его: https://git-scm.com/downloads"
        ) from exc


def run_git(repo: Path, *args: str) -> str:
    result = _git(repo, *args)
    if result.returncode != 0:
        details = result.stderr.strip() or f"код выхода {result.returncode}"
        raise CriticError(f"git {' '.join(args)} упал: {details}")
    return result.stdout


def ensure_repository(repo: Path) -> None:
    if not repo.is_dir():
        raise CriticError(f"Папка не найдена: {repo}")
    if _git(repo, "rev-parse", "--is-inside-work-tree").returncode != 0:
        raise CriticError(f"Это не Git-репозиторий: {repo}")
    if _git(repo, "rev-parse", "--verify", "--quiet", "HEAD").returncode != 0:
        raise CriticError(
            "Репозиторий пуст: нет ни одного коммита. Сделай первый commit — и приходи на обзор."
        )


def truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n\n[... дальше обрезано по лимиту размера ...]", True


def collect_code(repo: Path, max_chars: int) -> CodeSample:
    diff = run_git(repo, "diff", "HEAD", "--no-color")
    if diff.strip():
        source = "git diff HEAD · незакоммиченные изменения"
        raw = diff
    else:
        raw = run_git(repo, "log", "-n", str(LOG_COMMITS), "-p", "--no-color")
        source = f"git log -n {LOG_COMMITS} -p · последние коммиты"
        if not raw.strip():
            raise CriticError("Нечего анализировать: ни изменений, ни коммитов с патчами.")
    text, truncated = truncate(raw, max_chars)
    return CodeSample(source=source, text=text, truncated=truncated)


def collect_weekly_activity(repo: Path) -> list[tuple[date, int]]:
    """Коммиты по дням за последние 7 дней (включая сегодня), все ветки."""
    today = date.today()
    start = today - timedelta(days=WEEK_DAYS - 1)
    output = run_git(
        repo,
        "log",
        "--all",
        f"--since={start.isoformat()} 00:00",
        "--pretty=format:%ad",
        "--date=format-local:%Y-%m-%d",
    )
    counts = {start + timedelta(days=offset): 0 for offset in range(WEEK_DAYS)}
    for line in output.splitlines():
        try:
            day = date.fromisoformat(line.strip())
        except ValueError:
            continue
        if day in counts:
            counts[day] += 1
    return list(counts.items())


# ─── OpenAI ───────────────────────────────────────────────────────────────────


def request_review(sample: CodeSample, api_key: str, model: str) -> Review:
    client = OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SEC, max_retries=2)
    truncation_note = "\nВНИМАНИЕ: код обрезан по лимиту размера." if sample.truncated else ""
    user_message = (
        f"Источник: {sample.source}.{truncation_note}\n"
        f"Билд на обзор:\n```diff\n{sample.text}\n```"
    )
    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=0.9,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "stopgame_code_review",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                },
            },
        )
    except AuthenticationError as exc:
        raise CriticError("OpenAI отверг ключ: проверь OPENAI_API_KEY.") from exc
    except RateLimitError as exc:
        raise CriticError("Лимит запросов OpenAI или закончился баланс. Попробуй позже.") from exc
    except APITimeoutError as exc:
        raise CriticError(f"OpenAI не ответил за {REQUEST_TIMEOUT_SEC} с.") from exc
    except APIConnectionError as exc:
        raise CriticError("Нет связи с OpenAI: проверь интернет, прокси или VPN.") from exc
    except APIStatusError as exc:
        raise CriticError(f"OpenAI вернул ошибку {exc.status_code}: {exc.message}") from exc

    choice = completion.choices[0]
    if choice.message.refusal:
        raise CriticError(f"Модель отказалась отвечать: {choice.message.refusal}")
    if choice.finish_reason == "length" or not choice.message.content:
        raise CriticError("Ответ модели оборвался. Уменьши --max-chars и повтори.")
    return parse_review(choice.message.content)


def parse_review(raw: str) -> Review:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CriticError(f"Модель вернула невалидный JSON: {exc}") from exc

    verdict = data.get("verdict")
    if verdict not in VERDICTS:
        raise CriticError(f"Неизвестный вердикт от модели: {verdict!r}")

    review_text = str(data.get("review", "")).strip()
    if not review_text:
        raise CriticError("Модель вернула пустой обзор.")

    raw_metrics = data.get("metrics") or {}
    metrics: dict[str, int] = {}
    for name in METRIC_NAMES:
        value = raw_metrics.get(name)
        if not isinstance(value, int):
            raise CriticError(f"Метрика '{name}' отсутствует или не число: {value!r}")
        metrics[name] = max(1, min(METRIC_SEGMENTS, value))

    return Review(verdict=verdict, review=review_text, metrics=metrics)


# ─── Визуализация ─────────────────────────────────────────────────────────────


def section(body, title: str, accent: str) -> Panel:
    return Panel(
        body,
        title=Text(f" {title} ", style=accent),
        title_align="left",
        border_style=accent,
        box=box.HEAVY,
        style=BASE,
        padding=(1, 2),
    )


def render_header(console: Console, repo: Path, sample: CodeSample) -> None:
    logo_width = max(len(line) for line in LOGO)
    if console.width >= logo_width + 4:
        title = Text("\n".join(LOGO), style=CYAN, no_wrap=True, overflow="crop")
    else:
        title = Text("GIT CRITIC", style=CYAN)

    meta = Text(justify="center")
    meta.append("Обзор кода в стиле StopGame\n", style=YELLOW)
    meta.append(f"{repo.name}", style="bold white")
    meta.append(f"  ·  {sample.source}", style=DIM)
    if sample.truncated:
        meta.append("  ·  обрезано", style=RED)

    console.print(
        Panel(
            Group(Align.center(title), Text(""), meta),
            box=box.DOUBLE,
            border_style=CYAN,
            style=BASE,
            padding=(1, 2),
        )
    )


def render_verdict(verdict: str) -> Align:
    accent = VERDICT_STYLES[verdict]
    stamp = Text(justify="center")
    stamp.append("▓▓▓  В Е Р Д И К Т  ▓▓▓\n\n", style=DIM)
    stamp.append(f"★  {' '.join(verdict)}  ★", style=f"{accent} reverse")
    stamp.append(f"\n\n{VERDICT_TAGLINES[verdict]}", style=accent)

    inner = Panel(stamp, box=box.HEAVY, border_style=accent, style=BASE, padding=(1, 4), expand=False)
    outer = Panel(inner, box=box.DOUBLE, border_style=accent, style=BASE, padding=(0, 1), expand=False)
    return Align.center(outer, style=BG)


def metric_style(name: str, score: int) -> str:
    quality = METRIC_SEGMENTS + 1 - score if name in INVERTED_METRICS else score
    if quality >= 8:
        return GREEN
    if quality >= 5:
        return YELLOW
    return RED


def render_metrics(metrics: dict[str, int]) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="left", no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column(justify="right", no_wrap=True)
    for name in METRIC_NAMES:
        score = metrics[name]
        accent = metric_style(name, score)
        bar = Text()
        bar.append("█▌" * score, style=accent)
        bar.append("░░" * (METRIC_SEGMENTS - score), style=DIM)
        label = Text(name, style="bold white")
        if name in INVERTED_METRICS:
            label.append(" ↓", style=DIM)
        table.add_row(label, bar, Text(f"{score:>2}/{METRIC_SEGMENTS}", style=accent))
    caption = Text("\n↓ — чем меньше, тем лучше", style=DIM)
    return section(Group(table, caption), "МЕТРИКИ", CYAN)


def render_activity(activity: list[tuple[date, int]]) -> Panel:
    counts = [count for _, count in activity]
    peak = max(counts)
    scale = max(peak, 1)
    heights = [0 if count == 0 else max(1, round(count / scale * CHART_HEIGHT)) for count in counts]
    today = date.today()
    axis_width = len(str(scale))

    lines: list[Text] = []
    for level in range(CHART_HEIGHT, 0, -1):
        if level == CHART_HEIGHT:
            label = str(scale)
        elif level == CHART_HEIGHT // 2:
            label = str(round(scale / 2)) if scale > 1 else ""
        else:
            label = ""
        row = Text(f"{label:>{axis_width}} │", style=DIM)
        for (day, _), height in zip(activity, heights):
            cell = "███".center(CHART_COL_WIDTH)
            if height >= level:
                row.append(cell, style=CYAN if day == today else GREEN)
            else:
                row.append(cell.replace("█", "░"), style=DIM)
        lines.append(row)

    lines.append(Text(f"{'0':>{axis_width}} └" + "─" * (CHART_COL_WIDTH * WEEK_DAYS), style=DIM))

    day_row = Text(" " * (axis_width + 2))
    count_row = Text(" " * (axis_width + 2))
    for (day, count) in activity:
        is_today = day == today
        day_row.append(
            WEEKDAY_NAMES[day.weekday()].center(CHART_COL_WIDTH),
            style=CYAN if is_today else "bold white",
        )
        count_row.append(str(count).center(CHART_COL_WIDTH), style=YELLOW if count else DIM)
    lines.extend([day_row, count_row])

    total = sum(counts)
    summary = Text()
    summary.append(f"\nВсего коммитов за неделю: ", style=BASE)
    summary.append(str(total), style=YELLOW)
    if total == 0:
        summary.append("  ·  неделя AFK, сервер пустует", style=DIM)
    return section(Group(*lines, summary), "АКТИВНОСТЬ · 7 ДНЕЙ", GREEN)


def render_review(review_text: str, verdict: str) -> Panel:
    body = Text(review_text, style="white", justify="left")
    return section(body, "ОБЗОР", VERDICT_STYLES[verdict])


def render_error(console: Console, message: str) -> None:
    console.print(
        Panel(
            Text(message, style="white"),
            title=Text(" GAME OVER ", style=f"{RED} reverse"),
            border_style=RED,
            box=box.HEAVY,
            style=BASE,
            padding=(1, 2),
        )
    )


# ─── Точка входа ──────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="git_critic",
        description="Обзор Git-изменений в стиле StopGame.ru через OpenAI.",
    )
    parser.add_argument("repo", nargs="?", default=".", help="путь к репозиторию (по умолчанию текущая папка)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"модель OpenAI (по умолчанию {DEFAULT_MODEL})")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"лимит символов кода для отправки (по умолчанию {DEFAULT_MAX_CHARS})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    console = Console(style=BASE, highlight=False)

    try:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise CriticError(
                "Не задан OPENAI_API_KEY.\n"
                'PowerShell:  $env:OPENAI_API_KEY = "sk-..."\n'
                'bash:        export OPENAI_API_KEY="sk-..."'
            )
        if args.max_chars < 1_000:
            raise CriticError("--max-chars должен быть не меньше 1000.")

        repo = Path(args.repo).resolve()
        ensure_repository(repo)
        sample = collect_code(repo, args.max_chars)
        activity = collect_weekly_activity(repo)

        render_header(console, repo, sample)
        console.print(render_activity(activity))
        with console.status(Text("Критик качает билд и спускается в баг-подвал...", style=CYAN), spinner="dots"):
            review = request_review(sample, api_key, args.model)
    except CriticError as exc:
        render_error(console, str(exc))
        return 1
    except KeyboardInterrupt:
        render_error(console, "Прервано игроком. Прогресс не сохранён.")
        return 130

    console.print(render_verdict(review.verdict))
    console.print(render_review(review.review, review.verdict))
    console.print(render_metrics(review.metrics))
    return 0


if __name__ == "__main__":
    sys.exit(main())
