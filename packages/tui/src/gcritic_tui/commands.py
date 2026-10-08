"""Реестр команд: одна таблица → /help, автодополнение, хоткеи, диспетчер."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from gcritic_core.contracts import CriticService, GitService, StatsService
from gcritic_core.errors import CriticError
from gcritic_core.settings import Settings
from rich.console import Console
from rich.text import Text

from gcritic_tui import intro, logo, render
from gcritic_tui.theme import CYAN


class ExitShell(Exception):
    """Выход из оболочки."""


@dataclass
class Session:
    """Изменяемое состояние оболочки: текущий репозиторий и кэш для нижней строки."""

    repo: Path | None
    branch: str = ""
    changed_paths: list[str] = field(default_factory=list)
    logo_font: str = logo.DEFAULT_FONT


@dataclass(frozen=True)
class Context:
    settings: Settings
    git: GitService
    critic: CriticService
    stats: StatsService
    console: Console
    session: Session
    version: str


Handler = Callable[[Context, str], None]


@dataclass(frozen=True)
class Command:
    name: str
    args: str
    description: str
    hotkey: str
    handler: Handler

    @property
    def usage(self) -> str:
        return f"/{self.name} {self.args}".rstrip()


# ─── Чистые функции ───────────────────────────────────────────────────────────


def parse_line(line: str) -> tuple[str, str]:
    """«/diff  a.py» → ("diff", "a.py"). Слэш необязателен."""
    text = line.strip().removeprefix("/")
    name, _, args = text.partition(" ")
    return name.lower(), args.strip()


def parse_count(args: str, default: int) -> int:
    if not args:
        return default
    try:
        value = int(args)
    except ValueError as exc:
        raise CriticError(f"Нужно число, а не {args!r}.") from exc
    if value < 1:
        raise CriticError("Число должно быть больше нуля.")
    return value


def parse_diff_args(args: str) -> tuple[bool, str | None]:
    """«--staged path» → (True, "path"). Путь может содержать пробелы."""
    tokens = args.split()
    staged = "--staged" in tokens or "--cached" in tokens
    rest = " ".join(t for t in tokens if t not in {"--staged", "--cached"})
    return staged, rest or None


def find_command(name: str) -> Command | None:
    return next((cmd for cmd in COMMANDS if cmd.name == name), None)


def help_rows() -> list[tuple[str, str, str]]:
    return [(cmd.usage, cmd.hotkey, cmd.description) for cmd in COMMANDS]


# ─── Края: состояние ──────────────────────────────────────────────────────────


def require_repo(ctx: Context) -> Path:
    if ctx.session.repo is None:
        raise CriticError("Репозиторий не выбран. Укажи его: /repo <путь>")
    return ctx.session.repo


def refresh(ctx: Context) -> None:
    """Обновить ветку и список изменений для нижней строки и автодополнения."""
    session = ctx.session
    if session.repo is None:
        session.branch, session.changed_paths = "", []
        return
    try:
        session.branch = ctx.git.current_branch(session.repo)
        session.changed_paths = [change.path for change in ctx.git.status(session.repo)]
    except CriticError:
        session.branch, session.changed_paths = "?", []


# Рамка и поля панели шапки занимают столько колонок.
HEADER_CHROME = 8


def current_logo(ctx: Context, chrome: int = HEADER_CHROME) -> tuple[str, ...]:
    return logo.render_logo(ctx.session.logo_font, ctx.console.width - chrome)


def show_header(ctx: Context) -> None:
    session = ctx.session
    header = render.header(session.repo, session.branch, ctx.version, current_logo(ctx))
    ctx.console.print(header)


# ─── Обработчики ──────────────────────────────────────────────────────────────


def cmd_help(ctx: Context, _args: str) -> None:
    ctx.console.print(render.help_table(help_rows()))


def cmd_review(ctx: Context, _args: str) -> None:
    repo = require_repo(ctx)
    if not ctx.critic.backend:
        ctx.console.print(render.backends_table(ctx.critic.backends(), ""))
        raise CriticError("Критик не подключён: нужен API-ключ или вход в codex / claude.")
    working_diff = ctx.git.diff_head(repo)
    commits = ctx.settings.review_commits
    patches = "" if working_diff.strip() else ctx.git.log_patches(repo, commits)
    sample = ctx.critic.build_sample(working_diff, patches, commits)
    ctx.console.print(render.review_source(repo, sample))
    who = ctx.critic.backend or "критик"
    spinner = Text(f"{who} качает билд и спускается в баг-подвал...", style=CYAN)
    with ctx.console.status(spinner, spinner="dots"):
        result = ctx.critic.review(sample)
    ctx.console.print(render.review(result))


def cmd_backend(ctx: Context, args: str) -> None:
    if args:
        ctx.critic.use(args)
    ctx.console.print(render.backends_table(ctx.critic.backends(), ctx.critic.backend))


def cmd_stats(ctx: Context, _args: str) -> None:
    repo = require_repo(ctx)
    today = date.today()
    since = today - timedelta(days=ctx.stats.days - 1)
    days = ctx.stats.activity(ctx.git.commit_dates(repo, since), today)
    ctx.console.print(render.activity(days, today))


def cmd_status(ctx: Context, _args: str) -> None:
    repo = require_repo(ctx)
    ctx.console.print(render.status_table(ctx.git.status(repo), ctx.git.current_branch(repo)))


def cmd_diff(ctx: Context, args: str) -> None:
    repo = require_repo(ctx)
    staged, path = parse_diff_args(args)
    text = ctx.git.diff(repo, staged=staged, path=path)
    scope = "ИНДЕКС" if staged else "РАБОЧАЯ КОПИЯ"
    title = f"ДИФФ · {scope}" + (f" · {path}" if path else "")
    ctx.console.print(render.diff_view(text, title))
    untracked = {c.path for c in ctx.git.status(repo) if c.index == "?"}
    if not staged and path in untracked:
        ctx.console.print(render.note("Файл не отслеживается git — в диффе его нет до stage."))


def cmd_log(ctx: Context, args: str) -> None:
    repo = require_repo(ctx)
    ctx.console.print(
        render.log_table(ctx.git.log(repo, parse_count(args, ctx.settings.log_count)))
    )


def cmd_branches(ctx: Context, _args: str) -> None:
    ctx.console.print(render.branches_table(ctx.git.branches(require_repo(ctx))))


def cmd_repo(ctx: Context, args: str) -> None:
    session = ctx.session
    if not args:
        where = str(session.repo) if session.repo else "не выбран"
        ctx.console.print(render.note(f"Текущий репозиторий: {where}"))
        return
    base = session.repo or Path.cwd()
    target = (base / Path(args.strip("\"'")).expanduser()).resolve()
    session.repo = ctx.git.ensure_repository(target)
    refresh(ctx)
    ctx.console.print(
        Text.assemble(("▶ ", CYAN), (f"{session.repo}  ·  {session.branch}", "white"))
    )


def cmd_logo(ctx: Context, args: str) -> None:
    if args:
        if not logo.font_exists(args):
            raise CriticError(f"Шрифта {args!r} нет. Варианты: {', '.join(logo.FONTS)}")
        ctx.session.logo_font = args
        show_header(ctx)
        ctx.console.print(render.note(f"Закрепить навсегда: GCRITIC_LOGO_FONT={args} в .env"))
        return
    width = ctx.console.width - HEADER_CHROME
    for font in logo.FONTS:
        mark = "●" if font == ctx.session.logo_font else " "
        ctx.console.print(Text(f"{mark} /logo {font}", style=CYAN))
        ctx.console.print(render.logo_text(logo.render_logo(font, width)))
        ctx.console.print()


def cmd_intro(ctx: Context, _args: str) -> None:
    if not ctx.console.is_terminal:
        raise CriticError("Заставка показывается только в терминале.")
    intro.play(ctx.console, current_logo(ctx, chrome=2), ctx.settings.intro_sec)


def cmd_clear(ctx: Context, _args: str) -> None:
    ctx.console.clear()
    show_header(ctx)


def cmd_exit(_ctx: Context, _args: str) -> None:
    raise ExitShell


COMMANDS: tuple[Command, ...] = (
    Command("help", "", "список команд и хоткеев", "?", cmd_help),
    Command("review", "", "ИИ-обзор изменений (или последних коммитов)", "^R", cmd_review),
    Command("backend", "[auto|имя]", "кто пишет обзор: openai / codex / claude", "", cmd_backend),
    Command("stats", "", "активность коммитов по дням", "", cmd_stats),
    Command("status", "", "изменённые файлы: индекс и рабочая копия", "", cmd_status),
    Command("diff", "[--staged] [файл]", "дифф рабочей копии или индекса", "", cmd_diff),
    Command("log", "[n]", "последние коммиты", "", cmd_log),
    Command("branches", "", "локальные ветки и отставание от upstream", "", cmd_branches),
    Command("repo", "[путь]", "сменить репозиторий", "", cmd_repo),
    Command("logo", "[шрифт]", "примерить шрифт логотипа", "", cmd_logo),
    Command("intro", "", "показать демо-заставку", "", cmd_intro),
    Command("clear", "", "очистить экран", "^L", cmd_clear),
    Command("exit", "", "выйти", "^D", cmd_exit),
)


def dispatch(ctx: Context, line: str) -> None:
    """Выполнить строку ввода. Ошибки CriticError печатаются, ExitShell пробрасывается."""
    name, args = parse_line(line)
    if not name:
        return
    command = find_command(name)
    try:
        if command is None:
            raise CriticError(f"Неизвестная команда /{name}. Список: /help")
        command.handler(ctx, args)
    except CriticError as exc:
        ctx.console.print(render.error(str(exc)))
    except KeyboardInterrupt:
        ctx.console.print(render.error("Прервано игроком. Прогресс не сохранён."))
    finally:
        refresh(ctx)
