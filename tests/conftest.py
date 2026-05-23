from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest

from arxgent.config import ArxgentConfig, LLMConfig


@pytest.fixture
def tmp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / ".config" / "arxgent"
    config_dir.mkdir(parents=True)
    monkeypatch.setattr("arxgent.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("arxgent.config.CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr("arxgent.config.PROFILE_FILE", config_dir / "profile.json")
    return config_dir


@pytest.fixture
def default_config() -> ArxgentConfig:
    return ArxgentConfig()


@pytest.fixture
def custom_config() -> ArxgentConfig:
    return ArxgentConfig(
        llm=LLMConfig(model="claude-sonnet-4-20250514", max_tokens=2048, temperature=0.5),
        output_dir="/custom/path",
        num_papers=5,
        skip_review=True,
    )
