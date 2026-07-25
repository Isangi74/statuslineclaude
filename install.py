#!/usr/bin/env python3
"""Installer for statuslineclaude.

Copies the two scripts into the Claude Code config directory and merges
the ``statusLine`` entry and the PreToolUse/PostToolUse/Stop hooks into
``settings.json`` without disturbing anything else already in there.

Works on Linux, macOS and Windows. The shell wrappers (``install.sh`` and
``install.ps1``) only locate a Python interpreter and hand over to this
file, so the actual logic lives in one place.

Usage:
    python3 install.py              install or update
    python3 install.py --uninstall  remove it again
    python3 install.py --dry-run    show what would change
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import stat
import sys
from pathlib import Path

HOOK_EVENTS = ("PreToolUse", "PostToolUse", "Stop")
SCRIPT_NAMES = ("statusline.py", "state_collector.py")


def config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude"


def interpreter_name() -> str:
    """Interpreter to invoke the scripts with.

    A bare name (resolved through PATH at run time) is preferred over the
    absolute path of the interpreter running this installer: that way the
    install survives a Python upgrade or a virtualenv being deactivated.
    """
    for candidate in ("python3", "python") if os.name != "nt" else ("python", "py"):
        if shutil.which(candidate):
            return candidate
    # Nothing on PATH; fall back to whatever is running us.
    return sys.executable or "python3"


def command_for(script: Path) -> str:
    """Shell command string Claude Code should run for a script."""
    python = interpreter_name()
    if os.name == "nt":
        return f'{python} "{script}"'
    return f"{python} {shlex.quote(str(script))}"


def load_settings(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"error: {path} is not valid JSON ({exc}); "
            "fix or move it and run the installer again"
        ) from exc
    if not isinstance(data, dict):
        raise SystemExit(f"error: {path} does not contain a JSON object")
    return data


def save_settings(path: Path, settings: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def is_ours(command: str, script_paths) -> bool:
    """True when a settings command refers to one of our scripts."""
    return any(str(script) in (command or "") for script in script_paths)


def add_hooks(settings: dict, collector_command: str, collector_path: Path) -> None:
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise SystemExit("error: 'hooks' in settings.json is not an object")

    for event in HOOK_EVENTS:
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise SystemExit(f"error: hooks.{event} in settings.json is not a list")

        # Refresh a previous install (the command string may have changed,
        # e.g. a different interpreter) instead of appending a duplicate.
        replaced = False
        for group in groups:
            for entry in group.get("hooks", []) if isinstance(group, dict) else []:
                if is_ours(entry.get("command", ""), [collector_path]):
                    entry["command"] = collector_command
                    entry["type"] = "command"
                    replaced = True
        if not replaced:
            groups.append(
                {"hooks": [{"type": "command", "command": collector_command}]}
            )


def remove_hooks(settings: dict, collector_path: Path) -> None:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event in HOOK_EVENTS:
        groups = hooks.get(event)
        if not isinstance(groups, list):
            continue
        kept = []
        for group in groups:
            if not isinstance(group, dict):
                kept.append(group)
                continue
            entries = [
                entry
                for entry in group.get("hooks", [])
                if not is_ours(entry.get("command", ""), [collector_path])
            ]
            if entries:
                group["hooks"] = entries
                kept.append(group)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    if not hooks:
        settings.pop("hooks", None)


def install(dry_run: bool) -> int:
    source = Path(__file__).resolve().parent / "scripts"
    target_dir = config_dir()
    scripts_dir = target_dir / "scripts"
    settings_file = target_dir / "settings.json"

    missing = [name for name in SCRIPT_NAMES if not (source / name).is_file()]
    if missing:
        raise SystemExit(f"error: missing source script(s): {', '.join(missing)}")

    statusline = scripts_dir / "statusline.py"
    collector = scripts_dir / "state_collector.py"

    settings = load_settings(settings_file)
    settings["statusLine"] = {"type": "command", "command": command_for(statusline)}
    add_hooks(settings, command_for(collector), collector)

    if dry_run:
        print(f"would copy   {source / 'statusline.py'} -> {statusline}")
        print(f"would copy   {source / 'state_collector.py'} -> {collector}")
        print(f"would write  {settings_file}:")
        print(json.dumps(settings, indent=2))
        return 0

    scripts_dir.mkdir(parents=True, exist_ok=True)
    for name in SCRIPT_NAMES:
        destination = scripts_dir / name
        shutil.copyfile(source / name, destination)
        if os.name != "nt":
            mode = destination.stat().st_mode
            destination.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    save_settings(settings_file, settings)

    print("statuslineclaude installed.")
    print(f"  scripts:  {scripts_dir}")
    print(f"  settings: {settings_file}")
    print("Restart Claude Code (or open a new session) to see the status line.")
    return 0


def uninstall(dry_run: bool) -> int:
    target_dir = config_dir()
    scripts_dir = target_dir / "scripts"
    settings_file = target_dir / "settings.json"

    statusline = scripts_dir / "statusline.py"
    collector = scripts_dir / "state_collector.py"

    settings = load_settings(settings_file)
    status_block = settings.get("statusLine")
    if isinstance(status_block, dict) and is_ours(
        status_block.get("command", ""), [statusline]
    ):
        settings.pop("statusLine", None)
    remove_hooks(settings, collector)

    if dry_run:
        print(f"would write {settings_file}:")
        print(json.dumps(settings, indent=2))
        print(f"would delete {statusline}")
        print(f"would delete {collector}")
        return 0

    if settings_file.exists():
        save_settings(settings_file, settings)
    for path in (statusline, collector):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            print(f"warning: could not delete {path}: {exc}", file=sys.stderr)

    print(f"statuslineclaude uninstalled from {target_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Install statuslineclaude.")
    parser.add_argument(
        "--uninstall", action="store_true", help="remove the scripts and settings"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the changes without applying them"
    )
    args = parser.parse_args()

    # Deliberate runtime guard: ruff lints against the 3.9 target and so
    # believes this can never fire, but the whole point is to greet someone
    # on an older interpreter with a clear message instead of a traceback.
    if sys.version_info < (3, 9):  # noqa: UP036
        raise SystemExit(
            f"error: Python 3.9+ is required (found {sys.version.split()[0]})"
        )

    return uninstall(args.dry_run) if args.uninstall else install(args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
