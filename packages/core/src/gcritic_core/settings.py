"""Все настройки gcritic в одном месте.

Порядок источников (выше — важнее):
    1. переменные окружения;
    2. %USERPROFILE%\\.gcritic\\.env;
    3. значения по умолчанию ниже.

У каждого поля в metadata: env — имя переменной, where — кто её читает.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

HOME_DIR = Path.home() / ".gcritic"

# Бэкенды критика: auto — первый доступный в этом порядке (без auto).
BACKENDS = ("auto", "openai", "codex", "claude")
ENV_FILE = HOME_DIR / ".env"


def _var(default, env: str, where: str):
    return field(default=default, metadata={"env": env, "where": where})


@dataclass(frozen=True)
class Settings:
    # Кто пишет обзор: auto | openai (API-ключ) | codex (вход ChatGPT) | claude (вход Claude).
    # auto: есть ключ — openai, иначе установленный codex, иначе claude.
    backend: str = _var("auto", "GCRITIC_BACKEND", "critic_svc")
    # Ключ OpenAI для бэкенда openai. Пусто — openai недоступен.
    openai_api_key: str = _var("", "OPENAI_API_KEY", "critic_svc")
    # Модель OpenAI для ревью. По умолчанию gpt-4o-mini — дёшево и быстро.
    model: str = _var("gpt-4o-mini", "GCRITIC_MODEL", "critic_svc")
    # Температура ответа модели: выше — смешнее и менее предсказуемо.
    temperature: float = _var(0.9, "GCRITIC_TEMPERATURE", "critic_svc")
    # Лимит символов кода, отправляемого на ревью (~4 символа на токен). Минимум 1000.
    max_chars: int = _var(60_000, "GCRITIC_MAX_CHARS", "critic_svc")
    # Таймаут запроса к OpenAI, секунды.
    request_timeout_sec: int = _var(90, "GCRITIC_TIMEOUT", "critic_svc")
    # Модель для codex. Пусто — модель по умолчанию из ~/.codex/config.toml.
    codex_model: str = _var("", "GCRITIC_CODEX_MODEL", "critic_svc")
    # Модель для claude: sonnet | opus | haiku или полный id.
    claude_model: str = _var("sonnet", "GCRITIC_CLAUDE_MODEL", "critic_svc")
    # Таймаут вызова codex/claude, секунды: они медленнее API (агент, вход, старт).
    cli_timeout_sec: int = _var(300, "GCRITIC_CLI_TIMEOUT", "critic_svc")
    # Сколько последних коммитов отдавать на ревью, если рабочая копия чистая.
    review_commits: int = _var(5, "GCRITIC_REVIEW_COMMITS", "tui /review")
    # Сколько коммитов показывает /log без аргумента.
    log_count: int = _var(20, "GCRITIC_LOG_COUNT", "tui /log")
    # Глубина графика активности /stats, дни.
    stats_days: int = _var(7, "GCRITIC_STATS_DAYS", "stats_svc")
    # Шрифт логотипа (figlet): larry3d | 3d-ascii | bloody | delta_corps_priest_1 |
    # sub-zero | poison или любой шрифт pyfiglet. Примерить: /logo.
    logo_font: str = _var("larry3d", "GCRITIC_LOGO_FONT", "tui")
    # Демо-заставка при запуске (любая клавиша — пропустить). 0 — выключить.
    intro: bool = _var(True, "GCRITIC_INTRO", "tui")
    # Длительность заставки, секунды.
    intro_sec: float = _var(4.0, "GCRITIC_INTRO_SEC", "tui")
    # Файл истории ввода оболочки (↑/↓ между запусками).
    history_file: Path = _var(HOME_DIR / "history", "GCRITIC_HISTORY_FILE", "tui")


# Нижние границы числовых настроек: (поле, минимум).
MINIMUMS = (
    ("max_chars", 1_000),
    ("request_timeout_sec", 5),
    ("cli_timeout_sec", 10),
    ("review_commits", 1),
    ("log_count", 1),
    ("stats_days", 1),
)

# Допустимые значения строковых настроек: (поле, варианты).
CHOICES = (("backend", BACKENDS),)
