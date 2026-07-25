"""Shared helpers for the test suite.

The project ships standalone scripts rather than an installable package,
so the modules under test are loaded straight from their file paths.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_statusline():
    return load_module(SCRIPTS_DIR / "statusline.py", "_sl_statusline")


def load_collector():
    return load_module(SCRIPTS_DIR / "state_collector.py", "_sl_collector")


def load_installer():
    return load_module(REPO_ROOT / "install.py", "_sl_install")


def write_transcript(path: Path, entries, *, compact: bool = True) -> None:
    """Write a JSONL transcript.

    ``compact`` picks the separator style. Both are exercised on purpose:
    the fast pre-filter must not depend on how the writer spaces its JSON.
    """
    separators = (",", ":") if compact else None
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, separators=separators) + "\n")


def assistant(input_tokens=0, output_tokens=0, cache_read=0, cache_creation=0):
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
            },
        },
    }


def user(text="hello"):
    return {"type": "user", "message": {"role": "user", "content": text}}
