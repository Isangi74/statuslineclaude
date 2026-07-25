"""Tests for install.py.

The installer edits a file the user owns, so the important guarantees are
that it never loses unrelated settings and that uninstalling restores the
file exactly as it was.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from helpers import load_installer

installer = load_installer()


@contextlib.contextmanager
def quiet():
    """Swallow the installer's progress output during tests."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


FOREIGN_SETTINGS = {
    "theme": "dark",
    "model": "claude-opus-5",
    "hooks": {
        "PreToolUse": [
            {"hooks": [{"type": "command", "command": "/usr/local/bin/other-hook"}]}
        ],
        "SessionStart": [
            {"hooks": [{"type": "command", "command": "/usr/local/bin/greet"}]}
        ],
    },
}


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Path(self.tmp.name)
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.config)
        self.addCleanup(os.environ.pop, "CLAUDE_CONFIG_DIR", None)
        self.addCleanup(self.tmp.cleanup)
        self.settings_file = self.config / "settings.json"

    def write_settings(self, data):
        self.settings_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def read_settings(self):
        return json.loads(self.settings_file.read_text(encoding="utf-8"))

    def hook_commands(self, settings, event):
        return [
            entry.get("command")
            for group in settings.get("hooks", {}).get(event, [])
            for entry in group.get("hooks", [])
        ]

    # -- installing ------------------------------------------------------

    def test_install_from_scratch(self):
        with quiet():
            installer.install(dry_run=False)
        settings = self.read_settings()
        self.assertIn("statusline.py", settings["statusLine"]["command"])
        for event in installer.HOOK_EVENTS:
            self.assertTrue(
                any("state_collector.py" in c for c in self.hook_commands(settings, event)),
                msg=event,
            )

    def test_scripts_are_copied(self):
        with quiet():
            installer.install(dry_run=False)
        for name in installer.SCRIPT_NAMES:
            self.assertTrue((self.config / "scripts" / name).is_file(), msg=name)

    @unittest.skipIf(os.name == "nt", "POSIX permissions only")
    def test_scripts_are_executable(self):
        with quiet():
            installer.install(dry_run=False)
        for name in installer.SCRIPT_NAMES:
            mode = (self.config / "scripts" / name).stat().st_mode
            self.assertTrue(mode & 0o111, msg=name)

    def test_existing_settings_are_preserved(self):
        self.write_settings(FOREIGN_SETTINGS)
        with quiet():
            installer.install(dry_run=False)
        settings = self.read_settings()
        self.assertEqual(settings["theme"], "dark")
        self.assertEqual(settings["model"], "claude-opus-5")
        self.assertIn("/usr/local/bin/other-hook", self.hook_commands(settings, "PreToolUse"))
        self.assertIn("/usr/local/bin/greet", self.hook_commands(settings, "SessionStart"))

    def test_install_is_idempotent(self):
        self.write_settings(FOREIGN_SETTINGS)
        with quiet():
            installer.install(dry_run=False)
        first = self.read_settings()
        with quiet():
            installer.install(dry_run=False)
        with quiet():
            installer.install(dry_run=False)
        self.assertEqual(self.read_settings(), first)

    def test_reinstall_refreshes_a_changed_command(self):
        with quiet():
            installer.install(dry_run=False)
        settings = self.read_settings()
        # Simulate an install made with a different interpreter.
        for group in settings["hooks"]["PreToolUse"]:
            for entry in group["hooks"]:
                if "state_collector.py" in entry["command"]:
                    entry["command"] = "old-python " + entry["command"].split(" ", 1)[1]
        self.write_settings(settings)

        with quiet():
            installer.install(dry_run=False)
        commands = self.hook_commands(self.read_settings(), "PreToolUse")
        self.assertEqual(len([c for c in commands if "state_collector.py" in c]), 1)
        self.assertFalse(any(c.startswith("old-python") for c in commands))

    def test_dry_run_changes_nothing(self):
        self.write_settings(FOREIGN_SETTINGS)
        before = self.settings_file.read_text(encoding="utf-8")
        with quiet():
            installer.install(dry_run=True)
        self.assertEqual(self.settings_file.read_text(encoding="utf-8"), before)
        self.assertFalse((self.config / "scripts").exists())

    def test_invalid_settings_file_aborts(self):
        self.settings_file.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(SystemExit), quiet():
            installer.install(dry_run=False)

    # -- uninstalling ----------------------------------------------------

    def test_uninstall_restores_the_original_file(self):
        original = copy.deepcopy(FOREIGN_SETTINGS)
        self.write_settings(original)
        with quiet():
            installer.install(dry_run=False)
        with quiet():
            installer.uninstall(dry_run=False)
        self.assertEqual(self.read_settings(), original)

    def test_uninstall_removes_the_scripts(self):
        with quiet():
            installer.install(dry_run=False)
        with quiet():
            installer.uninstall(dry_run=False)
        for name in installer.SCRIPT_NAMES:
            self.assertFalse((self.config / "scripts" / name).exists(), msg=name)

    def test_uninstall_leaves_a_clean_file_when_nothing_else_is_set(self):
        with quiet():
            installer.install(dry_run=False)
        with quiet():
            installer.uninstall(dry_run=False)
        self.assertEqual(self.read_settings(), {})

    def test_uninstall_keeps_foreign_hooks_on_shared_events(self):
        self.write_settings(FOREIGN_SETTINGS)
        with quiet():
            installer.install(dry_run=False)
        with quiet():
            installer.uninstall(dry_run=False)
        settings = self.read_settings()
        self.assertIn("/usr/local/bin/other-hook", self.hook_commands(settings, "PreToolUse"))

    def test_uninstall_is_idempotent(self):
        with quiet():
            installer.install(dry_run=False)
        with quiet():
            installer.uninstall(dry_run=False)
        first = self.read_settings()
        with quiet():
            installer.uninstall(dry_run=False)
        self.assertEqual(self.read_settings(), first)

    def test_uninstall_without_an_install_is_harmless(self):
        self.write_settings(FOREIGN_SETTINGS)
        with quiet():
            installer.uninstall(dry_run=False)
        self.assertEqual(self.read_settings(), FOREIGN_SETTINGS)


class CommandBuildingTests(unittest.TestCase):
    def test_command_quotes_paths_with_spaces(self):
        command = installer.command_for(Path("/home/some user/.claude/scripts/x.py"))
        self.assertIn("some user", command)
        # The path must be quoted so the shell keeps it as one argument.
        self.assertTrue("'" in command or '"' in command, command)

    def test_command_mentions_an_interpreter(self):
        command = installer.command_for(Path("/tmp/x.py"))
        self.assertTrue(
            command.startswith(("python", "py")) or "python" in command, command
        )


if __name__ == "__main__":
    unittest.main()
