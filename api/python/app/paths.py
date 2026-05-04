from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def templates_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "templates"


def public_dir() -> Path:
    return repo_root() / "public"


def public_assets_dir() -> Path:
    return public_dir() / "assets"
