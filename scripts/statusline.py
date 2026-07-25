#!/usr/bin/env python3
"""Custom statusLine command for Claude Code.

Reads the statusLine JSON payload from stdin and prints a single line with
the model, current activity, context usage, session token counts, cost and
the 5h / 7d rate-limit windows.

If the line does not fit the terminal width, segments are dropped in this
order until it does: input/output tokens, absolute context value, activity
label, reset timestamps (the percentages are always kept).

Design notes
------------
The transcript can be tens of megabytes, and Claude Code repaints the
status line often, so the file is never read in full:

* the last ``assistant`` usage block is found by seeking from the end of
  the file backwards in small blocks;
* the session token totals are accumulated in an incremental cache that
  only parses the bytes appended since the previous render.

All the data is gathered once and then rendered repeatedly by the
compaction ladder, so widening or narrowing the terminal never costs
extra I/O.

No third-party dependencies: standard library only.
"""

from __future__ import annotations

import contextlib
import getpass
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

__version__ = "1.0.0"

# --------------------------------------------------------------------------
# Defaults (override them with the optional config file, see load_config)
# --------------------------------------------------------------------------

DEFAULTS = {
    # Seconds an activity label stays on screen after the last hook event.
    "activity_max_age_s": 10,
    # Context window sizes, in tokens.
    "context_window": 200_000,
    "context_window_1m": 1_000_000,
    # Percentage thresholds for the green -> yellow -> red ramp.
    "usage_warn_pct": 50,
    "usage_alert_pct": 80,
    # Separator drawn between segments.
    "separator": " │ ",
    # Segments the user can turn off entirely.
    "show_activity": True,
    "show_context": True,
    "show_io": True,
    "show_cost": True,
    "show_rate_limits": True,
    # Strftime pattern for the rate-limit reset stamps.
    "reset_time_format": "%H:%M-%d.%m",
}

CONFIG_FILENAME = "statusline.config.json"

# --------------------------------------------------------------------------
# Colors
# --------------------------------------------------------------------------

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

# --------------------------------------------------------------------------
# Tool name -> activity verb
# --------------------------------------------------------------------------

TOOL_VERBS = {
    "Edit": "Editing",
    "MultiEdit": "Editing",
    "NotebookEdit": "Editing",
    "Write": "Writing",
    "Read": "Reading",
    "Bash": "Running",
    "BashOutput": "Running",
    "Glob": "Searching",
    "Grep": "Searching",
    "WebFetch": "Fetching",
    "WebSearch": "Searching",
    "Task": "Delegating",
    "Agent": "Delegating",
    "TodoWrite": "Planning",
    "AskUserQuestion": "Asking",
}

# How far back we are willing to seek looking for the last assistant entry.
TAIL_BLOCK_BYTES = 256 * 1024
TAIL_MAX_BYTES = 16 * 1024 * 1024

# Cheap pre-filter to skip lines without parsing them as JSON. It is
# deliberately permissive (just the bare word, not '"type":"assistant"'):
# a false positive only costs one wasted parse, whereas a false negative
# would silently produce wrong numbers. Matching the punctuated form would
# assume a compact separator style the transcript writer never promised.
ASSISTANT_MARKER = b"assistant"


# --------------------------------------------------------------------------
# Environment helpers
# --------------------------------------------------------------------------


def colors_enabled() -> bool:
    """Honour the NO_COLOR convention (https://no-color.org)."""
    return "NO_COLOR" not in os.environ


def paint(text: str, color: str) -> str:
    if not colors_enabled():
        return text
    return f"{color}{text}{RESET}"


def _username() -> str:
    """Best-effort current user name, used to scope the state directory."""
    try:
        return getpass.getuser()
    except Exception:
        # getuser() raises when there is no password entry and no env vars.
        return str(os.getuid()) if hasattr(os, "getuid") else "default"


def state_dir() -> Path:
    """Per-user directory for the activity state files.

    Kept inside the system temp directory so the OS reclaims it on reboot,
    but scoped to the current user and created with 0700 so that on a
    shared machine no other user can read the session ids or pre-create the
    directory with permissions that would silently break our writes.

    NOTE: state_collector.py duplicates this helper on purpose, so that both
    scripts stay standalone single files. Keep the two in sync; the test
    suite asserts that they resolve to the same path.
    """
    override = os.environ.get("CLAUDE_STATUSLINE_STATE_DIR")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / f"claude-statusline-{_username()}"


def ensure_state_dir() -> Path | None:
    directory = state_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(directory, 0o700)
        return directory
    except OSError:
        return None


def config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))


def load_config() -> dict:
    """Merge the optional user config file over the defaults."""
    config = dict(DEFAULTS)
    try:
        raw = (config_dir() / CONFIG_FILENAME).read_text(encoding="utf-8")
        user = json.loads(raw)
    except (OSError, json.JSONDecodeError, ValueError):
        return config
    if isinstance(user, dict):
        # Only accept keys we know about, so a typo cannot inject anything.
        config.update({k: v for k, v in user.items() if k in DEFAULTS})
    return config


# --------------------------------------------------------------------------
# Width handling
# --------------------------------------------------------------------------


def display_width(text: str) -> int:
    """Visible width of a string in terminal cells.

    Strips ANSI sequences and counts East-Asian wide characters (such as
    the "high voltage" sign used for the activity label) as two cells, so
    the compaction ladder does not let a line through that would wrap.
    """
    plain = ANSI_RE.sub("", text)
    width = 0
    for char in plain:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def terminal_width() -> int:
    cols = os.environ.get("COLUMNS")
    if cols:
        try:
            value = int(cols)
            if value > 0:
                return value
        except ValueError:
            pass
    return shutil.get_terminal_size(fallback=(120, 24)).columns


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def usage_color(pct: float, config: dict) -> str:
    if pct < config["usage_warn_pct"]:
        return GREEN
    if pct < config["usage_alert_pct"]:
        return YELLOW
    return RED


def parse_resets_at(value):
    """Parse a reset timestamp given as epoch seconds, epoch ms or ISO 8601."""
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        seconds = float(value)
        # Some APIs report milliseconds; anything past year ~5138 in seconds
        # is far more likely to be a millisecond timestamp.
        if seconds > 1e11:
            seconds /= 1000.0
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    return None


def reset_color(resets_at: datetime, cycle_seconds: float) -> str:
    remaining = (resets_at - datetime.now(timezone.utc)).total_seconds()
    fraction = max(remaining, 0) / cycle_seconds if cycle_seconds else 0
    if fraction > 0.50:
        return GREEN
    if fraction > 0.25:
        return YELLOW
    if fraction > 0.10:
        return ORANGE
    return RED


def context_window_for(model_id: str, config: dict) -> int:
    """Pick the context window size for a model id.

    Long-context variants are tagged with a ``1m`` token delimited by a
    non-alphanumeric boundary (``claude-sonnet-4-5[1m]``,
    ``claude-sonnet-4-5-1m``), so a plain substring test is not used: it
    would also match an unrelated id that merely contains "1m".
    """
    if re.search(r"(?<![a-z0-9])1m(?![a-z0-9])", (model_id or "").lower()):
        return int(config["context_window_1m"])
    return int(config["context_window"])


# --------------------------------------------------------------------------
# Transcript reading
# --------------------------------------------------------------------------


def _usage_from_entry(entry: dict):
    message = entry.get("message")
    if isinstance(message, dict):
        usage = message.get("usage")
        if isinstance(usage, dict):
            return usage
    usage = entry.get("usage")
    return usage if isinstance(usage, dict) else None


def last_assistant_usage(transcript_path):
    """Usage block of the most recent assistant message.

    Seeks backwards from the end of the file in blocks instead of reading
    it whole: on a 42 MB transcript this is ~130x faster and uses ~70x less
    memory than slurping the file.
    """
    if not transcript_path:
        return None
    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        return None

    read = 0
    buffer = b""
    try:
        with open(transcript_path, "rb") as handle:
            while read < size and read < TAIL_MAX_BYTES:
                step = min(TAIL_BLOCK_BYTES, size - read)
                read += step
                handle.seek(size - read)
                buffer = handle.read(step) + buffer

                lines = buffer.split(b"\n")
                # lines[0] may be a partial line unless we reached the start.
                complete = lines if read >= size else lines[1:]
                for raw in reversed(complete):
                    if ASSISTANT_MARKER not in raw:
                        continue
                    try:
                        entry = json.loads(raw)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if entry.get("type") != "assistant":
                        continue
                    usage = _usage_from_entry(entry)
                    if usage:
                        return usage
                buffer = lines[0] if read < size else b""
    except OSError:
        return None
    return None


def _io_cache_path(transcript_path: str, directory: Path) -> Path:
    key = hashlib.sha256(str(transcript_path).encode("utf-8")).hexdigest()[:16]
    return directory / f"io-{key}.json"


def _atomic_write(path: Path, payload: str) -> None:
    # Written via a temp file so a concurrent reader never sees a half file.
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink()


def session_io_totals(transcript_path, directory: Path | None):
    """Cumulative input/output tokens for the session.

    Uses an incremental cache: the byte offset reached last time and the
    running totals are stored, so each render only parses the lines that
    were appended since. Without it, every repaint would re-parse the whole
    transcript.
    """
    if not transcript_path:
        return 0, 0
    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        return 0, 0

    cache_path = _io_cache_path(transcript_path, directory) if directory else None
    offset = 0
    total_in = 0
    total_out = 0

    if cache_path is not None:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(cached, dict):
                offset = int(cached.get("offset", 0))
                total_in = int(cached.get("input", 0))
                total_out = int(cached.get("output", 0))
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            offset = total_in = total_out = 0

    # The file shrank: it was rotated or replaced, so start over.
    if offset > size:
        offset = total_in = total_out = 0

    if offset == size:
        return total_in, total_out

    # Stream the new bytes line by line rather than slurping them: on a cold
    # cache the "delta" is the whole transcript, which can be tens of MB.
    consumed = 0
    try:
        with open(transcript_path, "rb") as handle:
            handle.seek(offset)
            pending = b""
            while True:
                block = handle.read(TAIL_BLOCK_BYTES)
                if not block:
                    break
                pending += block
                end = pending.rfind(b"\n")
                if end == -1:
                    continue
                for raw in pending[:end].split(b"\n"):
                    if ASSISTANT_MARKER not in raw:
                        continue
                    try:
                        entry = json.loads(raw)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if entry.get("type") != "assistant":
                        continue
                    usage = _usage_from_entry(entry)
                    if not usage:
                        continue
                    total_in += usage.get("input_tokens") or 0
                    total_out += usage.get("output_tokens") or 0
                consumed += end + 1
                # A partial trailing line is carried over to the next block,
                # and re-read on the next render if the file is still growing.
                pending = pending[end + 1 :]
    except OSError:
        return total_in, total_out

    if cache_path is not None and consumed:
        _atomic_write(
            cache_path,
            json.dumps(
                {"offset": offset + consumed, "input": total_in, "output": total_out}
            ),
        )

    return total_in, total_out


def read_activity(session_id, config: dict):
    """Verb describing what Claude is doing right now, if anything."""
    if not session_id:
        return None
    path = state_dir() / f"{session_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    timestamp = data.get("ts")
    if not isinstance(timestamp, (int, float)):
        return None
    if (time.time() - timestamp) > config["activity_max_age_s"]:
        return None

    tool = data.get("tool")
    if not tool or not isinstance(tool, str):
        return None
    return TOOL_VERBS.get(tool, f"{tool}…")


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def gather(payload: dict, config: dict) -> dict:
    """Collect every value the line may need. Runs exactly once."""
    directory = ensure_state_dir()

    model = payload.get("model") or {}
    if not isinstance(model, dict):
        model = {}
    model_id = model.get("id") or ""
    model_name = model.get("display_name") or model_id or "Claude"

    transcript_path = payload.get("transcript_path")

    usage = last_assistant_usage(transcript_path) or {}
    context_tokens = (
        (usage.get("input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
    )
    window = context_window_for(model_id, config)
    context_pct = min(context_tokens / window * 100, 100) if window else 0.0

    if config["show_io"]:
        tokens_in, tokens_out = session_io_totals(transcript_path, directory)
    else:
        tokens_in = tokens_out = 0

    cost_block = payload.get("cost") or {}
    cost = (cost_block.get("total_cost_usd") if isinstance(cost_block, dict) else 0) or 0

    activity = None
    if config["show_activity"]:
        activity = read_activity(payload.get("session_id"), config)

    limits = payload.get("rate_limits") or {}
    if not isinstance(limits, dict):
        limits = {}

    windows = []
    for key, label, cycle_seconds in (
        ("five_hour", "5h", 5 * 3600),
        ("seven_day", "7d", 7 * 24 * 3600),
    ):
        block = limits.get(key)
        if not isinstance(block, dict):
            continue
        windows.append(
            {
                "label": label,
                "pct": block.get("used_percentage") or 0,
                "resets_at": parse_resets_at(block.get("resets_at")),
                "cycle_seconds": cycle_seconds,
            }
        )

    return {
        "model_name": model_name,
        "activity": activity,
        "context_tokens": context_tokens,
        "context_pct": context_pct,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost": float(cost),
        "windows": windows,
    }


def render(data: dict, config: dict, *, io, context_abs, activity, reset_ts) -> str:
    parts = [paint(data["model_name"], BOLD_CYAN)]

    if activity and data["activity"]:
        parts.append(paint(f"⚡ {data['activity']}", BOLD_YELLOW))

    if config["show_context"]:
        pct = data["context_pct"]
        segment = paint(f"ctx {pct:.0f}%", usage_color(pct, config))
        if context_abs and data["context_tokens"]:
            segment += " " + paint(f"({fmt_tokens(data['context_tokens'])})", GRAY)
        parts.append(segment)

    if io and (data["tokens_in"] or data["tokens_out"]):
        parts.append(
            paint(f"{fmt_tokens(data['tokens_in'])}↑", BLUE)
            + " "
            + paint(f"{fmt_tokens(data['tokens_out'])}↓", GREEN_PLAIN)
        )

    if config["show_cost"]:
        parts.append(paint(f"${data['cost']:.2f}", MAGENTA))

    if config["show_rate_limits"]:
        for window in data["windows"]:
            pct = window["pct"]
            segment = paint(
                f"{window['label']} {pct:.0f}%", usage_color(pct, config)
            )
            if reset_ts and window["resets_at"] is not None:
                stamp = window["resets_at"].astimezone().strftime(
                    config["reset_time_format"]
                )
                segment += " " + paint(
                    f"↻{stamp}",
                    reset_color(window["resets_at"], window["cycle_seconds"]),
                )
            parts.append(segment)

    return config["separator"].join(parts)


# Progressively poorer variants, tried in order until one fits. Each rung
# turns off exactly one more thing than the previous one, so the drop order
# is: input/output tokens, absolute context, activity label, reset stamps.
LADDER = (
    {"io": True, "context_abs": True, "activity": True, "reset_ts": True},
    {"io": False, "context_abs": True, "activity": True, "reset_ts": True},
    {"io": False, "context_abs": False, "activity": True, "reset_ts": True},
    {"io": False, "context_abs": False, "activity": False, "reset_ts": True},
    {"io": False, "context_abs": False, "activity": False, "reset_ts": False},
)


def build(payload: dict, config: dict, width: int) -> str:
    data = gather(payload, config)
    line = ""
    for index, level in enumerate(LADDER):
        line = render(data, config, **level)
        if display_width(line) <= width or index == len(LADDER) - 1:
            break
    return line


def main() -> int:
    try:
        raw = sys.stdin.read()
    except (OSError, UnicodeDecodeError):
        raw = ""

    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    try:
        print(build(payload, load_config(), terminal_width()))
    except Exception:
        # A broken status line is worse than a minimal one: never let an
        # unexpected error leave Claude Code without any output at all.
        model = payload.get("model") or {}
        name = (model.get("display_name") if isinstance(model, dict) else None) or "Claude"
        print(paint(name, BOLD_CYAN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
