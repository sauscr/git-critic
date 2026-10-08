"""Палитра Pure Black: чёрный фон, неон только на акцентах. Rich + prompt_toolkit."""

from prompt_toolkit.styles import Style

BLACK = "#000000"
BG = f"on {BLACK}"
BASE = f"#d0d0d0 {BG}"
DIM = f"#4a4a4a {BG}"
CYAN = "bold bright_cyan"
GREEN = "bold bright_green"
YELLOW = "bold bright_yellow"
RED = "bold bright_red"
WHITE = "bold white"

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

# Статус файла (буква porcelain) → (подпись, стиль).
STATUS_LABELS = {
    "M": ("изменён", YELLOW),
    "A": ("добавлен", GREEN),
    "D": ("удалён", RED),
    "R": ("переименован", CYAN),
    "C": ("скопирован", CYAN),
    "U": ("конфликт", RED),
    "T": ("тип изменён", YELLOW),
    "?": ("новый", GREEN),
    "!": ("игнорируется", DIM),
}

CHART_HEIGHT = 8
CHART_COL_WIDTH = 5
WEEKDAY_NAMES = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

PROMPT_STYLE = Style.from_dict(
    {
        "": f"bg:{BLACK} #d0d0d0",
        "prompt.repo": "bold #00d7d7",
        "prompt.branch": "#5f8787",
        "prompt.arrow": "bold #00ffff",
        "bottom-toolbar": f"noreverse bg:{BLACK} #4a4a4a",
        "toolbar.repo": "bold #d0d0d0",
        "toolbar.branch": "bold #00d7d7",
        "toolbar.dirty": "bold #ffd700",
        "toolbar.clean": "#5faf5f",
        "toolbar.key": "bold #00ffff",
        "toolbar.sep": "#303030",
        "completion-menu": "bg:#0a0a0a #d0d0d0",
        "completion-menu.completion": "bg:#0a0a0a #d0d0d0",
        "completion-menu.completion.current": "bg:#00afaf #000000 bold",
        "completion-menu.meta.completion": "bg:#0a0a0a #6c6c6c",
        "completion-menu.meta.completion.current": "bg:#008787 #000000",
        "scrollbar.background": "bg:#121212",
        "scrollbar.button": "bg:#00afaf",
    }
)
