"""Рендер-функции: данные → rich-объекты. Ничего не печатают сами."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from gcritic_core.types import (
    INVERTED_METRICS,
    METRIC_MAX,
    METRIC_NAMES,
    BackendInfo,
    Branch,
    CodeSample,
    Commit,
    DayCount,
    FileChange,
    Review,
)
from rich import box
from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from gcritic_tui.theme import (
    BASE,
    BG,
    BLACK,
    CHART_COL_WIDTH,
    CHART_HEIGHT,
    CYAN,
    DIM,
    GREEN,
    RED,
    STATUS_LABELS,
    VERDICT_STYLES,
    VERDICT_TAGLINES,
    WEEKDAY_NAMES,
    WHITE,
    YELLOW,
)


def section(body: RenderableType, title: str, accent: str) -> Panel:
    return Panel(
        body,
        title=Text(f" {title} ", style=accent),
        title_align="left",
        border_style=accent,
        box=box.HEAVY,
        style=BASE,
        padding=(1, 2),
    )


def note(message: str) -> Text:
    return Text(message, style=DIM)


def error(message: str) -> Panel:
    return Panel(
        Text(message, style="white"),
        title=Text(" GAME OVER ", style=f"{RED} reverse"),
        title_align="left",
        border_style=RED,
        box=box.HEAVY,
        style=BASE,
        padding=(1, 2),
    )


# ─── Шапка ────────────────────────────────────────────────────────────────────


LOGO_GRADIENT = ("#00ffff", "#00d7ff", "#5fafff", "#8787ff", "#af5fff", "#d75fd7", "#ff5faf")


def logo_text(lines: tuple[str, ...]) -> Text:
    """Логотип с вертикальным градиентом циан → маджента; пустой — простой текст."""
    if not lines:
        return Text("GIT CRITIC", style=CYAN)
    text = Text(no_wrap=True, overflow="crop")
    for index, line in enumerate(lines):
        color = LOGO_GRADIENT[index * len(LOGO_GRADIENT) // len(lines)]
        text.append(line + ("\n" if index < len(lines) - 1 else ""), style=f"bold {color}")
    return text


def header(repo: Path | None, branch: str, version: str, logo: tuple[str, ...]) -> Panel:
    title = logo_text(logo)
    meta = Text(justify="center")
    meta.append(f"Git-клиент с обзорами в стиле StopGame · v{version}\n", style=YELLOW)
    if repo is None:
        meta.append("репозиторий не выбран — /repo <путь>", style=RED)
    else:
        meta.append(repo.name, style=WHITE)
        meta.append(f"  ·  {branch}", style=CYAN)
        meta.append(f"  ·  {repo}", style=DIM)
    meta.append("\n\n/ — команды   ? — справка   Tab — дополнение", style=DIM)
    return Panel(
        Group(Align.center(title), Text(""), meta),
        box=box.DOUBLE,
        border_style=CYAN,
        style=BASE,
        padding=(1, 2),
    )


# ─── Справка ──────────────────────────────────────────────────────────────────


def help_table(rows: list[tuple[str, str, str]]) -> Panel:
    """rows: (команда с аргументами, хоткей, описание)."""
    table = Table.grid(padding=(0, 3))
    table.add_column(no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column()
    for usage, hotkey, description in rows:
        table.add_row(Text(usage, style=CYAN), Text(hotkey, style=YELLOW), Text(description))
    keys = Text("\n↑/↓ история · Tab дополнение · Esc сброс ввода · ^C отмена", style=DIM)
    return section(Group(table, keys), "КОМАНДЫ", CYAN)


# ─── Git: статус, дифф, лог, ветки ────────────────────────────────────────────


def _status_cell(code: str) -> Text:
    if code == " ":
        return Text("·", style=DIM)
    label, style = STATUS_LABELS.get(code, (code, WHITE))
    return Text(label, style=style)


def status_table(changes: list[FileChange], branch: str) -> RenderableType:
    if not changes:
        return section(
            Text("Рабочая копия чиста. Нечего коммитить, нечего ревьюить.", style=GREEN),
            f"СТАТУС · {branch}",
            GREEN,
        )
    table = Table(box=box.SIMPLE_HEAD, style=BASE, header_style=DIM, expand=False, pad_edge=False)
    table.add_column("индекс", no_wrap=True)
    table.add_column("рабочая копия", no_wrap=True)
    table.add_column("файл")
    for change in changes:
        path = Text(change.path, style=WHITE)
        if change.orig_path:
            path = Text.assemble((change.orig_path, DIM), (" → ", DIM), (change.path, WHITE))
        if change.index == "?":
            table.add_row(_status_cell(" "), _status_cell("?"), path)
        else:
            table.add_row(_status_cell(change.index), _status_cell(change.worktree), path)
    staged = sum(change.staged for change in changes)
    summary = Text()
    summary.append(f"{len(changes)} файлов", style=YELLOW)
    summary.append(f"  ·  в индексе: {staged}", style=DIM)
    return section(Group(table, summary), f"СТАТУС · {branch}", YELLOW)


def diff_view(text: str, title: str) -> RenderableType:
    if not text.strip():
        return note(f"{title}: изменений нет.")
    syntax = Syntax(
        text.rstrip("\n"), "diff", theme="monokai", background_color=BLACK, word_wrap=True
    )
    return section(syntax, title, CYAN)


def log_table(commits: list[Commit]) -> RenderableType:
    if not commits:
        return note("Коммитов пока нет.")
    table = Table(box=box.SIMPLE_HEAD, style=BASE, header_style=DIM, pad_edge=False)
    table.add_column("sha", style=YELLOW, no_wrap=True)
    table.add_column("дата", style=DIM, no_wrap=True)
    table.add_column("автор", style=CYAN, no_wrap=True, max_width=20)
    table.add_column("сообщение", style="white")
    for commit in commits:
        table.add_row(commit.sha, commit.date, commit.author, commit.subject)
    return section(table, f"ЛОГ · {len(commits)}", CYAN)


def branches_table(branches: list[Branch]) -> RenderableType:
    if not branches:
        return note("Веток пока нет: сделай первый коммит.")
    table = Table.grid(padding=(0, 2))
    table.add_column(no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column(no_wrap=True)
    for branch in branches:
        marker = Text("●", style=GREEN) if branch.current else Text(" ")
        name = Text(branch.name, style=GREEN if branch.current else "white")
        upstream = Text(branch.upstream or "—", style=DIM)
        track = Text(branch.track, style=RED if "gone" in branch.track else YELLOW)
        table.add_row(marker, name, upstream, track)
    return section(table, f"ВЕТКИ · {len(branches)}", GREEN)


def backends_table(backends: list[BackendInfo], current: str) -> Panel:
    table = Table.grid(padding=(0, 2))
    for _ in range(3):
        table.add_column(no_wrap=True)
    table.add_column()
    for item in backends:
        marker = Text("●", style=GREEN) if item.name == current else Text(" ")
        state = Text("готов", style=GREEN) if item.available else Text("нет", style=RED)
        name = Text(item.name, style=GREEN if item.name == current else WHITE)
        table.add_row(marker, name, state, Text(item.hint, style=DIM))
    caption = Text("\nСменить: /backend <имя> · авто-выбор: /backend auto", style=DIM)
    return section(Group(table, caption), "КРИТИК", CYAN)


# ─── Активность ───────────────────────────────────────────────────────────────


def _axis_label(level: int, scale: int) -> str:
    if level == CHART_HEIGHT:
        return str(scale)
    if level == CHART_HEIGHT // 2 and scale > 1:
        return str(round(scale / 2))
    return ""


def activity(days: list[DayCount], today: date) -> Panel:
    counts = [item.count for item in days]
    scale = max(max(counts, default=0), 1)
    heights = [0 if c == 0 else max(1, round(c / scale * CHART_HEIGHT)) for c in counts]
    axis_width = len(str(scale))

    lines: list[Text] = []
    for level in range(CHART_HEIGHT, 0, -1):
        row = Text(f"{_axis_label(level, scale):>{axis_width}} │", style=DIM)
        for item, height in zip(days, heights, strict=True):
            cell = "███".center(CHART_COL_WIDTH)
            if height >= level:
                row.append(cell, style=CYAN if item.day == today else GREEN)
            else:
                row.append(cell.replace("█", "░"), style=DIM)
        lines.append(row)
    lines.append(Text(f"{'0':>{axis_width}} └" + "─" * (CHART_COL_WIDTH * len(days)), style=DIM))

    day_row = Text(" " * (axis_width + 2))
    count_row = Text(" " * (axis_width + 2))
    for item in days:
        is_today = item.day == today
        day_row.append(
            WEEKDAY_NAMES[item.day.weekday()].center(CHART_COL_WIDTH),
            style=CYAN if is_today else WHITE,
        )
        count_row.append(
            str(item.count).center(CHART_COL_WIDTH), style=YELLOW if item.count else DIM
        )
    lines.extend([day_row, count_row])

    total = sum(counts)
    summary = Text()
    summary.append(f"\nВсего коммитов за {len(days)} дн.: ", style=BASE)
    summary.append(str(total), style=YELLOW)
    if total == 0:
        summary.append("  ·  AFK, сервер пустует", style=DIM)
    return section(Group(*lines, summary), f"АКТИВНОСТЬ · {len(days)} ДН.", GREEN)


# ─── Ревью ────────────────────────────────────────────────────────────────────


def review_source(repo: Path, sample: CodeSample) -> Text:
    meta = Text()
    meta.append("▶ ", style=CYAN)
    meta.append(repo.name, style=WHITE)
    meta.append(f"  ·  {sample.source}", style=DIM)
    if sample.truncated:
        meta.append("  ·  обрезано", style=RED)
    return meta


def verdict(value: str) -> Align:
    accent = VERDICT_STYLES[value]
    stamp = Text(justify="center")
    stamp.append("▓▓▓  В Е Р Д И К Т  ▓▓▓\n\n", style=DIM)
    stamp.append(f"★  {' '.join(value)}  ★", style=f"{accent} reverse")
    stamp.append(f"\n\n{VERDICT_TAGLINES[value]}", style=accent)
    inner = Panel(
        stamp, box=box.HEAVY, border_style=accent, style=BASE, padding=(1, 4), expand=False
    )
    outer = Panel(
        inner, box=box.DOUBLE, border_style=accent, style=BASE, padding=(0, 1), expand=False
    )
    return Align.center(outer, style=BG)


def metric_style(name: str, score: int) -> str:
    quality = METRIC_MAX + 1 - score if name in INVERTED_METRICS else score
    if quality >= 8:
        return GREEN
    if quality >= 5:
        return YELLOW
    return RED


def metrics(values: dict[str, int]) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="left", no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column(justify="right", no_wrap=True)
    for name in METRIC_NAMES:
        score = values[name]
        accent = metric_style(name, score)
        bar = Text()
        bar.append("█▌" * score, style=accent)
        bar.append("░░" * (METRIC_MAX - score), style=DIM)
        label = Text(name, style=WHITE)
        if name in INVERTED_METRICS:
            label.append(" ↓", style=DIM)
        table.add_row(label, bar, Text(f"{score:>2}/{METRIC_MAX}", style=accent))
    caption = Text("\n↓ — чем меньше, тем лучше", style=DIM)
    return section(Group(table, caption), "МЕТРИКИ", CYAN)


def review(result: Review) -> Group:
    body = section(Text(result.review, style="white"), "ОБЗОР", VERDICT_STYLES[result.verdict])
    return Group(verdict(result.verdict), body, metrics(result.metrics))


# ─── Нижняя строка ────────────────────────────────────────────────────────────

TOOLBAR_KEYS = (("?", "help"), ("^R", "review"), ("^L", "clear"), ("^D", "exit"))


def toolbar(
    repo: Path | None, branch: str, changes: int, backend: str = ""
) -> list[tuple[str, str]]:
    """Фрагменты prompt_toolkit: репозиторий · ветка · изменения · критик · хоткеи."""
    sep = ("class:toolbar.sep", "  ·  ")
    parts: list[tuple[str, str]] = [("", " ")]
    if repo is None:
        parts.append(("class:toolbar.dirty", "нет репозитория"))
    else:
        parts += [("class:toolbar.repo", repo.name), sep, ("class:toolbar.branch", branch), sep]
        if changes:
            parts.append(("class:toolbar.dirty", f"{changes} изм."))
        else:
            parts.append(("class:toolbar.clean", "чисто"))
    parts.append(sep)
    if backend:
        parts += [("", "критик "), ("class:toolbar.branch", backend), sep]
    else:
        parts += [("class:toolbar.dirty", "критик не подключён"), sep]
    for index, (key, label) in enumerate(TOOLBAR_KEYS):
        if index:
            parts.append(("", " · "))
        parts += [("class:toolbar.key", key), ("", f" {label}")]
    return parts
