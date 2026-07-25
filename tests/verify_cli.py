#!/usr/bin/env python3
"""End-to-end check of the command-line entry points.

The unit tests exercise install.py's functions directly; this drives the
actual CLI in a throwaway config directory, which is what CI runs on every
platform. Usage:

    python3 tests/verify_cli.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_SETTINGS = {"theme": "dark", "model": "claude-opus-5"}

PAYLOAD = {
    "model": {"display_name": "Claude Opus 5", "id": "claude-opus-5"},
    "cost": {"total_cost_usd": 1.5},
    "session_id": "verify-cli",
    "rate_limits": {
        "five_hour": {"used_percentage": 10, "resets_at": 4102444800},
        "seven_day": {"used_percentage": 55, "resets_at": 4102444800},
    },
}


def run(args, env, stdin=None):
    result = subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"command failed: {args}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result.stdout


def check(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")
    print(f"  ok: {message}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "claude-config"
        config.mkdir()
        settings_file = config / "settings.json"
        settings_file.write_text(json.dumps(ORIGINAL_SETTINGS), encoding="utf-8")

        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(config))

        print("installing three times...")
        for _ in range(3):
            run(["install.py"], env)

        settings = json.loads(settings_file.read_text(encoding="utf-8"))
        check("statusline.py" in settings["statusLine"]["command"], "statusLine wired")
        for event in ("PreToolUse", "PostToolUse", "Stop"):
            groups = settings["hooks"][event]
            check(len(groups) == 1, f"{event} has exactly one hook group (idempotent)")
        check(settings["theme"] == "dark", "pre-existing settings preserved")
        for name in ("statusline.py", "state_collector.py"):
            check((config / "scripts" / name).is_file(), f"{name} copied")

        print("rendering the status line...")
        line = run(
            ["scripts/statusline.py"],
            dict(env, COLUMNS="200"),
            stdin=json.dumps(PAYLOAD),
        ).strip()
        check(bool(line), "status line produced output")
        check(len(line.splitlines()) == 1, "status line is a single line")
        check("Claude Opus 5" in line, "status line shows the model")

        print("driving the hook...")
        state_dir = Path(tmp) / "state"
        hook_env = dict(env, CLAUDE_STATUSLINE_STATE_DIR=str(state_dir))
        run(
            ["scripts/state_collector.py"],
            hook_env,
            stdin=json.dumps(
                {
                    "session_id": "verify-cli",
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                }
            ),
        )
        check((state_dir / "verify-cli.json").is_file(), "hook wrote the state file")
        run(
            ["scripts/state_collector.py"],
            hook_env,
            stdin=json.dumps(
                {"session_id": "verify-cli", "hook_event_name": "Stop"}
            ),
        )
        check(
            not (state_dir / "verify-cli.json").exists(),
            "Stop removed the state file",
        )

        print("uninstalling...")
        run(["install.py", "--uninstall"], env)
        after = json.loads(settings_file.read_text(encoding="utf-8"))
        check(after == ORIGINAL_SETTINGS, "uninstall restored the original settings")
        for name in ("statusline.py", "state_collector.py"):
            check(not (config / "scripts" / name).exists(), f"{name} removed")

    print("\nall CLI checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
