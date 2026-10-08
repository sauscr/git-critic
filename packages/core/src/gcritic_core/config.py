"""Загрузка настроек: .env + окружение → frozen Settings."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import fields, replace
from pathlib import Path

from gcritic_core.errors import CriticError
from gcritic_core.settings import CHOICES, ENV_FILE, MINIMUMS, Settings

# ─── Чистые функции ───────────────────────────────────────────────────────────


def parse_env_file(text: str) -> dict[str, str]:
    """KEY=VALUE построчно; # — комментарий; кавычки вокруг значения снимаются."""
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip().removeprefix("﻿")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def _convert(raw: str, default: object, env: str) -> object:
    try:
        if isinstance(default, bool):
            return raw.lower() in {"1", "true", "yes", "on"}
        if isinstance(default, int):
            return int(raw.replace("_", ""))
        if isinstance(default, float):
            return float(raw)
        if isinstance(default, Path):
            return Path(os.path.expandvars(raw)).expanduser()
    except ValueError as exc:
        raise CriticError(f"{env}: не удалось разобрать значение {raw!r}") from exc
    return raw


def build_settings(sources: Mapping[str, str]) -> Settings:
    """Собрать Settings из словаря «имя переменной → строка». Пустые строки игнорируются."""
    overrides: dict[str, object] = {}
    for item in fields(Settings):
        env = item.metadata["env"]
        raw = sources.get(env, "").strip()
        if raw:
            overrides[item.name] = _convert(raw, item.default, env)
    if "backend" in overrides:
        overrides["backend"] = str(overrides["backend"]).lower()
    settings = replace(Settings(), **overrides)
    env_names = {item.name: item.metadata["env"] for item in fields(Settings)}
    for name, minimum in MINIMUMS:
        if getattr(settings, name) < minimum:
            raise CriticError(f"{env_names[name]} должен быть не меньше {minimum}.")
    for name, options in CHOICES:
        if getattr(settings, name) not in options:
            raise CriticError(f"{env_names[name]}: допустимо {' | '.join(options)}.")
    return settings


# ─── Ввод-вывод ───────────────────────────────────────────────────────────────


def load_settings(env_file: Path = ENV_FILE, environ: Mapping[str, str] | None = None) -> Settings:
    file_values = parse_env_file(env_file.read_text(encoding="utf-8")) if env_file.is_file() else {}
    env_values = os.environ if environ is None else environ
    return build_settings({**file_values, **{k: v for k, v in env_values.items() if v.strip()}})
