"""Central configuration loading. Nothing here reads or prints secrets."""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"


def _load(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_settings() -> dict:
    return _load("settings.yaml")


def load_scoring() -> dict:
    return _load("scoring.yaml")


def load_playbook_cfg() -> dict:
    return _load("playbook_mapping.yaml")


def load_note_signals() -> dict:
    return _load("note_signals.yaml")


def clone(cfg: dict) -> dict:
    return copy.deepcopy(cfg)


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p
