#!/usr/bin/env python3
"""Textual TUI smoke tests."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TuiTests(unittest.IsolatedAsyncioTestCase):
    async def test_app_mounts(self) -> None:
        import opencode_infinity as core
        from textual.widgets import Static
        from tui.app import InfinityApp

        with tempfile.TemporaryDirectory() as tmp:
            core.init_config_dir(tmp)
            app = InfinityApp()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                self.assertIsNotNone(app.query_one("#console-panel"))
                self.assertIsNotNone(app.query_one("#editor-panel"))
                indicator = app.query_one("#tab-status", Static)
                self.assertIn("輪次", str(indicator.content))
                self.assertFalse(app.controller.snapshot()["running"])


if __name__ == "__main__":
    unittest.main()
