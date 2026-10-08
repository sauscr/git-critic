"""Чистая логика ревью: подготовка кода, сообщения и разбор ответа модели."""

from __future__ import annotations

import json

from gcritic_core.errors import CriticError
from gcritic_core.types import METRIC_MAX, METRIC_NAMES, VERDICTS, BackendInfo, CodeSample, Review

from gcritic_critic.config import TRUNCATION_MARK


def truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + TRUNCATION_MARK, True


def build_sample(
    working_diff: str, recent_patches: str, commits: int, max_chars: int
) -> CodeSample:
    """Незакоммиченные изменения важнее; если их нет — патчи последних коммитов."""
    if working_diff.strip():
        source, raw = "git diff HEAD · незакоммиченные изменения", working_diff
    elif recent_patches.strip():
        source, raw = f"git log -n {commits} -p · последние коммиты", recent_patches
    else:
        raise CriticError("Нечего анализировать: ни изменений, ни коммитов с патчами.")
    text, truncated = truncate(raw, max_chars)
    return CodeSample(source=source, text=text, truncated=truncated)


def build_user_message(sample: CodeSample) -> str:
    truncation_note = "\nВНИМАНИЕ: код обрезан по лимиту размера." if sample.truncated else ""
    return (
        f"Источник: {sample.source}.{truncation_note}\nБилд на обзор:\n```diff\n{sample.text}\n```"
    )


def parse_review(raw: str) -> Review:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CriticError(f"Модель вернула невалидный JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CriticError("Модель вернула не объект JSON.")

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
        if not isinstance(value, int) or isinstance(value, bool):
            raise CriticError(f"Метрика '{name}' отсутствует или не число: {value!r}")
        metrics[name] = max(1, min(METRIC_MAX, value))

    return Review(verdict=verdict, review=review_text, metrics=metrics)


def resolve_backend(preferred: str, availability: dict[str, bool]) -> str:
    """auto → первый доступный по порядку; явное имя — только если доступно."""
    if preferred == "auto":
        for name, ok in availability.items():
            if ok:
                return name
        raise CriticError("Нет доступного бэкенда.")
    if preferred not in availability:
        raise CriticError(
            f"Неизвестный бэкенд {preferred!r}. Есть: auto, {', '.join(availability)}."
        )
    if not availability[preferred]:
        raise CriticError(f"Бэкенд {preferred} недоступен. Список: /backend")
    return preferred


def no_backend_message(backends: list[BackendInfo]) -> str:
    lines = ["Критику нечем писать обзор. Подключи любой бэкенд:"]
    lines += [f"  {b.name:<7} {b.hint}" for b in backends]
    lines.append("Потом перезапусти gcritic или выбери: /backend <имя>")
    return "\n".join(lines)
