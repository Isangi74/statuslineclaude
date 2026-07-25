#!/usr/bin/env bash
# Installs statuslineclaude into ~/.claude
#
# - Copies scripts/statusline.py and scripts/state_collector.py to
#   ~/.claude/scripts/
# - Merges the hooks (PreToolUse/PostToolUse/Stop) and statusLine
#   entries into ~/.claude/settings.json without touching anything
#   else already in that file.
#
# Usage:
#   ./install.sh            install (or update) statuslineclaude
#   ./install.sh --uninstall  remove it again
set -euo pipefail

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SCRIPTS_DIR="$CLAUDE_DIR/scripts"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts"

STATUSLINE_DEST="$SCRIPTS_DIR/statusline.py"
COLLECTOR_DEST="$SCRIPTS_DIR/state_collector.py"

command -v python3 >/dev/null 2>&1 || {
  echo "error: python3 is required and was not found on PATH" >&2
  exit 1
}

if [[ "${1:-}" == "--uninstall" ]]; then
  python3 - "$SETTINGS_FILE" "$STATUSLINE_DEST" "$COLLECTOR_DEST" <<'PY'
import json
import sys

settings_file, statusline_path, collector_path = sys.argv[1:4]

try:
    with open(settings_file) as fh:
        settings = json.load(fh)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

if settings.get("statusLine", {}).get("command") == statusline_path:
    settings.pop("statusLine", None)

hooks = settings.get("hooks", {})
for event in ("PreToolUse", "PostToolUse", "Stop"):
    groups = hooks.get(event)
    if not groups:
        continue
    kept = []
    for group in groups:
        entries = [h for h in group.get("hooks", []) if h.get("command") != collector_path]
        if entries:
            group["hooks"] = entries
            kept.append(group)
    if kept:
        hooks[event] = kept
    else:
        hooks.pop(event, None)
if hooks:
    settings["hooks"] = hooks
else:
    settings.pop("hooks", None)

with open(settings_file, "w") as fh:
    json.dump(settings, fh, indent=2)
    fh.write("\n")
PY
  rm -f "$STATUSLINE_DEST" "$COLLECTOR_DEST"
  echo "statuslineclaude uninstalled from $CLAUDE_DIR"
  exit 0
fi

mkdir -p "$SCRIPTS_DIR"
cp "$SOURCE_DIR/statusline.py" "$STATUSLINE_DEST"
cp "$SOURCE_DIR/state_collector.py" "$COLLECTOR_DEST"
chmod +x "$STATUSLINE_DEST" "$COLLECTOR_DEST"

python3 - "$SETTINGS_FILE" "$STATUSLINE_DEST" "$COLLECTOR_DEST" <<'PY'
import json
import sys

settings_file, statusline_path, collector_path = sys.argv[1:4]

try:
    with open(settings_file) as fh:
        settings = json.load(fh)
except FileNotFoundError:
    settings = {}
except json.JSONDecodeError:
    print(f"error: {settings_file} is not valid JSON, aborting", file=sys.stderr)
    sys.exit(1)

hooks = settings.setdefault("hooks", {})
for event in ("PreToolUse", "PostToolUse", "Stop"):
    groups = hooks.setdefault(event, [])
    already_present = any(
        h.get("command") == collector_path
        for group in groups
        for h in group.get("hooks", [])
    )
    if not already_present:
        groups.append({"hooks": [{"type": "command", "command": collector_path}]})

settings["statusLine"] = {"type": "command", "command": statusline_path}

with open(settings_file, "w") as fh:
    json.dump(settings, fh, indent=2)
    fh.write("\n")
PY

echo "statuslineclaude installed."
echo "  scripts: $SCRIPTS_DIR"
echo "  settings: $SETTINGS_FILE"
echo "Restart Claude Code (or start a new session) to see the status line."
