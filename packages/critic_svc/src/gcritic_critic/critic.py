"""Critic — реализация CriticService: выбор бэкенда + общая логика ревью."""

from __future__ import annotations

from gcritic_core.errors import CriticError
from gcritic_core.settings import Settings
from gcritic_core.types import BackendInfo, CodeSample, Review

from gcritic_critic import logic
from gcritic_critic.backends import Backend, ClaudeBackend, CodexBackend, OpenAIBackend
from gcritic_critic.config import SYSTEM_PROMPT


class Critic:
    def __init__(self, settings: Settings, backends: list[Backend] | None = None) -> None:
        self._settings = settings
        self._backends = backends or [
            OpenAIBackend(settings),
            CodexBackend(settings),
            ClaudeBackend(settings),
        ]
        self._current = ""
        self.use(settings.backend, strict=False)

    @property
    def backend(self) -> str:
        return self._current

    def backends(self) -> list[BackendInfo]:
        return [BackendInfo(b.name, b.available(), b.hint) for b in self._backends]

    def use(self, name: str, *, strict: bool = True) -> None:
        availability = {b.name: b.available() for b in self._backends}
        try:
            self._current = logic.resolve_backend(name.lower(), availability)
        except CriticError:
            if strict:
                raise
            self._current = ""

    def build_sample(self, working_diff: str, recent_patches: str, commits: int) -> CodeSample:
        return logic.build_sample(working_diff, recent_patches, commits, self._settings.max_chars)

    def review(self, sample: CodeSample) -> Review:
        if not self._current:
            raise CriticError(logic.no_backend_message(self.backends()))
        backend = next(b for b in self._backends if b.name == self._current)
        raw = backend.complete(SYSTEM_PROMPT, logic.build_user_message(sample))
        return logic.parse_review(raw)
