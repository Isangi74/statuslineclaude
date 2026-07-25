#!/usr/bin/env python3
"""Claude Code hook: records which tool is running, per session.

Wired to PreToolUse, PostToolUse and Stop. While a tool is running it
writes ``<state_dir>/<session_id>.json`` so statusline.py can show a
short-lived "activity" label; on Stop it removes that file and prunes
leftovers from sessions that ended without a Stop event.

No third-party dependencies: standard library only.
"""

from __future__ import annotations

import getpass
import json
import os
import sys
import tempfile
import time
from pathlib import Path

__version__ = "1.0.0"

# Remove state and cache files untouched for this long (seconds).
STALE_AFTER_S = 7 * 24 * 3600


def _username() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return str(os.getuid()) if hasattr(os, "getuid") else "default"


def state_dir() -> Path:
    """Per-user directory for the activity state files.

    NOTE: statusline.py duplicates this helper on purpose, so that both
    scripts stay standalone single files. Keep the two in sync; the test
    suite asserts that they resolve to the same path.
    """
    override = os.environ.get("CLAUDE_STATUSLINE_STATE_DIR")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / f"claude-statusline-{_username()}"


def prune(directory: Path) -> None:
    """Drop state and token-cache files left behind by dead sessions."""
    cutoff = time.time() - STALE_AFTER_S
    try:
        entries = list(directory.iterdir())
    except OSError:
        return
    for entry in entries:
        try:
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                entry.unlink()
        except OSError:
            continue


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    session_id = payload.get("session_id")
    if not session_id or not isinstance(session_id, str):
        return 0
    # The session id lands in a filename: refuse anything with separators.
    if os.sep in session_id or (os.altsep and os.altsep in session_id) or ".." in session_id:
        return 0

    directory = state_dir()
    state_file = directory / f"{session_id}.json"
    event = payload.get("hook_event_name")

    try:
        if event == "Stop":
            state_file.unlink(missing_ok=True)
            prune(directory)
            return 0

        directory.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(directory, 0o700)

        tool = payload.get("tool_name") or ""
        state_file.write_text(
            json.dumps({"tool": tool, "event": event, "ts": time.time()}),
            encoding="utf-8",
        )
    except OSError:
        # A hook must never break the session over a temp-file problem.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
