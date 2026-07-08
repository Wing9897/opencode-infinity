#!/usr/bin/env python3
"""Smoke tests for OpenCode Infinity."""
from __future__ import annotations

import os
import subprocess
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
            self.assertEqual(sorted(result["created"]), ["article-en.yaml", "codex.yaml", "opencode.yaml"])
            self.assertEqual(result["overwritten"], [])
            self.assertEqual(
                sorted(path.name for path in config_dir.glob("*.yaml")),
                ["article-en.yaml", "codex.yaml", "opencode.yaml"],
            )

    def test_create_factory_templates_overwrites_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "opencode.yaml"
            existing.write_text("custom: true\n", encoding="utf-8")
            config_dir = self.mod.init_config_dir(tmp)
            result = self.mod._create_factory_templates(config_dir)
            self.assertEqual(result["errors"], [])
            self.assertEqual(sorted(result["created"]), ["article-en.yaml", "codex.yaml"])
            self.assertEqual(result["overwritten"], ["opencode.yaml"])
            self.assertIn("連載文章創作", existing.read_text(encoding="utf-8"))

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

    def test_opencode_adapter_model_flag(self) -> None:
        cfg = self.mod.CLIConfig(tool="opencode", model="opencode/deepseek-v4-flash-free")
        with patch.object(self.mod.shutil, "which", return_value="/usr/bin/opencode"):
            adapter = self.mod.OpenCodeAdapter(cfg)
        self.assertEqual(
            adapter.build_run_command("hi"),
            [
                "/usr/bin/opencode",
                "run",
                "--print-logs",
                "--auto",
                "-m",
                "opencode/deepseek-v4-flash-free",
                "hi",
            ],
        )

    def test_opencode_session_command_uses_continue(self) -> None:
        with patch.object(self.mod.shutil, "which", return_value="/usr/bin/opencode"):
            adapter = self.mod.OpenCodeAdapter(self.mod.CLIConfig(tool="opencode"))
        cmd = adapter.build_session_command("ses_not_real", "next prompt")
        self.assertEqual(
            cmd,
            ["/usr/bin/opencode", "run", "--print-logs", "--auto", "-c", "next prompt"],
        )
        self.assertNotIn("ses_not_real", cmd)

    def test_subprocess_env_strips_opencode_desktop_vars(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENCODE_SERVER_PASSWORD": "secret",
                "OPENCODE_SERVER_USERNAME": "user",
                "OPENCODE_CLIENT": "desktop",
                "PATH": "/usr/bin",
            },
            clear=False,
        ):
            env = self.mod._subprocess_env_for_command(["opencode", "run"])
            self.assertNotIn("OPENCODE_SERVER_PASSWORD", env)
            self.assertNotIn("OPENCODE_SERVER_USERNAME", env)
            self.assertNotIn("OPENCODE_CLIENT", env)
            codex_env = self.mod._subprocess_env_for_command(["codex", "exec"])
            self.assertEqual(codex_env["OPENCODE_SERVER_PASSWORD"], "secret")

    def test_stderr_indicates_failure(self) -> None:
        self.assertTrue(
            self.mod._stderr_indicates_failure("ERROR Session not found: ses_123")
        )
        self.assertTrue(self.mod._stderr_indicates_failure("NotFoundError: missing"))
        self.assertFalse(self.mod._stderr_indicates_failure("completed successfully"))

    def test_evaluate_subprocess_success(self) -> None:
        self.assertTrue(self.mod._evaluate_subprocess_success(0, ""))
        self.assertFalse(
            self.mod._evaluate_subprocess_success(0, "Session not found: ses_1")
        )
        self.assertFalse(self.mod._evaluate_subprocess_success(1, ""))

    def test_build_round_command_opencode_round2(self) -> None:
        with patch.object(self.mod.shutil, "which", return_value="/usr/bin/opencode"):
            adapter = self.mod.OpenCodeAdapter(self.mod.CLIConfig(tool="opencode"))
        cmd = self.mod._build_round_command(adapter, 2, "ses_fake", "continue writing")
        self.assertIn("-c", cmd)
        self.assertNotIn("-s", cmd)

    def test_gui_log_broadcasts_to_all_subscribers(self) -> None:
        q1 = self.mod._gui_log_subscribe()
        q2 = self.mod._gui_log_subscribe()
        try:
            self.mod._gui_log("broadcast-check")
            m1 = q1.get_nowait()
            while "broadcast-check" not in m1:
                m1 = q1.get_nowait()
            m2 = q2.get_nowait()
            while "broadcast-check" not in m2:
                m2 = q2.get_nowait()
            self.assertIn("broadcast-check", m1)
            self.assertIn("broadcast-check", m2)
        finally:
            self.mod._gui_log_unsubscribe(q1)
            self.mod._gui_log_unsubscribe(q2)

    def test_ensure_windows_user_path_adds_npm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            npm_dir = Path(tmp) / "npm"
            npm_dir.mkdir()
            with patch.dict(os.environ, {"APPDATA": tmp, "PATH": ""}, clear=False):
                self.mod._ensure_windows_user_path()
                self.assertIn(str(npm_dir), os.environ["PATH"])

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
            self.assertEqual(sorted(create_payload["created"]), ["article-en.yaml", "codex.yaml", "opencode.yaml"])

            self.assertIn("codex.yaml", client.get("/api/configs").get_json()["configs"])
            self.assertFalse(client.get("/api/status").get_json()["running"])

    def test_resolve_execution_working_dir_from_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "codex.yaml"
            config_path.write_text(
                "cli:\n  tool: codex\nexecution:\n  working_dir: "
                + repr(tmp).replace("'", '"')
                + "\n",
                encoding="utf-8",
            )
            config = self.mod.ConfigLoader(config_path).load()
            resolved = self.mod._resolve_execution_working_dir(config)
            self.assertEqual(resolved, Path(tmp).resolve())

    def test_gui_override_working_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with tempfile.TemporaryDirectory() as other:
                config_path = Path(tmp) / "configs" / "codex.yaml"
                config_path.parent.mkdir(parents=True)
                config_path.write_text("cli:\n  tool: codex\n", encoding="utf-8")
                self.mod.init_config_dir(str(config_path.parent))
                config = self.mod.ConfigLoader(config_path).load()
                resolved = self.mod._resolve_execution_working_dir(
                    config, override=other
                )
                self.assertEqual(resolved, Path(other).resolve())

    def test_api_start_rejects_invalid_working_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.mod.init_config_dir(tmp)
            self.mod._create_factory_templates(Path(tmp))
            client = self.mod._create_flask_app().test_client()
            response = client.post(
                "/api/start",
                json={
                    "config": "codex.yaml",
                    "working_dir": str(Path(tmp) / "missing-dir"),
                },
            )
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.get_json()["ok"])

    def test_legacy_task_section_still_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "legacy.yaml"
            config_path.write_text(
                "task:\n  name: legacy\n  language: English\n"
                "cli:\n  tool: codex\n"
                "prompts:\n  - go\n",
                encoding="utf-8",
            )
            loader = self.mod.ConfigLoader(config_path)
            errors = loader.validate(loader._read_yaml())
            warnings = [e for e in errors if e.severity == "warning"]
            self.assertTrue(any("task" in e.field_path for e in warnings))
            config = loader.load()
            self.assertEqual(config.cli.tool, "codex")
            self.assertEqual(config.prompts, ["go"])

    def test_executor_passes_subprocess_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working_dir = Path(tmp).resolve()
            executor = self.mod.Executor(working_dir=working_dir)
            with patch.object(self.mod.subprocess, "run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=["echo"], returncode=0, stdout=b"", stderr=b""
                )
                executor.run_with_retry(
                    command=["echo", "ok"],
                    timeout=5,
                    max_retries=0,
                )
            self.assertEqual(mock_run.call_args.kwargs.get("cwd"), str(working_dir))


if __name__ == "__main__":
    unittest.main()
