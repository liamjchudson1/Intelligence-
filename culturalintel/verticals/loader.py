"""Load vertical configurations from YAML/JSON config files."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

logger = structlog.get_logger()

VERTICALS_DIR = Path(__file__).parent


def load_vertical(name: str) -> dict:
    """Load a vertical configuration by name.

    Looks for a config.json file in the vertical's subdirectory.
    """
    config_path = VERTICALS_DIR / name / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Vertical config not found: {config_path}")

    with open(config_path) as f:
        config = json.load(f)

    config.setdefault("name", name)
    logger.info("vertical.loaded", name=name, keywords=len(config.get("keywords", [])))
    return config


def list_verticals() -> list[str]:
    """List all available vertical names."""
    verticals = []
    for path in VERTICALS_DIR.iterdir():
        if path.is_dir() and (path / "config.json").exists():
            verticals.append(path.name)
    return sorted(verticals)
