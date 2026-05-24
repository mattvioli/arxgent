from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError


CONFIG_DIR = Path.home() / ".config" / "arxgent"
CONFIG_FILE = CONFIG_DIR / "config.json"
PROFILE_FILE = CONFIG_DIR / "profile.json"


class LLMConfig(BaseModel):
    model: str = "gpt-4o-mini"
    max_tokens: int = 1024
    temperature: float = 0.3


class ArxgentConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    output_dir: str = str(Path.home() / "arxgent_papers")
    num_papers: int = 3
    fetch_count: int = 50


def resolve_env_vars(value: str) -> str:
    if value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.environ.get(env_name, "")
    return value


def get_config_path() -> Path:
    return CONFIG_FILE


def load_config() -> ArxgentConfig:
    path = get_config_path()
    if not path.exists():
        return ArxgentConfig()
    try:
        raw = json.loads(path.read_text())
        return ArxgentConfig.model_validate(raw)
    except (json.JSONDecodeError, ValidationError):
        return ArxgentConfig()


def save_config(config: ArxgentConfig) -> None:
    path = get_config_path()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    path.write_text(json.dumps(data, indent=2))


def config_exists() -> bool:
    return get_config_path().exists()
