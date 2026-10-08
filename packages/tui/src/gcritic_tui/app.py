"""REPL на prompt_toolkit: меню /, история, хоткеи, нижняя строка."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable, Iterator

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import CompleteEvent, Completer, Completion, PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import FileHistory, History, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent

from gcritic_tui import intro, render
from gcritic_tui.commands import (
    COMMANDS,
    Context,
    ExitShell,
    current_logo,
    dispatch,
    refresh,
    show_header,
)
from gcritic_tui.logo import FONTS
from gcritic_tui.theme import PROMPT_STYLE

# Хоткей → команда, которую он набирает и выполняет.
HOTKEY_COMMANDS = {"c-r": "/review", "c-l": "/clear"}


class CommandCompleter(Completer):
    """«/» — команды с описаниями; аргументы /diff — изменённые файлы; /repo — папки."""

    def __init__(self, ctx: Context) -> None:
        self._ctx = ctx
        self._paths = PathCompleter(only_directories=True, expanduser=True)

    def get_completions(self, document: Document, event: CompleteEvent) -> Iterable[Completion]:
        text = document.text_before_cursor.lstrip()
        if not text.startswith("/"):
            return
        name, space, arg = text[1:].partition(" ")
        if not space:
            for cmd in COMMANDS:
                if cmd.name.startswith(name.lower()):
                    yield Completion(
                        f"/{cmd.name}",
                        start_position=-len(text),
                        display=cmd.usage,
                        display_meta=cmd.description,
                    )
            return
        if name == "diff":
            word = arg.split(" ")[-1]
            options = ["--staged", *self._ctx.session.changed_paths]
            for option in options:
                if option.startswith(word):
                    yield Completion(option, start_position=-len(word))
        elif name == "backend":
            for option in ["auto", *(b.name for b in self._ctx.critic.backends())]:
                if option.startswith(arg):
                    yield Completion(option, start_position=-len(arg))
        elif name == "logo":
            for option in FONTS:
                if option.startswith(arg):
                    yield Completion(option, start_position=-len(arg))
        elif name == "repo":
            yield from self._paths.get_completions(Document(arg), event)


def _key_bindings() -> KeyBindings:
    bindings = KeyBindings()

    def run(command: str):
        def handler(event: KeyPressEvent) -> None:
            event.current_buffer.text = command
            event.current_buffer.validate_and_handle()

        return handler

    for key, command in HOTKEY_COMMANDS.items():
        bindings.add(key)(run(command))

    @bindings.add("c-d")
    def _exit(event: KeyPressEvent) -> None:
        event.app.exit(exception=EOFError)

    @bindings.add("escape", eager=True)
    def _reset(event: KeyPressEvent) -> None:
        event.current_buffer.reset()

    empty = Condition(lambda: not _current_text())

    @bindings.add("?", filter=empty)
    def _help(event: KeyPressEvent) -> None:
        run("/help")(event)

    return bindings


def _current_text() -> str:
    from prompt_toolkit.application.current import get_app

    return get_app().current_buffer.text


def _history(ctx: Context) -> History:
    path = ctx.settings.history_file
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        return FileHistory(str(path))
    except OSError:
        return InMemoryHistory()


def _prompt(ctx: Context) -> list[tuple[str, str]]:
    session = ctx.session
    if session.repo is None:
        return [("class:prompt.arrow", "❯ ")]
    return [
        ("class:prompt.repo", session.repo.name),
        ("class:prompt.branch", f":{session.branch}"),
        ("class:prompt.arrow", " ❯ "),
    ]


def _read_lines(ctx: Context) -> Iterator[str]:
    """Интерактивный ввод: меню, хоткеи, история, нижняя строка."""
    prompt = PromptSession(
        history=_history(ctx),
        completer=CommandCompleter(ctx),
        complete_while_typing=True,
        key_bindings=_key_bindings(),
        style=PROMPT_STYLE,
        bottom_toolbar=lambda: render.toolbar(
            ctx.session.repo, ctx.session.branch, len(ctx.session.changed_paths), ctx.critic.backend
        ),
        reserve_space_for_menu=8,
    )
    while True:
        try:
            yield prompt.prompt(lambda: _prompt(ctx))
        except KeyboardInterrupt:
            continue
        except EOFError:
            return


def _read_piped() -> Iterator[str]:
    """Ввод не из консоли (пайп, скрипт): команды построчно, без prompt_toolkit."""
    for line in sys.stdin:
        yield line.rstrip("\r\n")


def _start(ctx: Context) -> None:
    """Загрузка оболочки: под демо-заставку, если она включена и это терминал."""
    if not ctx.settings.intro:
        refresh(ctx)
        return

    def loader(report: Callable[[float], None]) -> None:
        report(0.3)
        refresh(ctx)
        report(1.0)

    intro.play(ctx.console, current_logo(ctx, chrome=2), ctx.settings.intro_sec, loader)


def run_shell(ctx: Context) -> int:
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    ctx.session.logo_font = ctx.settings.logo_font
    if interactive:
        _start(ctx)
        show_header(ctx)
    else:
        refresh(ctx)
    for line in _read_lines(ctx) if interactive else _read_piped():
        try:
            dispatch(ctx, line)
        except ExitShell:
            break
    if interactive:
        ctx.console.print(render.note("GG. До следующего патча."))
    return 0
