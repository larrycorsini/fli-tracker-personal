"""Shared I/O utilities for the Fli-Tracker pipeline."""

from __future__ import annotations

import json
import os


def atomic_write_json(path: str, data: object) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(tmp_path, path)


def atomic_write_text(path: str, content: str) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.replace(tmp_path, path)
