from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from arxgent.config import (
    ArxgentConfig,
    CONFIG_DIR,
    LLMConfig,
    config_exists,
    load_config,
    resolve_env_vars,
    save_config,
)


class TestDefaults:
    def test_default_llm_model(self, default_config: ArxgentConfig) -> None:
        assert default_config.llm.model == "gpt-4o-mini"

    def test_default_llm_max_tokens(self, default_config: ArxgentConfig) -> None:
        assert default_config.llm.max_tokens == 1024

    def test_default_llm_temperature(self, default_config: ArxgentConfig) -> None:
        assert default_config.llm.temperature == 0.3

    def test_default_output_dir(self, default_config: ArxgentConfig) -> None:
        assert default_config.output_dir.endswith("arxgent_papers")

    def test_default_num_papers(self, default_config: ArxgentConfig) -> None:
        assert default_config.num_papers == 3


class TestRoundtrip:
    def test_save_and_load(self, tmp_config_dir: Path) -> None:
        config = ArxgentConfig(llm=LLMConfig(model="gpt-4o"), num_papers=5)
        save_config(config)

        loaded = load_config()
        assert loaded.llm.model == "gpt-4o"
        assert loaded.num_papers == 5
        assert loaded.llm.temperature == 0.3

    def test_file_content(self, tmp_config_dir: Path) -> None:
        config = ArxgentConfig()
        save_config(config)

        raw = json.loads((tmp_config_dir / "config.json").read_text())
        assert raw["llm"]["model"] == "gpt-4o-mini"
        assert raw["num_papers"] == 3

    def test_load_nonexistent_returns_defaults(self) -> None:
        config = load_config()
        assert isinstance(config, ArxgentConfig)


class TestPartialConfig:
    def test_merge_partial_with_defaults(self, tmp_config_dir: Path) -> None:
        partial = {"num_papers": 10}
        (tmp_config_dir / "config.json").write_text(json.dumps(partial))

        config = load_config()
        assert config.num_papers == 10
        assert config.llm.model == "gpt-4o-mini"

    def test_merge_partial_llm(self, tmp_config_dir: Path) -> None:
        partial = {"llm": {"temperature": 0.9}}
        (tmp_config_dir / "config.json").write_text(json.dumps(partial))

        config = load_config()
        assert config.llm.temperature == 0.9
        assert config.llm.model == "gpt-4o-mini"
        assert config.llm.max_tokens == 1024


class TestCorruptedConfig:
    def test_invalid_json_returns_defaults(self, tmp_config_dir: Path) -> None:
        (tmp_config_dir / "config.json").write_text("not valid json")
        config = load_config()
        assert isinstance(config, ArxgentConfig)

    def test_wrong_types_returns_defaults(self, tmp_config_dir: Path) -> None:
        (tmp_config_dir / "config.json").write_text(json.dumps({"num_papers": "not_a_number"}))
        config = load_config()
        assert isinstance(config, ArxgentConfig)


class TestConfigExists:
    def test_exists(self, tmp_config_dir: Path) -> None:
        save_config(ArxgentConfig())
        assert config_exists() is True

    def test_not_exists(self) -> None:
        assert config_exists() is False


class TestResolveEnvVars:
    def test_resolves_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_TEST_KEY", "resolved_value")
        assert resolve_env_vars("${MY_TEST_KEY}") == "resolved_value"

    def test_non_env_var_passthrough(self) -> None:
        assert resolve_env_vars("plain_string") == "plain_string"

    def test_empty_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NONEXISTENT_KEY", raising=False)
        assert resolve_env_vars("${NONEXISTENT_KEY}") == ""


class TestCustomConfig:
    def test_custom_llm(self, custom_config: ArxgentConfig) -> None:
        assert custom_config.llm.model == "claude-sonnet-4-20250514"
        assert custom_config.llm.max_tokens == 2048
        assert custom_config.llm.temperature == 0.5

    def test_custom_fields(self, custom_config: ArxgentConfig) -> None:
        assert custom_config.output_dir == "/custom/path"
        assert custom_config.num_papers == 5

    def test_custom_roundtrip(self, tmp_config_dir: Path, custom_config: ArxgentConfig) -> None:
        save_config(custom_config)
        loaded = load_config()
        assert loaded.llm.model == "claude-sonnet-4-20250514"
        assert loaded.num_papers == 5


class TestDirectoryCreation:
    def test_config_dir_created_on_save(self, tmp_config_dir: Path) -> None:
        save_config(ArxgentConfig())
        assert tmp_config_dir.exists()

    def test_nested_permissions(self, tmp_path: Path) -> None:
        deep_path = tmp_path / "a" / "b" / "c"
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("arxgent.config.CONFIG_DIR", deep_path)
        monkeypatch.setattr("arxgent.config.CONFIG_FILE", deep_path / "config.json")
        monkeypatch.setattr("arxgent.config.PROFILE_FILE", deep_path / "profile.json")
        save_config(ArxgentConfig())
        assert deep_path.exists()
