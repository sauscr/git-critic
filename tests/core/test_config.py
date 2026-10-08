from dataclasses import fields
from pathlib import Path

import pytest
from gcritic_core import CriticError, Settings, build_settings, load_settings, parse_env_file

BOM = chr(0xFEFF)


def test_parse_env_file_handles_comments_quotes_and_bom():
    lines = [
        f"{BOM}# коммент",
        'OPENAI_API_KEY="sk-1"',
        "export GCRITIC_MODEL = gpt-x",
        "",
        "broken",
    ]
    text = "\n".join([*lines, "A='b'"])
    assert parse_env_file(text) == {"OPENAI_API_KEY": "sk-1", "GCRITIC_MODEL": "gpt-x", "A": "b"}


def test_build_settings_defaults():
    assert build_settings({}) == Settings()


def test_build_settings_converts_types():
    settings = build_settings(
        {
            "GCRITIC_MAX_CHARS": "5_000",
            "GCRITIC_TEMPERATURE": "0.2",
            "GCRITIC_HISTORY_FILE": "~/h.txt",
            "GCRITIC_MODEL": "  ",
        }
    )
    assert settings.max_chars == 5000
    assert settings.temperature == 0.2
    assert settings.history_file == Path.home() / "h.txt"
    assert settings.model == Settings().model


def test_build_settings_rejects_garbage_and_minimums():
    with pytest.raises(CriticError, match="GCRITIC_LOG_COUNT"):
        build_settings({"GCRITIC_LOG_COUNT": "много"})
    with pytest.raises(CriticError, match="GCRITIC_MAX_CHARS"):
        build_settings({"GCRITIC_MAX_CHARS": "10"})


def test_load_settings_environment_beats_env_file(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=from-file\nGCRITIC_LOG_COUNT=7\n", encoding="utf-8")
    settings = load_settings(env_file, {"OPENAI_API_KEY": "from-env", "GCRITIC_LOG_COUNT": ""})
    assert settings.openai_api_key == "from-env"
    assert settings.log_count == 7


def test_load_settings_without_file(tmp_path: Path):
    assert load_settings(tmp_path / "missing", {}) == Settings()


def test_env_example_lists_every_setting():
    example = Path(__file__).parents[2] / ".env.example"
    keys = parse_env_file(example.read_text(encoding="utf-8")).keys()
    assert set(keys) == {item.metadata["env"] for item in fields(Settings)}
    assert build_settings(dict.fromkeys(keys, "")) == Settings()
