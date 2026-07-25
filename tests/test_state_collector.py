"""Tests for scripts/state_collector.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from helpers import SCRIPTS_DIR, load_collector, load_statusline

collector = load_collector()
sl = load_statusline()


class StateDirTests(unittest.TestCase):
    def test_both_scripts_agree_on_the_state_directory(self):
        """The helper is duplicated on purpose; it must not drift."""
        os.environ.pop("CLAUDE_STATUSLINE_STATE_DIR", None)
        self.assertEqual(collector.state_dir(), sl.state_dir())

    def test_environment_override(self):
        os.environ["CLAUDE_STATUSLINE_STATE_DIR"] = "/somewhere/else"
        self.addCleanup(os.environ.pop, "CLAUDE_STATUSLINE_STATE_DIR", None)
        self.assertEqual(collector.state_dir(), Path("/somewhere/else"))
        self.assertEqual(sl.state_dir(), Path("/somewhere/else"))

    def test_directory_is_scoped_to_the_user(self):
        os.environ.pop("CLAUDE_STATUSLINE_STATE_DIR", None)
        self.assertIn("claude-statusline-", collector.state_dir().name)


class HookBehaviourTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "state"
        self.addCleanup(self.tmp.cleanup)

    def run_hook(self, payload):
        env = dict(os.environ, CLAUDE_STATUSLINE_STATE_DIR=str(self.dir))
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "state_collector.py")],
            input=payload if isinstance(payload, str) else json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def state_file(self, session):
        return self.dir / f"{session}.json"

    def test_pre_tool_use_records_the_tool(self):
        self.run_hook(
            {"session_id": "abc", "hook_event_name": "PreToolUse", "tool_name": "Bash"}
        )
        data = json.loads(self.state_file("abc").read_text())
        self.assertEqual(data["tool"], "Bash")
        self.assertEqual(data["event"], "PreToolUse")
        self.assertAlmostEqual(data["ts"], time.time(), delta=30)

    def test_post_tool_use_overwrites(self):
        self.run_hook(
            {"session_id": "abc", "hook_event_name": "PreToolUse", "tool_name": "Bash"}
        )
        self.run_hook(
            {"session_id": "abc", "hook_event_name": "PostToolUse", "tool_name": "Grep"}
        )
        data = json.loads(self.state_file("abc").read_text())
        self.assertEqual(data["tool"], "Grep")

    def test_stop_removes_the_state_file(self):
        self.run_hook(
            {"session_id": "abc", "hook_event_name": "PreToolUse", "tool_name": "Bash"}
        )
        self.assertTrue(self.state_file("abc").exists())
        self.run_hook({"session_id": "abc", "hook_event_name": "Stop"})
        self.assertFalse(self.state_file("abc").exists())

    def test_stop_without_a_state_file_is_harmless(self):
        self.run_hook({"session_id": "never-seen", "hook_event_name": "Stop"})

    def test_sessions_do_not_collide(self):
        self.run_hook(
            {"session_id": "one", "hook_event_name": "PreToolUse", "tool_name": "Edit"}
        )
        self.run_hook(
            {"session_id": "two", "hook_event_name": "PreToolUse", "tool_name": "Read"}
        )
        self.assertEqual(json.loads(self.state_file("one").read_text())["tool"], "Edit")
        self.assertEqual(json.loads(self.state_file("two").read_text())["tool"], "Read")

    def test_garbage_input_is_ignored(self):
        for payload in ("", "   ", "not json", "[]", "null", "123"):
            self.run_hook(payload)

    def test_missing_session_id_writes_nothing(self):
        self.run_hook({"hook_event_name": "PreToolUse", "tool_name": "Bash"})
        self.assertFalse(self.dir.exists() and any(self.dir.iterdir()))

    def test_session_id_cannot_escape_the_state_directory(self):
        """The id lands in a filename, so traversal must be refused."""
        for bad in ("../evil", "a/b", "..", "../../etc/passwd"):
            self.run_hook(
                {"session_id": bad, "hook_event_name": "PreToolUse", "tool_name": "X"}
            )
        outside = Path(self.tmp.name) / "evil.json"
        self.assertFalse(outside.exists())
        if self.dir.exists():
            for entry in self.dir.iterdir():
                self.assertNotIn("..", entry.name)

    @unittest.skipIf(os.name == "nt", "POSIX permissions only")
    def test_state_directory_is_private(self):
        self.run_hook(
            {"session_id": "abc", "hook_event_name": "PreToolUse", "tool_name": "Bash"}
        )
        mode = self.dir.stat().st_mode & 0o777
        self.assertEqual(mode, 0o700, f"expected 0700, got {mode:o}")


class PruneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_stale_files_are_removed_and_fresh_ones_kept(self):
        fresh = self.dir / "fresh.json"
        stale = self.dir / "stale.json"
        fresh.write_text("{}", encoding="utf-8")
        stale.write_text("{}", encoding="utf-8")
        old = time.time() - collector.STALE_AFTER_S - 3600
        os.utime(stale, (old, old))

        collector.prune(self.dir)

        self.assertTrue(fresh.exists())
        self.assertFalse(stale.exists())

    def test_prune_on_a_missing_directory_is_harmless(self):
        collector.prune(self.dir / "does-not-exist")


if __name__ == "__main__":
    unittest.main()
