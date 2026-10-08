"""Заставка в духе кряктро и демок 90-х/00-х.

Слои снизу вверх: звёздное поле → copper-бары → логотип (падает с отскоком,
переливается радугой) → слоган печатной машинкой → полоса загрузки → синус-скроллер.
Кадр — чистая функция времени; цикл, клавиатура и фоновая загрузка — в play().
"""

from __future__ import annotations

import colorsys
import math
import random
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from rich.console import Console
from rich.live import Live
from rich.text import Text

# ─── Параметры ────────────────────────────────────────────────────────────────

FPS = 30
STAR_COUNT = 140
STAR_SPEED = 0.35  # доля глубины за секунду
STAR_CHARS = ((0.25, "@"), (0.5, "*"), (0.75, "+"), (math.inf, "."))  # (глубина до, символ)
DROP_SEC = 0.9  # падение логотипа
BOUNCE = 0.18  # амплитуда отскока, доля высоты
RAINBOW_SPEED = 0.35  # оборотов радуги в секунду
COPPER_BARS = (("#ff0055", 0.0), ("#00e5ff", 2.1), ("#ffd400", 4.2))  # (цвет, фаза)
COPPER_HEIGHT = 3
TYPE_START = 1.0  # когда слоган начинает печататься, с
TYPE_CPS = 40  # символов в секунду
SCROLL_CPS = 18  # скорость скроллера, символов в секунду
SCROLL_WAVE = (0.09, 3.0, 1.4)  # (частота по x, по времени, амплитуда в строках)
BAR_WIDTH = 40
BG = "#000000"

TAGLINE = "обзоры кода в стиле StopGame · git-клиент в терминале"
SCROLLER = (
    "*** GIT CRITIC *** cracked & reviewed in 2026 *** "
    "ни один коммит не уйдёт без обзора *** "
    "greetings to: StopGame, Linus, всем кентам, кто коммитит в пятницу вечером *** "
    "костыли — это не баг, это фича раннего доступа *** "
    "нажми любую клавишу *** "
)
STATUS_STEPS = (
    "распаковка трейнера",
    "чтение git",
    "поиск критика",
    "калибровка сарказма",
    "загрузка баг-подвала",
)


@dataclass(frozen=True)
class Star:
    x: float  # -1..1
    y: float  # -1..1
    z: float  # 0..1, начальная глубина


@dataclass(frozen=True)
class Scene:
    width: int
    height: int
    logo: tuple[str, ...]
    stars: tuple[Star, ...]


# ─── Чистые функции ───────────────────────────────────────────────────────────


def make_stars(count: int = STAR_COUNT, seed: int = 1993) -> tuple[Star, ...]:
    rng = random.Random(seed)
    return tuple(
        Star(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0.05, 1)) for _ in range(count)
    )


def rainbow(position: float, lightness: float = 0.6) -> str:
    r, g, b = colorsys.hls_to_rgb(position % 1.0, lightness, 1.0)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def shade(color: str, factor: float) -> str:
    value = int(color[1:], 16)
    channels = ((value >> 16) & 255, (value >> 8) & 255, value & 255)
    return "#" + "".join(f"{max(0, min(255, int(c * factor))):02x}" for c in channels)


def logo_top(t: float, height: int, logo_height: int) -> int:
    """Логотип падает сверху и затухающе подпрыгивает у цели."""
    target = max(1, (height - logo_height) // 2 - 3)
    if t < DROP_SEC:
        progress = t / DROP_SEC
        return round(-logo_height + (target + logo_height) * progress * progress)
    bounce = abs(math.sin((t - DROP_SEC) * 7)) * math.exp(-(t - DROP_SEC) * 4)
    return target - round(bounce * BOUNCE * height)


def progress_bar(progress: float, status: str, width: int = BAR_WIDTH) -> str:
    filled = round(max(0.0, min(1.0, progress)) * width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {progress * 100:3.0f}%  {status}"


Cell = tuple[str, str]  # (символ, стиль)


def background(style: str) -> str:
    """«#fff on #123456» → «on #123456»."""
    _, sep, color = style.rpartition("on ")
    return f"on {color}" if sep else f"on {BG}"


def frame(scene: Scene, t: float, progress: float, status: str) -> Text:
    width, height = scene.width, scene.height
    grid: list[list[Cell]] = [[(" ", f"on {BG}")] * width for _ in range(height)]

    def put(x: int, y: int, char: str, style: str) -> None:
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = (char, style)

    # Звёзды: летят на зрителя, ближние ярче и крупнее.
    cx, cy = width / 2, height / 2
    for star in scene.stars:
        z = (star.z - t * STAR_SPEED) % 1.0 + 0.02
        x, y = round(cx + star.x / z * cx * 0.5), round(cy + star.y / z * cy * 0.5)
        char = next(c for limit, c in STAR_CHARS if z < limit)
        put(x, y, char, f"{shade('#ffffff', 1.1 - z)} on {BG}")

    # Логотип перекрывает звёзды: чистим его область (бары пройдут поверх ниже).
    logo_w = max((len(line) for line in scene.logo), default=0)
    left = (width - logo_w) // 2
    top = logo_top(t, height, len(scene.logo))
    for dy in range(-1, len(scene.logo) + 1):
        for dx in range(-2, logo_w + 2):
            put(left + dx, top + dy, " ", f"on {BG}")

    # Copper-бары: горизонтальные градиентные полосы на синусе.
    for color, phase in COPPER_BARS:
        center = cy + math.sin(t * 1.7 + phase) * height * 0.3
        for offset in range(-(COPPER_HEIGHT // 2), COPPER_HEIGHT // 2 + 1):
            row = round(center) + offset
            if 0 <= row < height:
                tone = shade(color, 1.0 - abs(offset) / (COPPER_HEIGHT + 1) - 0.45)
                grid[row] = [(" ", f"on {tone}")] * width

    # Логотип: радуга по диагонали бежит со временем; фон берём из-под буквы (бар).
    for dy, line in enumerate(scene.logo):
        y = top + dy
        for dx, char in enumerate(line):
            x = left + dx
            if char != " " and 0 <= x < width and 0 <= y < height:
                hue = (dx + dy * 2) / max(logo_w, 1) - t * RAINBOW_SPEED
                put(x, y, char, f"bold {rainbow(hue)} {background(grid[y][x][1])}")

    # Слоган: печатная машинка с мигающим курсором.
    below = top + len(scene.logo) + 1
    shown = TAGLINE[: max(0, int((t - TYPE_START) * TYPE_CPS))]
    cursor = "█" if int(t * 3) % 2 else " "
    tag = shown + (cursor if len(shown) < len(TAGLINE) else "")
    for i, char in enumerate(tag):
        put((width - len(TAGLINE)) // 2 + i, below, char, f"#ffd400 on {BG}")

    # Полоса загрузки.
    bar = progress_bar(progress, status)
    bar_row = height - 6
    for i, char in enumerate(bar):
        style = "#00ff9c" if char == "█" else "#3a3a3a" if char == "░" else "#d0d0d0"
        put((width - len(bar)) // 2 + i, bar_row, char, f"{style} on {BG}")

    # Синус-скроллер внизу.
    freq_x, freq_t, amp = SCROLL_WAVE
    base = height - 3
    shift = t * SCROLL_CPS
    whole, frac = int(shift), shift - int(shift)
    for x in range(width):
        char = SCROLLER[(x + whole) % len(SCROLLER)]
        if char == " ":
            continue
        y = base + round(math.sin((x + frac) * freq_x + t * freq_t) * amp)
        put(x, y, char, f"bold {rainbow(x / width + t * 0.5, 0.65)} on {BG}")

    return _to_text(grid)


def _to_text(grid: list[list[Cell]]) -> Text:
    text = Text(no_wrap=True, overflow="crop")
    for row_index, row in enumerate(grid):
        run_chars: list[str] = []
        run_style = row[0][1]
        for char, style in row:
            if style != run_style:
                text.append("".join(run_chars), style=run_style)
                run_chars, run_style = [], style
            run_chars.append(char)
        text.append("".join(run_chars), style=run_style)
        if row_index < len(grid) - 1:
            text.append("\n")
    return text


# ─── Ввод-вывод ───────────────────────────────────────────────────────────────


@contextmanager
def key_watcher() -> Iterator[Callable[[], bool]]:
    """Контекст, отдающий функцию «была ли нажата клавиша» (неблокирующе)."""
    if sys.platform == "win32":
        import msvcrt

        def pressed() -> bool:
            hit = False
            while msvcrt.kbhit():
                msvcrt.getwch()
                hit = True
            return hit

        yield pressed
        return

    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)

        def pressed() -> bool:
            hit = False
            while select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.read(1)
                hit = True
            return hit

        yield pressed
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


Loader = Callable[[Callable[[float], None]], None]


def play(
    console: Console, logo: tuple[str, ...], duration: float, loader: Loader | None = None
) -> None:
    """Показать заставку. loader(report) выполняется в фоне; report(доля 0..1).

    Заставка идёт не меньше duration (клавиша — пропустить) и не кончается раньше loader.
    Исключение из loader пробрасывается после заставки.
    """
    state = {"done": 0.0, "error": None}

    def run_loader() -> None:
        try:
            if loader:
                loader(lambda value: state.__setitem__("done", value))
        except Exception as exc:
            state["error"] = exc
        finally:
            state["done"] = 1.0

    worker = threading.Thread(target=run_loader, daemon=True)
    worker.start()
    stars = make_stars()
    start = time.monotonic()
    skipped = False
    with key_watcher() as pressed, Live(console=console, screen=True, auto_refresh=False) as live:
        while True:
            t = time.monotonic() - start
            skipped = skipped or pressed()
            loaded = state["done"] >= 1.0 and not worker.is_alive()
            if loaded and (skipped or t >= duration):
                break
            progress = min(state["done"], t / duration) if not skipped else state["done"]
            step = STATUS_STEPS[min(int(progress * len(STATUS_STEPS)), len(STATUS_STEPS) - 1)]
            scene = Scene(console.width, console.height, logo, stars)
            live.update(frame(scene, t, progress, step + "..."), refresh=True)
            time.sleep(1 / FPS)
    if state["error"] is not None:
        raise state["error"]
