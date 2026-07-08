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
        self.mod._opencode_auto_flag_cache.clear()
        self.mod._opencode_capabilities_cache.clear()

    def _init_with_templates(self, tmp: str) -> Path:
        config_dir = self.mod.init_config_dir(tmp)
        self.mod._create_factory_templates(config_dir)
        return config_dir

    def test_parse_launch_options(self) -> None:
        options = self.mod._parse_launch_options(["--config-dir", "./configs"])
        self.assertEqual(options.config_dir, "./configs")

        with self.assertRaises(self.mod.ConfigError):
            self.mod._parse_launch_options(["codex"])

        with self.assertRaises(self.mod.ConfigError):
            self.mod._parse_launch_options(["--port", "9000"])

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
            import yaml

            for name in ("opencode.yaml", "codex.yaml", "article-en.yaml"):
                content = (config_dir / name).read_text(encoding="utf-8")
                parsed = yaml.safe_load(content)
                self.assertIsInstance(parsed.get("prompts"), list)
                self.assertGreater(len(parsed["prompts"]), 0)

    def test_create_factory_templates_overwrites_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "opencode.yaml"
            existing.write_text("custom: true\n", encoding="utf-8")
            config_dir = self.mod.init_config_dir(tmp)
            result = self.mod._create_factory_templates(config_dir)
            self.assertEqual(result["errors"], [])
            self.assertEqual(sorted(result["created"]), ["article-en.yaml", "codex.yaml"])
            self.assertEqual(result["overwritten"], ["opencode.yaml"])
            self.assertIn("連載文章", existing.read_text(encoding="utf-8"))

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
            ["/usr/bin/opencode", "run", "--print-logs", "-c", "next prompt"],
        )
        self.assertNotIn("ses_not_real", cmd)

    def test_opencode_headless_permission_env_when_no_auto_flag(self) -> None:
        with patch.object(self.mod, "_opencode_cli_supports_auto", return_value=False):
            env = self.mod._subprocess_env_for_command(["opencode", "run"])
        self.assertEqual(env["OPENCODE_PERMISSION"], '{"*":"allow"}')

    def test_opencode_headless_uses_auto_flag_when_supported(self) -> None:
        caps = self.mod.OpenCodeCliCapabilities(version="2.0.0", supports_auto=True)
        with patch.object(self.mod.shutil, "which", return_value="/usr/bin/opencode"):
            with patch.object(self.mod, "_probe_opencode_cli", return_value=caps):
                adapter = self.mod.OpenCodeAdapter(self.mod.CLIConfig(tool="opencode"))
        self.assertEqual(
            adapter.build_run_command("hi"),
            ["/usr/bin/opencode", "run", "--print-logs", "--auto", "hi"],
        )

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
        self.assertTrue(
            self.mod._cli_output_indicates_failure(
                "Positionals:\nOptions:\n-h, --help  show help"
            )
        )
        self.assertFalse(self.mod._stderr_indicates_failure("completed successfully"))

    def test_evaluate_subprocess_success(self) -> None:
        self.assertTrue(self.mod._evaluate_subprocess_success(0, "", ""))
        self.assertFalse(
            self.mod._evaluate_subprocess_success(0, "", "Session not found: ses_1")
        )
        self.assertFalse(self.mod._evaluate_subprocess_success(1, "", ""))

    def test_probe_opencode_cli(self) -> None:
        with patch.object(self.mod.subprocess, "run") as mock_run:
            mock_run.side_effect = [
                self.mod.subprocess.CompletedProcess(
                    args=["opencode", "--version"],
                    returncode=0,
                    stdout="1.2.27\n",
                    stderr="",
                ),
                self.mod.subprocess.CompletedProcess(
                    args=["opencode", "run", "--help"],
                    returncode=0,
                    stdout="Options:\n  -c, --continue\n",
                    stderr="",
                ),
            ]
            caps = self.mod._probe_opencode_cli("/usr/bin/opencode")
        self.assertEqual(caps.version, "1.2.27")
        self.assertFalse(caps.supports_auto)
        self.assertEqual(caps.headless_mode, "OPENCODE_PERMISSION")

    def test_build_round_command_opencode_round2(self) -> None:
        with patch.object(self.mod.shutil, "which", return_value="/usr/bin/opencode"):
            adapter = self.mod.OpenCodeAdapter(self.mod.CLIConfig(tool="opencode"))
        cmd = self.mod._build_round_command(adapter, 2, "ses_fake", "continue writing")
        self.assertIn("-c", cmd)
        self.assertNotIn("-s", cmd)

    def test_services_list_and_templates(self) -> None:
        from tui import services

        with tempfile.TemporaryDirectory() as tmp:
            self.mod.init_config_dir(tmp)
            self.assertEqual(services.list_configs(), [])
            result = services.create_templates()
            self.assertEqual(result["errors"], [])
            self.assertIn("codex.yaml", services.list_configs())

    def test_services_save_and_read_config(self) -> None:
        from tui import services
        from tui.services import ServiceError

        with tempfile.TemporaryDirectory() as tmp:
            self.mod.init_config_dir(tmp)
            yaml_text = "cli:\n  tool: codex\nprompts:\n  - go\n"
            path = services.save_config("test.yaml", yaml_text)
            self.assertTrue(Path(path).is_file())
            payload = services.read_config("test.yaml")
            self.assertIn("tool: codex", payload["content"])
            with self.assertRaises(ServiceError):
                services.read_config("missing.yaml")

    def test_services_prepare_start(self) -> None:
        from tui import services
        from tui.services import ServiceError

        with tempfile.TemporaryDirectory() as tmp:
            config_dir = self._init_with_templates(tmp)
            session_id, resolved = services.prepare_start("codex.yaml", "", "")
            self.assertTrue(session_id.startswith("ses_"))
            self.assertIsNone(resolved)
            with self.assertRaises(ServiceError):
                services.prepare_start("missing.yaml", "", "")

    def test_services_diagnose(self) -> None:
        from tui import services

        with tempfile.TemporaryDirectory() as tmp:
            self.mod.init_config_dir(tmp)
            payload = services.get_diagnose()
            self.assertTrue(payload["ok"])
            self.assertIn("build", payload)
            self.assertIn("issues", payload)

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

    def test_services_rejects_path_traversal(self) -> None:
        from tui import services
        from tui.services import ServiceError

        with tempfile.TemporaryDirectory() as tmp:
            self.mod.init_config_dir(tmp)
            with self.assertRaises(ServiceError):
                services.read_config("..secret.yaml")

    def test_bootstrap_runtime_loads_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = self._init_with_templates(tmp)
            runtime = self.mod._bootstrap_runtime("codex.yaml")
            self.assertEqual(runtime.config.cli.tool, "codex")
            self.assertTrue(runtime.config_path.is_file())

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

    def test_override_working_dir(self) -> None:
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

    def test_services_prepare_start_rejects_invalid_working_dir(self) -> None:
        from tui import services
        from tui.services import ServiceError

        with tempfile.TemporaryDirectory() as tmp:
            self._init_with_templates(tmp)
            with self.assertRaises(ServiceError):
                services.prepare_start(
                    "codex.yaml",
                    "",
                    str(Path(tmp) / "missing-dir"),
                )

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

    def test_parse_opencode_stats_tokens(self) -> None:
        output = (
            "Input 12.5K\n"
            "Output 3K\n"
            "Cache Read 1.2M\n"
            "Cache Write 500\n"
        )
        self.assertEqual(self.mod._parse_opencode_stats_tokens(output), 1_216_000)

    def test_parse_opencode_stats_tokens_empty(self) -> None:
        self.assertIsNone(self.mod._parse_opencode_stats_tokens("no stats here"))

    def test_opencode_build_export_command_returns_none(self) -> None:
        with patch.object(self.mod.shutil, "which", return_value="/usr/bin/opencode"):
            adapter = self.mod.OpenCodeAdapter(self.mod.CLIConfig(tool="opencode"))
        self.assertIsNone(adapter.build_export_command("ses_test"))

    def test_opencode_build_stats_command_includes_project(self) -> None:
        with patch.object(self.mod.shutil, "which", return_value="/usr/bin/opencode"):
            adapter = self.mod.OpenCodeAdapter(self.mod.CLIConfig(tool="opencode"))
        self.assertEqual(adapter.build_stats_command()[-2:], ["--project", ""])

    def test_format_command_preview_truncates_prompt(self) -> None:
        prompt = "x" * 500
        preview = self.mod._format_command_preview(["opencode", "run", prompt])
        self.assertTrue(preview.startswith("opencode run "))
        self.assertLess(len(preview), len(prompt) + 20)

    def test_display_config_show_token_usage_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = self._init_with_templates(tmp)
            config = self.mod.ConfigLoader(config_dir / "opencode.yaml").load()
            self.assertTrue(config.display.show_token_usage)

    def test_round_failure_hint_codes_cli_incompatible(self) -> None:
        result = self.mod.ExecutionResult(
            success=False,
            return_code=1,
            duration_seconds=1.0,
            retry_count=2,
            stderr_text="positionals:\n  CMD\noptions:\n  -h",
        )
        self.assertEqual(
            self.mod._round_failure_hint_codes(result), ["cli_incompatible"]
        )

    def test_round_failure_hint_codes_session_not_found(self) -> None:
        result = self.mod.ExecutionResult(
            success=False,
            return_code=1,
            duration_seconds=1.0,
            retry_count=0,
            stderr_text="Error: session not found",
        )
        self.assertEqual(
            self.mod._round_failure_hint_codes(result), ["session_not_found"]
        )

    def test_format_round_failure_message_i18n(self) -> None:
        from tui import i18n
        from tui.runtime import format_round_failure_message

        result = self.mod.ExecutionResult(
            success=False,
            return_code=2,
            duration_seconds=1.0,
            retry_count=1,
            stderr_text="session not found",
        )
        i18n.set_locale("en")
        message = format_round_failure_message(3, result)
        self.assertIn("Round 3 failed", message)
        self.assertIn("Session cannot resume", message)

        i18n.set_locale("zh-TW")
        message = format_round_failure_message(3, result)
        self.assertIn("第 3 輪失敗", message)
        self.assertIn("Session 無法接續", message)


if __name__ == "__main__":
    unittest.main()
