#!/usr/bin/env python3
"""Custom statusLine command for Claude Code.

Reads the statusLine JSON payload from stdin and prints a single
status line with model, current activity, context usage, token
counts, session cost and rate-limit windows (5h / 7d).

If the line does not fit in the terminal width, segments are dropped
in this order until it fits: input/output tokens, absolute context
value, activity label, reset timestamps (percentages are kept last).
"""

import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RESET = "\033[0m"
BOLD_CYAN = "\033[1;96m"
BOLD_YELLOW = "\033[1;93m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
ORANGE = "\033[38;5;208m"
BLUE = "\033[94m"
GREEN_PLAIN = "\033[32m"
MAGENTA = "\033[95m"
GRAY = "\033[90m"

ANSI_RE = re.compile(r"\033\[[0-9;]*m")

STATE_DIR = Path("/tmp/claude-state")
ACTIVITY_MAX_AGE_S = 10

TOOL_VERBS = {
    "Edit": "Editing",
    "NotebookEdit": "Editing",
    "Write": "Writing",
    "Bash": "Running",
    "Glob": "Searching",
    "Grep": "Searching",
    "WebFetch": "Fetching",
    "Task": "Delegating",
    "Agent": "Delegating",
    "TodoWrite": "Planning",
    "AskUserQuestion": "Asking",
}


def visible_len(s: str) -> int:
    return len(ANSI_RE.sub("", s))


def terminal_width() -> int:
    cols = os.environ.get("COLUMNS")
    if cols:
        try:
            return int(cols)
        except ValueError:
            pass
    return shutil.get_terminal_size(fallback=(120, 24)).columns


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def usage_color(pct: float) -> str:
    if pct < 50:
        return GREEN
    if pct < 80:
        return YELLOW
    return RED


def parse_resets_at(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            v = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


def reset_color(resets_at: datetime, cycle_seconds: float) -> str:
    remaining = (resets_at - datetime.now(timezone.utc)).total_seconds()
    frac = max(remaining, 0) / cycle_seconds if cycle_seconds else 0
    if frac > 0.5:
        return GREEN
    if frac > 0.25:
        return YELLOW
    if frac > 0.10:
        return ORANGE
    return RED


def read_activity_label(session_id: str):
    if not session_id:
        return None
    state_file = STATE_DIR / f"{session_id}.json"
    try:
        raw = state_file.read_text()
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None

    ts = data.get("ts")
    if ts is None or (time.time() - ts) > ACTIVITY_MAX_AGE_S:
        return None

    tool = data.get("tool")
    if not tool:
        return None

    verb = TOOL_VERBS.get(tool, f"{tool}…")
    return verb


def last_assistant_usage(transcript_path: str):
    if not transcript_path:
        return None
    try:
        with open(transcript_path, "r") as fh:
            lines = fh.readlines()
    except OSError:
        return None

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "assistant":
            continue
        usage = (obj.get("message") or {}).get("usage") or obj.get("usage")
        if usage:
            return usage
    return None


def session_io_totals(transcript_path: str):
    total_in = 0
    total_out = 0
    if not transcript_path:
        return total_in, total_out
    try:
        with open(transcript_path, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "assistant":
                    continue
                usage = (obj.get("message") or {}).get("usage") or obj.get("usage")
                if not usage:
                    continue
                total_in += usage.get("input_tokens", 0) or 0
                total_out += usage.get("output_tokens", 0) or 0
    except OSError:
        pass
    return total_in, total_out


def build_line(data, *, show_io, show_ctx_abs, show_activity, show_reset_ts):
    parts = []

    model = data.get("model", {}) or {}
    model_name = model.get("display_name") or model.get("id") or "Claude"
    model_id = model.get("id", "") or ""
    parts.append(f"{BOLD_CYAN}{model_name}{RESET}")

    if show_activity:
        label = read_activity_label(data.get("session_id"))
        if label:
            parts.append(f"{BOLD_YELLOW}⚡ {label}{RESET}")

    transcript_path = data.get("transcript_path")
    window = 1_000_000 if "1m" in model_id else 200_000
    usage = last_assistant_usage(transcript_path) or {}
    ctx_tokens = (
        (usage.get("input_tokens", 0) or 0)
        + (usage.get("cache_creation_input_tokens", 0) or 0)
        + (usage.get("cache_read_input_tokens", 0) or 0)
    )
    ctx_pct = min(ctx_tokens / window * 100, 100) if window else 0
    color = usage_color(ctx_pct)
    ctx_seg = f"{color}ctx {ctx_pct:.0f}%{RESET}"
    if show_ctx_abs and ctx_tokens:
        ctx_seg += f" {GRAY}({fmt_tokens(ctx_tokens)}){RESET}"
    parts.append(ctx_seg)

    if show_io:
        total_in, total_out = session_io_totals(transcript_path)
        if total_in or total_out:
            parts.append(
                f"{BLUE}{fmt_tokens(total_in)}↑{RESET} "
                f"{GREEN_PLAIN}{fmt_tokens(total_out)}↓{RESET}"
            )

    cost = (data.get("cost", {}) or {}).get("total_cost_usd", 0.0) or 0.0
    parts.append(f"{MAGENTA}${cost:.2f}{RESET}")

    rate_limits = data.get("rate_limits", {}) or {}
    for key, label, cycle_seconds in (
        ("five_hour", "5h", 5 * 3600),
        ("seven_day", "7d", 7 * 24 * 3600),
    ):
        window_data = rate_limits.get(key)
        if not window_data:
            continue
        pct = window_data.get("used_percentage", 0) or 0
        seg = f"{usage_color(pct)}{label} {pct:.0f}%{RESET}"
        if show_reset_ts:
            resets_at = parse_resets_at(window_data.get("resets_at"))
            if resets_at is not None:
                local = resets_at.astimezone()
                stamp = local.strftime("%H:%M-%d.%m")
                seg += f" {reset_color(resets_at, cycle_seconds)}↻{stamp}{RESET}"
        parts.append(seg)

    return " │ ".join(parts)


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {}

    width = terminal_width()

    levels = [
        dict(show_io=True, show_ctx_abs=True, show_activity=True, show_reset_ts=True),
        dict(show_io=False, show_ctx_abs=True, show_activity=True, show_reset_ts=True),
        dict(show_io=False, show_ctx_abs=False, show_activity=True, show_reset_ts=True),
        dict(show_io=False, show_ctx_abs=False, show_activity=False, show_reset_ts=True),
        dict(show_io=False, show_ctx_abs=False, show_activity=False, show_reset_ts=False),
    ]

    line = ""
    for i, level in enumerate(levels):
        line = build_line(data, **level)
        if visible_len(line) <= width or i == len(levels) - 1:
            break

    print(line)


if __name__ == "__main__":
    main()
