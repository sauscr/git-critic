"""Логотип figlet-шрифтами: подбор раскладки под ширину терминала."""

from __future__ import annotations

from functools import lru_cache

import pyfiglet

LOGO_TEXT = "GIT CRITIC"
# Шрифты на выбор (/logo); любой другой шрифт pyfiglet тоже принимается по имени.
FONTS = ("larry3d", "3d-ascii", "bloody", "delta_corps_priest_1", "sub-zero", "poison")
DEFAULT_FONT = FONTS[0]


def font_exists(font: str) -> bool:
    return font in _all_fonts()


@lru_cache(maxsize=1)
def _all_fonts() -> frozenset[str]:
    return frozenset(pyfiglet.FigletFont.getFonts())


def _figlet(text: str, font: str) -> list[str]:
    raw = pyfiglet.figlet_format(text, font=font, width=1000)
    lines = [line.rstrip() for line in raw.splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    return lines


def width_of(lines: list[str]) -> int:
    return max((len(line) for line in lines), default=0)


@lru_cache(maxsize=64)
def render_logo(font: str, max_width: int) -> tuple[str, ...]:
    """Логотип в одну строку, если влезает; иначе «GIT» над «CRITIC»; иначе пусто."""
    if not font_exists(font):
        font = DEFAULT_FONT
    single = _figlet(LOGO_TEXT, font)
    if width_of(single) <= max_width:
        return tuple(single)
    stacked = [*_figlet("GIT", font), "", *_figlet("CRITIC", font)]
    if width_of(stacked) <= max_width:
        return tuple(stacked)
    return ()
