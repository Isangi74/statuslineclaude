#!/usr/bin/env python3
"""Claude Code hook: tracks the current in-flight tool per session.

Wired to PreToolUse/PostToolUse/Stop. On Stop it removes the state
file for the session; on any other event it records which tool ran
and when, so statusline.py can show a short-lived "⚡ <verb>" label.
"""

import json
import sys
import time
from pathlib import Path

STATE_DIR = Path("/tmp/claude-state")


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return

    session_id = data.get("session_id")
    if not session_id:
        return

    state_file = STATE_DIR / f"{session_id}.json"
    event = data.get("hook_event_name")

    try:
        if event == "Stop":
            state_file.unlink(missing_ok=True)
            return

        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps({"tool": data.get("tool_name", ""), "event": event, "ts": time.time()})
        )
    except OSError:
        pass


if __name__ == "__main__":
    main()
