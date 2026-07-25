"""Tests for scripts/statusline.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from helpers import (
    SCRIPTS_DIR,
    assistant,
    load_statusline,
    user,
    write_transcript,
)

sl = load_statusline()


class FormattingTests(unittest.TestCase):
    def test_fmt_tokens(self):
        self.assertEqual(sl.fmt_tokens(0), "0")
        self.assertEqual(sl.fmt_tokens(999), "999")
        self.assertEqual(sl.fmt_tokens(1_000), "1.0K")
        self.assertEqual(sl.fmt_tokens(45_200), "45.2K")
        self.assertEqual(sl.fmt_tokens(1_300_000), "1.3M")

    def test_usage_color_thresholds(self):
        config = dict(sl.DEFAULTS)
        self.assertEqual(sl.usage_color(0, config), sl.GREEN)
        self.assertEqual(sl.usage_color(49.9, config), sl.GREEN)
        self.assertEqual(sl.usage_color(50, config), sl.YELLOW)
        self.assertEqual(sl.usage_color(79.9, config), sl.YELLOW)
        self.assertEqual(sl.usage_color(80, config), sl.RED)
        self.assertEqual(sl.usage_color(100, config), sl.RED)

    def test_display_width_ignores_ansi(self):
        self.assertEqual(sl.display_width("\033[1;96mabc\033[0m"), 3)

    def test_display_width_counts_wide_chars(self):
        # The activity bolt is East-Asian "Wide": it occupies two cells.
        self.assertEqual(sl.display_width("⚡"), 2)
        # Arrows and the box separator are single width.
        self.assertEqual(sl.display_width("↑↓↻│"), 4)


class ResetTimestampTests(unittest.TestCase):
    def test_epoch_seconds(self):
        moment = sl.parse_resets_at(1_700_000_000)
        self.assertEqual(moment, datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc))

    def test_epoch_milliseconds_are_detected(self):
        seconds = sl.parse_resets_at(1_700_000_000)
        millis = sl.parse_resets_at(1_700_000_000_000)
        self.assertEqual(seconds, millis)

    def test_iso_variants(self):
        expected = datetime(2026, 7, 25, 10, 30, tzinfo=timezone.utc)
        self.assertEqual(sl.parse_resets_at("2026-07-25T10:30:00Z"), expected)
        self.assertEqual(sl.parse_resets_at("2026-07-25T10:30:00+00:00"), expected)
        # A naive timestamp is assumed to be UTC rather than rejected.
        self.assertEqual(sl.parse_resets_at("2026-07-25T10:30:00"), expected)

    def test_invalid_values_return_none(self):
        for value in (None, "", "   ", "not-a-date", {}, [], True, False, 1e300):
            self.assertIsNone(sl.parse_resets_at(value), msg=repr(value))

    def test_reset_color_ramp(self):
        now = datetime.now(timezone.utc)
        cycle = 5 * 3600
        self.assertEqual(sl.reset_color(now + timedelta(hours=4), cycle), sl.GREEN)
        self.assertEqual(sl.reset_color(now + timedelta(hours=2), cycle), sl.YELLOW)
        self.assertEqual(sl.reset_color(now + timedelta(minutes=45), cycle), sl.ORANGE)
        self.assertEqual(sl.reset_color(now + timedelta(minutes=5), cycle), sl.RED)
        # Already elapsed must not blow up or wrap around.
        self.assertEqual(sl.reset_color(now - timedelta(hours=1), cycle), sl.RED)


class ContextWindowTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(sl.DEFAULTS)

    def test_default_window(self):
        self.assertEqual(
            sl.context_window_for("claude-sonnet-5", self.config), 200_000
        )

    def test_long_context_variants(self):
        for model_id in ("claude-sonnet-4-5[1m]", "claude-sonnet-4-5-1m", "model-1M"):
            self.assertEqual(
                sl.context_window_for(model_id, self.config), 1_000_000, msg=model_id
            )

    def test_does_not_match_embedded_1m(self):
        # A bare substring test would wrongly promote these to 1M tokens.
        for model_id in ("claude-x1martian", "claude-91mini", "claude-opus-51m2"):
            self.assertEqual(
                sl.context_window_for(model_id, self.config), 200_000, msg=model_id
            )

    def test_empty_model_id(self):
        self.assertEqual(sl.context_window_for("", self.config), 200_000)
        self.assertEqual(sl.context_window_for(None, self.config), 200_000)


class TranscriptReadingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_returns_last_assistant_usage(self):
        path = self.dir / "t.jsonl"
        write_transcript(
            path,
            [
                user(),
                assistant(input_tokens=1, output_tokens=1),
                user(),
                assistant(input_tokens=99, output_tokens=7, cache_read=5),
            ],
        )
        usage = sl.last_assistant_usage(str(path))
        self.assertEqual(usage["input_tokens"], 99)
        self.assertEqual(usage["cache_read_input_tokens"], 5)

    def test_works_with_spaced_json(self):
        """The pre-filter must not assume compact separators."""
        path = self.dir / "spaced.jsonl"
        write_transcript(path, [assistant(input_tokens=42)], compact=False)
        usage = sl.last_assistant_usage(str(path))
        self.assertIsNotNone(usage)
        self.assertEqual(usage["input_tokens"], 42)

    def test_seeks_across_multiple_blocks(self):
        """The wanted entry sits further back than one seek block."""
        path = self.dir / "big.jsonl"
        padding = [user("x" * 5_000) for _ in range(200)]
        write_transcript(path, [assistant(input_tokens=1234), *padding])
        original = sl.TAIL_BLOCK_BYTES
        sl.TAIL_BLOCK_BYTES = 4096  # force several backwards reads
        try:
            usage = sl.last_assistant_usage(str(path))
        finally:
            sl.TAIL_BLOCK_BYTES = original
        self.assertIsNotNone(usage)
        self.assertEqual(usage["input_tokens"], 1234)

    def test_ignores_malformed_lines(self):
        path = self.dir / "broken.jsonl"
        path.write_text(
            '{"type":"assistant" broken\n'
            + json.dumps(assistant(input_tokens=5)) + "\n"
            + "{not json at all}\n",
            encoding="utf-8",
        )
        usage = sl.last_assistant_usage(str(path))
        self.assertIsNotNone(usage)
        self.assertEqual(usage["input_tokens"], 5)

    def test_missing_or_empty_file(self):
        self.assertIsNone(sl.last_assistant_usage(None))
        self.assertIsNone(sl.last_assistant_usage(str(self.dir / "nope.jsonl")))
        empty = self.dir / "empty.jsonl"
        empty.touch()
        self.assertIsNone(sl.last_assistant_usage(str(empty)))

    def test_no_assistant_entries(self):
        path = self.dir / "users.jsonl"
        write_transcript(path, [user(), user()])
        self.assertIsNone(sl.last_assistant_usage(str(path)))


class IoTotalsCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.state = self.dir / "state"
        self.state.mkdir()
        self.addCleanup(self.tmp.cleanup)

    def totals(self, path):
        return sl.session_io_totals(str(path), self.state)

    def test_totals_match_a_naive_full_scan(self):
        path = self.dir / "t.jsonl"
        entries = []
        expected_in = expected_out = 0
        for i in range(1, 51):
            entries.append(user())
            entries.append(assistant(input_tokens=i * 10, output_tokens=i))
            expected_in += i * 10
            expected_out += i
        write_transcript(path, entries)
        self.assertEqual(self.totals(path), (expected_in, expected_out))

    def test_incremental_update_on_append(self):
        path = self.dir / "t.jsonl"
        write_transcript(path, [assistant(input_tokens=100, output_tokens=10)])
        self.assertEqual(self.totals(path), (100, 10))

        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(assistant(input_tokens=400, output_tokens=90)) + "\n"
            )
        self.assertEqual(self.totals(path), (500, 100))

    def test_repeated_calls_are_stable(self):
        path = self.dir / "t.jsonl"
        write_transcript(path, [assistant(input_tokens=7, output_tokens=3)])
        first = self.totals(path)
        for _ in range(5):
            self.assertEqual(self.totals(path), first)

    def test_partial_trailing_line_is_not_double_counted(self):
        path = self.dir / "t.jsonl"
        write_transcript(path, [assistant(input_tokens=10, output_tokens=1)])
        # A half-written line, as would be seen mid-append.
        with path.open("a", encoding="utf-8") as handle:
            handle.write('{"type":"assistant","message":{"usage":{"input_')
        self.assertEqual(self.totals(path), (10, 1))
        # Completing the line must count it exactly once.
        with path.open("a", encoding="utf-8") as handle:
            handle.write('tokens":5,"output_tokens":2}}}\n')
        self.assertEqual(self.totals(path), (15, 3))

    def test_truncated_file_resets_the_cache(self):
        path = self.dir / "t.jsonl"
        write_transcript(path, [assistant(input_tokens=1000, output_tokens=100)])
        self.assertEqual(self.totals(path), (1000, 100))
        # Rotated / replaced by a shorter file.
        write_transcript(path, [assistant(input_tokens=1, output_tokens=1)])
        self.assertEqual(self.totals(path), (1, 1))

    def test_works_without_a_state_directory(self):
        path = self.dir / "t.jsonl"
        write_transcript(path, [assistant(input_tokens=5, output_tokens=2)])
        self.assertEqual(sl.session_io_totals(str(path), None), (5, 2))

    def test_corrupt_cache_is_recovered(self):
        path = self.dir / "t.jsonl"
        write_transcript(path, [assistant(input_tokens=8, output_tokens=4)])
        self.totals(path)
        cache = sl._io_cache_path(str(path), self.state)
        cache.write_text("{{{ not json", encoding="utf-8")
        self.assertEqual(self.totals(path), (8, 4))


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        os.environ["CLAUDE_STATUSLINE_STATE_DIR"] = str(self.dir)
        self.addCleanup(os.environ.pop, "CLAUDE_STATUSLINE_STATE_DIR", None)
        self.addCleanup(self.tmp.cleanup)
        self.config = dict(sl.DEFAULTS)

    def write_state(self, session, tool, age=0.0):
        (self.dir / f"{session}.json").write_text(
            json.dumps({"tool": tool, "ts": time.time() - age}), encoding="utf-8"
        )

    def test_known_tool_maps_to_verb(self):
        self.write_state("s", "Edit")
        self.assertEqual(sl.read_activity("s", self.config), "Editing")

    def test_unknown_tool_falls_back_to_its_name(self):
        self.write_state("s", "SomeMcpTool")
        self.assertEqual(sl.read_activity("s", self.config), "SomeMcpTool…")

    def test_stale_state_is_ignored(self):
        self.write_state("s", "Bash", age=self.config["activity_max_age_s"] + 5)
        self.assertIsNone(sl.read_activity("s", self.config))

    def test_missing_or_invalid_state(self):
        self.assertIsNone(sl.read_activity(None, self.config))
        self.assertIsNone(sl.read_activity("absent", self.config))
        (self.dir / "bad.json").write_text("nonsense", encoding="utf-8")
        self.assertIsNone(sl.read_activity("bad", self.config))
        (self.dir / "nots.json").write_text('{"tool":"Edit"}', encoding="utf-8")
        self.assertIsNone(sl.read_activity("nots", self.config))


class CompactionLadderTests(unittest.TestCase):
    """The ladder must shed segments in the documented order."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        os.environ["CLAUDE_STATUSLINE_STATE_DIR"] = str(self.dir / "state")
        self.addCleanup(os.environ.pop, "CLAUDE_STATUSLINE_STATE_DIR", None)
        self.addCleanup(self.tmp.cleanup)

        (self.dir / "state").mkdir()
        (self.dir / "state" / "sess.json").write_text(
            json.dumps({"tool": "Edit", "ts": time.time()}), encoding="utf-8"
        )

        # 30_000 + 16_000 = 46_000 tokens of context. Deliberately not a
        # value that lands on a .5 rounding tie, so the expected percentage
        # is unambiguous: 23% of 200K, 5% of 1M.
        self.transcript = self.dir / "t.jsonl"
        write_transcript(
            self.transcript,
            [assistant(input_tokens=30_000, output_tokens=4_000, cache_read=16_000)],
        )

        now = time.time()
        self.payload = {
            "model": {"display_name": "Claude Sonnet 5", "id": "claude-sonnet-5"},
            "cost": {"total_cost_usd": 0.4237},
            "transcript_path": str(self.transcript),
            "session_id": "sess",
            "rate_limits": {
                "five_hour": {"used_percentage": 42, "resets_at": now + 2 * 3600},
                "seven_day": {"used_percentage": 61, "resets_at": now + 86400},
            },
        }
        self.config = dict(sl.DEFAULTS)

    def line_at(self, width):
        return sl.ANSI_RE.sub("", sl.build(self.payload, self.config, width))

    def test_full_line_has_everything(self):
        line = self.line_at(300)
        self.assertIn("Claude Sonnet 5", line)
        self.assertIn("⚡ Editing", line)
        self.assertIn("ctx ", line)
        self.assertIn("(46.0K)", line)
        self.assertIn("↑", line)
        self.assertIn("$0.42", line)
        self.assertIn("5h 42%", line)
        self.assertIn("↻", line)

    def test_ladder_drops_segments_in_order(self):
        # The five rungs of this fixture measure 113 / 98 / 90 / 77 / 51
        # cells, so these widths select one rung each.
        lines = [self.line_at(w) for w in (300, 100, 95, 80, 60)]

        # 1st casualty: the input/output token counts.
        self.assertIn("↑", lines[0])
        self.assertNotIn("↑", lines[1])
        # 2nd: the absolute context value.
        self.assertIn("(46.0K)", lines[1])
        self.assertNotIn("(46.0K)", lines[2])
        # 3rd: the activity label.
        self.assertIn("⚡", lines[2])
        self.assertNotIn("⚡", lines[3])
        # 4th: the reset timestamps, percentages survive.
        self.assertIn("↻", lines[3])
        self.assertNotIn("↻", lines[4])
        self.assertIn("5h 42%", lines[4])

    def test_essentials_always_survive(self):
        for width in (300, 100, 95, 80, 60, 40, 10, 1):
            line = self.line_at(width)
            self.assertIn("Claude Sonnet 5", line)
            self.assertIn("ctx ", line)
            self.assertIn("$0.42", line)
            self.assertIn("5h 42%", line)
            self.assertIn("7d 61%", line)

    def test_line_fits_when_it_can(self):
        # Anything down to the width of the last rung must not overflow.
        for width in (300, 200, 150, 120, 113, 100, 98, 95, 90, 80, 77, 60, 51):
            rendered = sl.build(self.payload, self.config, width)
            self.assertLessEqual(
                sl.display_width(rendered), width, msg=f"overflow at {width}"
            )

    def test_context_percentage_and_window(self):
        # 30_000 + 16_000 = 46_000 of 200_000 -> 23%
        self.assertIn("ctx 23%", self.line_at(300))

    def test_long_context_model_lowers_the_percentage(self):
        # Same 46_000 tokens, now against a 1M window -> 5%.
        self.payload["model"]["id"] = "claude-sonnet-5[1m]"
        self.assertIn("ctx 5%", self.line_at(300))


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.dir)
        self.addCleanup(os.environ.pop, "CLAUDE_CONFIG_DIR", None)
        self.addCleanup(self.tmp.cleanup)

    def test_defaults_when_no_file(self):
        self.assertEqual(sl.load_config(), sl.DEFAULTS)

    def test_user_values_override_defaults(self):
        (self.dir / sl.CONFIG_FILENAME).write_text(
            json.dumps({"separator": " | ", "usage_warn_pct": 30}), encoding="utf-8"
        )
        config = sl.load_config()
        self.assertEqual(config["separator"], " | ")
        self.assertEqual(config["usage_warn_pct"], 30)
        # Untouched keys keep their defaults.
        self.assertEqual(config["context_window"], sl.DEFAULTS["context_window"])

    def test_unknown_keys_are_ignored(self):
        (self.dir / sl.CONFIG_FILENAME).write_text(
            json.dumps({"totally_made_up": 1}), encoding="utf-8"
        )
        self.assertNotIn("totally_made_up", sl.load_config())

    def test_broken_config_falls_back_to_defaults(self):
        (self.dir / sl.CONFIG_FILENAME).write_text("{ not json", encoding="utf-8")
        self.assertEqual(sl.load_config(), sl.DEFAULTS)


class EndToEndTests(unittest.TestCase):
    """Run the script the way Claude Code does: JSON on stdin."""

    def run_script(self, payload, env_extra=None, columns="300"):
        env = dict(os.environ, COLUMNS=columns)
        env.pop("NO_COLOR", None)
        if env_extra:
            env.update(env_extra)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "statusline.py")],
            input=payload if isinstance(payload, str) else json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_prints_a_single_line(self):
        output = self.run_script({"model": {"display_name": "Claude Opus 5"}})
        self.assertEqual(len(output.splitlines()), 1)
        self.assertIn("Claude Opus 5", output)

    def test_survives_garbage_stdin(self):
        for payload in ("", "   ", "not json", "[]", "null", '{"model": "wrong type"}'):
            output = self.run_script(payload)
            self.assertTrue(output, msg=f"no output for {payload!r}")

    def test_no_color_strips_escapes(self):
        output = self.run_script(
            {"model": {"display_name": "Claude Opus 5"}}, {"NO_COLOR": "1"}
        )
        self.assertNotIn("\033", output)

    def test_colors_present_by_default(self):
        output = self.run_script({"model": {"display_name": "Claude Opus 5"}})
        self.assertIn("\033", output)


if __name__ == "__main__":
    unittest.main()
