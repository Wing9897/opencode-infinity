#!/usr/bin/env python3
"""Smoke tests for OpenCode Infinity."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


def load_app_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import opencode_infinity

    return opencode_infinity


class SmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_app_module()

    def setUp(self) -> None:
        self.mod._tasks_config_dir = None

    def _init_with_templates(self, tmp: str) -> Path:
        config_dir = self.mod.init_config_dir(tmp)
        self.mod._create_factory_templates(config_dir)
        return config_dir

    def test_parse_launch_options(self) -> None:
        positional, options = self.mod._parse_launch_options(
            ["--config-dir", "./configs", "--port", "9000", "--no-browser", "codex"]
        )
        self.assertEqual(positional, ["codex"])
        self.assertEqual(options.config_dir, "./configs")
        self.assertEqual(options.port, 9000)
        self.assertFalse(options.open_browser)

    def test_resolve_launch_arguments(self) -> None:
        session_id, config_name = self.mod._resolve_launch_arguments(["codex"])
        self.assertTrue(session_id.startswith("ses_"))
        self.assertEqual(config_name, "codex")

        session_id, config_name = self.mod._resolve_launch_arguments(["ses_abc", "codex"])
        self.assertEqual(session_id, "ses_abc")
        self.assertEqual(config_name, "codex")

    def test_init_config_dir_does_not_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = self.mod.init_config_dir(tmp)
            self.assertTrue(config_dir.is_dir())
            self.assertEqual(list(config_dir.glob("*.yaml")), [])

    def test_create_factory_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = self.mod.init_config_dir(tmp)
            result = self.mod._create_factory_templates(config_dir)
            self.assertEqual(result["errors"], [])
            self.assertEqual(sorted(result["created"]), ["codex.yaml", "opencode.yaml"])
            self.assertEqual(result["skipped"], [])
            self.assertEqual(
                sorted(path.name for path in config_dir.glob("*.yaml")),
                ["codex.yaml", "opencode.yaml"],
            )

    def test_create_factory_templates_skips_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "opencode.yaml"
            existing.write_text("custom: true\n", encoding="utf-8")
            config_dir = self.mod.init_config_dir(tmp)
            result = self.mod._create_factory_templates(config_dir)
            self.assertEqual(existing.read_text(encoding="utf-8"), "custom: true\n")
            self.assertEqual(result["created"], ["codex.yaml"])
            self.assertEqual(result["skipped"], ["opencode.yaml"])

    def test_resolve_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = self._init_with_templates(tmp)
            resolved = self.mod._resolve_config_path("codex")
            self.assertEqual(resolved, config_dir / "codex.yaml")

    def test_execution_token_settings_from_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = self._init_with_templates(tmp)
            config = self.mod.ConfigLoader(config_dir / "codex.yaml").load()
            self.assertEqual(config.execution.max_tokens, 128000)
            self.assertEqual(config.execution.token_threshold, 0.7)

    def test_legacy_opencode_token_settings_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "legacy.yaml"
            config_path.write_text(
                "cli:\n  tool: opencode\nexecution:\n  delay: 1\nopencode:\n  max_tokens: 64000\n  token_threshold: 0.5\n  model: opencode/mimo-v2.5-free\nprompts:\n  - go\n",
                encoding="utf-8",
            )
            config = self.mod.ConfigLoader(config_path).load()
            self.assertEqual(config.execution.max_tokens, 64000)
            self.assertEqual(config.execution.token_threshold, 0.5)
            self.assertEqual(config.cli.model, "opencode/mimo-v2.5-free")

    def test_opencode_adapter_model_flag(self) -> None:
        cfg = self.mod.CLIConfig(tool="opencode", model="opencode/deepseek-v4-flash-free")
        with patch.object(self.mod.shutil, "which", return_value="/usr/bin/opencode"):
            adapter = self.mod.OpenCodeAdapter(cfg)
        self.assertEqual(
            adapter.build_run_command("hi"),
            ["opencode", "run", "-m", "opencode/deepseek-v4-flash-free", "hi"],
        )

    def test_validate_session_id(self) -> None:
        self.assertTrue(self.mod._validate_session_id("ses_abc123"))
        self.assertTrue(self.mod._validate_session_id("a1b2c3d4-e5f6-7890-abcd-ef1234567890"))
        self.assertFalse(self.mod._validate_session_id("invalid"))
        self.assertFalse(self.mod._validate_session_id("../ses_abc"))

    def test_config_filename_validation(self) -> None:
        with self.assertRaises(self.mod.ConfigError):
            self.mod._validate_config_filename("../secret.yaml")
        with self.assertRaises(self.mod.ConfigError):
            self.mod._validate_config_filename("bad.txt")

    def test_api_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.mod.init_config_dir(tmp)
            client = self.mod._create_flask_app().test_client()
            response = client.get("/api/config/..secret.yaml")
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.get_json()["ok"])

    def test_api_start_requires_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.mod.init_config_dir(tmp)
            client = self.mod._create_flask_app().test_client()
            response = client.post("/api/start", json={"config": "missing.yaml"})
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.get_json()["ok"])

    def test_flask_api_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.mod.init_config_dir(tmp)
            client = self.mod._create_flask_app().test_client()

            index_response = client.get("/")
            self.assertEqual(index_response.status_code, 200)
            self.assertIn(b"OpenCode Infinity", index_response.data)
            self.assertIn(b"ui-lang-select", index_response.data)

            for asset, content_type in (
                ("/gui/styles.css", "css"),
                ("/gui/app.js", "javascript"),
                ("/gui/i18n.js", "javascript"),
                ("/gui/pico.min.css", "css"),
            ):
                response = client.get(asset)
                self.assertEqual(response.status_code, 200, asset)
                self.assertTrue(response.content_type and content_type in response.content_type)

            self.assertIn(b"MESSAGES", client.get("/gui/i18n.js").data)
            self.assertEqual(client.get("/api/configs").get_json()["configs"], [])

            create_response = client.post("/api/config/create-templates")
            self.assertEqual(create_response.status_code, 200)
            create_payload = create_response.get_json()
            self.assertTrue(create_payload["ok"])
            self.assertEqual(sorted(create_payload["created"]), ["codex.yaml", "opencode.yaml"])

            self.assertIn("codex.yaml", client.get("/api/configs").get_json()["configs"])
            self.assertFalse(client.get("/api/status").get_json()["running"])


if __name__ == "__main__":
    unittest.main()
