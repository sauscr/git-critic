from datetime import date
from pathlib import Path

import pytest
from conftest import git
from gcritic_core import CriticError, Settings
from gcritic_core.types import METRIC_NAMES, BackendInfo, CodeSample, DayCount, Review
from gcritic_critic.logic import build_sample
from gcritic_git import GitCli
from gcritic_stats import Stats
from gcritic_tui import Context, Session, intro, logo, render
from gcritic_tui.app import CommandCompleter
from gcritic_tui.commands import (
    COMMANDS,
    ExitShell,
    dispatch,
    help_rows,
    parse_count,
    parse_diff_args,
    parse_line,
)
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from rich.console import Console

REVIEW = Review("ПОХВАЛЬНО", "Крепкий билд с подколкой.", dict.fromkeys(METRIC_NAMES, 7))


class FakeCritic:
    def __init__(self, available: bool = True) -> None:
        self.backend = "codex" if available else ""
        self.samples: list[CodeSample] = []

    def backends(self) -> list[BackendInfo]:
        return [
            BackendInfo("openai", False, "ключ"),
            BackendInfo("codex", bool(self.backend), "вход"),
        ]

    def use(self, name: str) -> None:
        if name not in {"auto", "codex"}:
            raise CriticError(f"Бэкенд {name} недоступен.")
        self.backend = "codex"

    def build_sample(self, working_diff: str, recent_patches: str, commits: int) -> CodeSample:
        return build_sample(working_diff, recent_patches, commits, 60_000)

    def review(self, sample: CodeSample) -> Review:
        self.samples.append(sample)
        return REVIEW


def make_ctx(repo: Path | None, critic: FakeCritic | None = None) -> Context:
    return Context(
        settings=Settings(history_file=Path("unused")),
        git=GitCli(),
        critic=critic or FakeCritic(),
        stats=Stats(7),
        console=Console(record=True, width=120, color_system=None),
        session=Session(repo=repo),
        version="0.1.0",
    )


def output(ctx: Context) -> str:
    return ctx.console.export_text(clear=False)


# ─── Разбор ввода ─────────────────────────────────────────────────────────────


def test_parsers():
    assert parse_line("  /Diff   a b.py ") == ("diff", "a b.py")
    assert parse_line("log 3") == ("log", "3")
    assert parse_count("", 20) == 20 and parse_count("3", 20) == 3
    with pytest.raises(CriticError):
        parse_count("x", 1)
    with pytest.raises(CriticError):
        parse_count("0", 1)
    assert parse_diff_args("--staged my file.py") == (True, "my file.py")
    assert parse_diff_args("") == (False, None)


def test_registry_is_consistent():
    names = [cmd.name for cmd in COMMANDS]
    assert len(names) == len(set(names))
    expected = {
        "help",
        "review",
        "stats",
        "status",
        "diff",
        "log",
        "branches",
        "repo",
        "clear",
        "exit",
    }
    assert expected <= set(names)
    assert len(help_rows()) == len(COMMANDS)


# ─── Команды на живом репозитории ─────────────────────────────────────────────


def test_status_diff_log_branches(repo: Path):
    (repo / "app.py").write_text("print('bye')\n", encoding="utf-8")
    ctx = make_ctx(repo)
    for line in ("/status", "/diff", "/diff --staged", "/log 1", "/branches"):
        dispatch(ctx, line)
    text = output(ctx)
    assert "СТАТУС · main" in text and "изменён" in text
    assert "bye" in text
    assert "ДИФФ · ИНДЕКС: изменений нет" in text
    assert "feat: библиотека" in text and "первый коммит" not in text
    assert "ВЕТКИ · 1" in text
    assert ctx.session.changed_paths == ["app.py"]


def test_review_uses_working_diff_then_commits(repo: Path):
    critic = FakeCritic()
    ctx = make_ctx(repo, critic)
    dispatch(ctx, "/review")
    assert critic.samples[-1].source.startswith("git log -n 5")
    (repo / "app.py").write_text("print('bye')\n", encoding="utf-8")
    dispatch(ctx, "review")
    assert critic.samples[-1].source.startswith("git diff HEAD")
    text = output(ctx)
    assert "П О Х В А Л Ь Н О" in text and "Крепкий билд" in text and "МЕТРИКИ" in text


def test_review_without_key(repo: Path):
    ctx = make_ctx(repo, FakeCritic(available=False))
    dispatch(ctx, "/review")
    assert "GAME OVER" in output(ctx) and "Критик не подключён" in output(ctx)
    assert "КРИТИК" in output(ctx)


def test_backend_command(repo: Path):
    ctx = make_ctx(repo)
    dispatch(ctx, "/backend")
    dispatch(ctx, "/backend openai")
    text = output(ctx)
    assert "КРИТИК" in text and "готов" in text and "Бэкенд openai недоступен" in text


def test_stats(repo: Path):
    ctx = make_ctx(repo)
    dispatch(ctx, "/stats")
    assert "АКТИВНОСТЬ · 7 ДН." in output(ctx)
    assert "Всего коммитов за 7 дн.: 2" in output(ctx)


def test_repo_switch_and_errors(repo: Path, tmp_path: Path):
    ctx = make_ctx(None)
    dispatch(ctx, "/status")
    assert "Репозиторий не выбран" in output(ctx)
    dispatch(ctx, f'/repo "{repo}"')
    assert ctx.session.repo == repo.resolve() and ctx.session.branch == "main"
    dispatch(ctx, f"/repo {tmp_path}")
    assert "не Git-репозиторий" in output(ctx)
    assert ctx.session.repo == repo.resolve()
    dispatch(ctx, "/nope")
    assert "Неизвестная команда /nope" in output(ctx)
    dispatch(ctx, "/help")
    assert "/diff [--staged] [файл]" in output(ctx)


def test_exit_and_clear(repo: Path):
    ctx = make_ctx(repo)
    dispatch(ctx, "/clear")
    assert "Git-клиент с обзорами" in output(ctx)
    with pytest.raises(ExitShell):
        dispatch(ctx, "/exit")


def test_untracked_diff_note(repo: Path):
    (repo / "new.py").write_text("n\n", encoding="utf-8")
    git(repo, "status")
    ctx = make_ctx(repo)
    dispatch(ctx, "/diff new.py")
    assert "не отслеживается" in output(ctx)


# ─── Автодополнение и нижняя строка ───────────────────────────────────────────


def complete(ctx: Context, text: str) -> list[str]:
    completer = CommandCompleter(ctx)
    return [c.text for c in completer.get_completions(Document(text), CompleteEvent())]


def test_completer(repo: Path):
    ctx = make_ctx(repo)
    ctx.session.changed_paths = ["app.py", "lib.py"]
    assert complete(ctx, "/") == [f"/{cmd.name}" for cmd in COMMANDS]
    assert complete(ctx, "/re") == ["/review", "/repo"]
    assert complete(ctx, "/backend c") == ["codex"]
    assert complete(ctx, "/diff a") == ["app.py"]
    assert complete(ctx, "/diff --st") == ["--staged"]
    assert complete(ctx, "hello") == []


def test_toolbar():
    assert "нет репозитория" in "".join(t for _, t in render.toolbar(None, "", 0))
    text = "".join(t for _, t in render.toolbar(Path("/x/proj"), "dev", 3))
    assert "proj" in text and "dev" in text and "3 изм." in text and "^R" in text
    assert "критик не подключён" in text
    assert "codex" in "".join(t for _, t in render.toolbar(None, "", 0, "codex"))
    assert "чисто" in "".join(t for _, t in render.toolbar(Path("/x/proj"), "dev", 0))


def test_activity_render_empty_week():
    today = date(2026, 10, 8)
    days = [DayCount(date(2026, 10, d), 0) for d in range(2, 9)]
    console = Console(record=True, width=100, color_system=None)
    console.print(render.activity(days, today))
    text = console.export_text()
    assert "AFK" in text and "Чт" in text


def test_metric_style():
    assert render.metric_style("Чистота кода", 9) != render.metric_style("Чистота кода", 2)
    assert render.metric_style("Уровень костылей", 2) == render.metric_style("Чистота кода", 9)


# ─── Логотип и заставка ───────────────────────────────────────────────────────


def test_every_font_renders():
    for font in logo.FONTS:
        assert logo.font_exists(font)
        lines = logo.render_logo(font, 200)
        assert lines and logo.width_of(list(lines)) <= 200


def test_logo_stacks_then_falls_back():
    wide = logo.render_logo("larry3d", 200)
    stacked = logo.render_logo("larry3d", 60)
    assert len(stacked) > len(wide) and logo.width_of(list(stacked)) <= 60
    assert logo.render_logo("larry3d", 10) == ()
    assert logo.render_logo("нет-такого", 200) == wide


def test_logo_command(repo: Path):
    ctx = make_ctx(repo)
    dispatch(ctx, "/logo")
    assert all(f"/logo {font}" in output(ctx) for font in logo.FONTS)
    dispatch(ctx, "/logo bloody")
    assert ctx.session.logo_font == "bloody" and "GCRITIC_LOGO_FONT=bloody" in output(ctx)
    dispatch(ctx, "/logo comic-sans")
    assert "Шрифта 'comic-sans' нет" in output(ctx)


def test_intro_command_needs_terminal(repo: Path):
    ctx = make_ctx(repo)
    dispatch(ctx, "/intro")
    assert "только в терминале" in output(ctx)


def test_frame_has_exact_size_and_is_deterministic():
    scene = intro.Scene(80, 24, logo.render_logo("larry3d", 78), intro.make_stars())
    for t in (0.0, 0.5, 1.3, 3.9):
        text = intro.frame(scene, t, 0.5, "чтение git...")
        lines = text.plain.split("\n")
        assert len(lines) == 24 and all(len(line) == 80 for line in lines)
        assert intro.frame(scene, t, 0.5, "x").plain == intro.frame(scene, t, 0.5, "x").plain
    late = intro.frame(scene, 3.0, 1.0, "готово").plain
    assert "100%" in late and "StopGame" in late


def test_tiny_terminal_does_not_crash():
    scene = intro.Scene(10, 5, (), intro.make_stars())
    assert len(intro.frame(scene, 1.0, 0.2, "s").plain.split("\n")) == 5


def test_helpers():
    assert intro.progress_bar(0.5, "s", 10).startswith("[█████░░░░░]  50%")
    assert intro.logo_top(0.0, 30, 7) == -7
    assert intro.logo_top(10.0, 30, 7) == (30 - 7) // 2 - 3
    assert intro.rainbow(0.0).startswith("#") and len(intro.rainbow(0.3)) == 7
    assert intro.shade("#808080", 2.0) == "#ffffff"
