import json

import pytest
from gcritic_core import CriticError, Settings
from gcritic_core.types import METRIC_NAMES
from gcritic_critic import Critic
from gcritic_critic.backends import parse_claude_output
from gcritic_critic.logic import (
    build_sample,
    build_user_message,
    parse_review,
    resolve_backend,
    truncate,
)


def payload(**overrides) -> str:
    data = {
        "verdict": "ПРОХОДНЯК",
        "review": "  Билд собран на изоленте.  ",
        "metrics": dict.fromkeys(METRIC_NAMES, 5),
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


def test_parse_review_ok():
    review = parse_review(payload())
    assert review.verdict == "ПРОХОДНЯК"
    assert review.review == "Билд собран на изоленте."
    assert review.metrics == dict.fromkeys(METRIC_NAMES, 5)


def test_parse_review_clamps_metrics():
    metrics = {"Чистота кода": 99, "Архитектура": -3, "Уровень костылей": 4}
    assert parse_review(payload(metrics=metrics)).metrics == {
        "Чистота кода": 10,
        "Архитектура": 1,
        "Уровень костылей": 4,
    }


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("{not json", "невалидный JSON"),
        ("[]", "не объект"),
        (payload(verdict="ШЕДЕВР"), "Неизвестный вердикт"),
        (payload(review="   "), "пустой обзор"),
        (payload(metrics={"Чистота кода": 5}), "Архитектура"),
        (payload(metrics=dict.fromkeys(METRIC_NAMES, True)), "не число"),
    ],
)
def test_parse_review_errors(raw: str, message: str):
    with pytest.raises(CriticError, match=message):
        parse_review(raw)


def test_build_sample_priorities_and_truncation():
    assert build_sample("diff", "patches", 5, 1000).text == "diff"
    sample = build_sample("  ", "p" * 2000, 3, 1000)
    assert sample.source.startswith("git log -n 3")
    assert sample.truncated and sample.text.startswith("p" * 1000)
    with pytest.raises(CriticError, match="Нечего"):
        build_sample("", "\n", 5, 1000)


def test_truncate_and_user_message():
    assert truncate("abc", 3) == ("abc", False)
    sample = build_sample("d" * 10, "", 5, 4)
    message = build_user_message(sample)
    assert "обрезан" in message and "```diff\ndddd" in message


class FakeBackend:
    def __init__(self, name: str, ok: bool, answer: str = "") -> None:
        self.name, self.hint, self._ok, self._answer = name, f"подключи {name}", ok, answer
        self.calls: list[tuple[str, str]] = []

    def available(self) -> bool:
        return self._ok

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self._answer


def test_resolve_backend():
    order = {"openai": False, "codex": True, "claude": True}
    assert resolve_backend("auto", order) == "codex"
    assert resolve_backend("claude", order) == "claude"
    with pytest.raises(CriticError, match="недоступен"):
        resolve_backend("openai", order)
    with pytest.raises(CriticError, match="Неизвестный"):
        resolve_backend("gemini", order)
    with pytest.raises(CriticError, match="Нет доступного"):
        resolve_backend("auto", dict.fromkeys(order, False))


def test_critic_auto_picks_available_and_reviews():
    codex = FakeBackend("codex", True, payload())
    critic = Critic(Settings(), [FakeBackend("openai", False), codex])
    assert critic.backend == "codex"
    review = critic.review(build_sample("diff --git a", "", 5, 1000))
    assert review.verdict == "ПРОХОДНЯК"
    system, user = codex.calls[0]
    assert "StopGame" in system and "diff --git a" in user


def test_critic_without_backends():
    critic = Critic(Settings(backend="openai"), [FakeBackend("openai", False)])
    assert critic.backend == ""
    assert [b.available for b in critic.backends()] == [False]
    with pytest.raises(CriticError, match="подключи openai"):
        critic.review(build_sample("d", "", 5, 1000))
    with pytest.raises(CriticError, match="недоступен"):
        critic.use("openai")


def test_critic_switch():
    critic = Critic(Settings(), [FakeBackend("openai", True), FakeBackend("claude", True)])
    assert critic.backend == "openai"
    critic.use("CLAUDE")
    assert critic.backend == "claude"
    critic.use("auto")
    assert critic.backend == "openai"


def test_default_backends_order():
    assert [b.name for b in Critic(Settings()).backends()] == ["openai", "codex", "claude"]


def test_parse_claude_output():
    ok = json.dumps({"is_error": False, "structured_output": {"verdict": "МУСОР"}, "result": ""})
    assert json.loads(parse_claude_output(ok, "", 0)) == {"verdict": "МУСОР"}
    fallback = json.dumps({"is_error": False, "result": '{"a": 1}'})
    assert parse_claude_output(fallback, "", 0) == '{"a": 1}'
    with pytest.raises(CriticError, match="не авторизован"):
        parse_claude_output(json.dumps({"is_error": True, "result": "Please run /login"}), "", 1)
    with pytest.raises(CriticError, match="упал"):
        parse_claude_output("not json", "boom", 1)
