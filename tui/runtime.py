"""Background execution bridge for the TUI."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

import opencode_infinity as core


class RunController:
    """Manage a single background execution loop."""

    def __init__(self, on_log: Callable[[str], None], on_stats: Callable[[], None]) -> None:
        self._on_log = on_log
        self._on_stats = on_stats
        self._lock = threading.Lock()
        self.running = False
        self.round_count = 0
        self.session_count = 1
        self.session_id = ""
        self.config_name = ""
        self.working_dir = ""
        self.start_time = 0.0
        self._stop_event: Optional[threading.Event] = None
        self._thread: Optional[threading.Thread] = None

    def _log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self._on_log(f"[{timestamp}] {message}")

    def _sync_stats(self, loop_stats: core._ExecutionLoopStats) -> None:
        with self._lock:
            self.round_count = loop_stats.round_count
            self.session_count = loop_stats.session_count
            self.session_id = loop_stats.session_id
        self._on_stats()

    def start(
        self,
        config_name: str,
        session_id: str,
        working_dir_override: Optional[str] = None,
    ) -> str:
        with self._lock:
            if self.running:
                raise RuntimeError("已在執行中")
            self.running = True
            self.config_name = config_name
            self.session_id = session_id
            self.round_count = 0
            self.session_count = 1
            self.start_time = time.monotonic()
            self._stop_event = threading.Event()

        thread = threading.Thread(
            target=self._run_task,
            args=(config_name, session_id, self._stop_event, working_dir_override),
            daemon=True,
        )
        with self._lock:
            self._thread = thread
        thread.start()
        return session_id

    def stop(self) -> None:
        with self._lock:
            stop_event = self._stop_event
        if stop_event:
            stop_event.set()
        self._log("⏹ 使用者請求停止")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self.running,
                "round_count": self.round_count,
                "session_count": self.session_count,
                "session_id": self.session_id,
                "config_name": self.config_name,
                "working_dir": self.working_dir,
                "start_time": self.start_time,
            }

    def _log_draft_status(self, working_dir: Optional[Path]) -> None:
        base = working_dir if working_dir is not None else Path.cwd()
        draft = base / "output" / "articles" / "draft.md"
        if not draft.is_file():
            return
        try:
            size = draft.stat().st_size
        except OSError as exc:
            self._log(f"  ⚠️ 無法讀取 draft.md: {exc}")
            return
        if size == 0:
            self._log(
                "  ⚠️ draft.md 已建立但為空檔。"
                "這通常不是 exe 權限問題（能建檔代表目錄可寫），"
                "而是本輪 AI 尚未寫入內容；請確認工作目錄正確並讓下一輪繼續。"
            )
            self._log(f"  📁 檔案位置: {draft.resolve()}")
            return
        self._log(f"  📝 draft.md 目前 {size} bytes — {draft.resolve()}")

    def _on_round_success(
        self, round_num: int, result: core.ExecutionResult, working_dir: Optional[Path]
    ) -> None:
        self._log(f"  ✅ Round {round_num} 完成 ({result.duration_seconds:.1f}s)")
        self._log_draft_status(working_dir)

    def _run_task(
        self,
        config_name: str,
        session_id: str,
        stop_event: threading.Event,
        working_dir_override: Optional[str],
    ) -> None:
        self._log(f"🚀 啟動執行 - Config: {config_name}, Session: {session_id}")
        try:
            try:
                runtime = core._bootstrap_runtime(
                    config_name, working_dir_override=working_dir_override
                )
            except (core.ConfigError, OSError, ValueError) as exc:
                self._log(f"❌ 設定載入失敗: {exc}")
                return
            except core.CLIAdapterError as exc:
                self._log(f"❌ CLI 適配器建立失敗: {exc}")
                if core.sys.platform == "win32":
                    self._log(
                        "💡 提示：請確認已安裝 opencode（npm i -g opencode-ai），"
                        "並重新啟動以載入 PATH。"
                    )
                return

            with self._lock:
                self.working_dir = (
                    str(runtime.working_dir) if runtime.working_dir else ""
                )

            self._log(f"📄 讀取設定: {runtime.config_path}")
            self._log(f"✅ 設定載入成功: tool={runtime.config.cli.tool}")

            tool_warning = (
                core._self_tool_directory_warning(runtime.working_dir)
                if runtime.working_dir
                else None
            )
            if tool_warning:
                self._log(f"⚠️ {tool_warning}")
            if runtime.working_dir:
                self._log(f"📁 工作目錄: {runtime.working_dir}")
            else:
                self._log(f"📁 工作目錄: {Path.cwd()}（沿用啟動目錄）")

            core._log_opencode_adapter_info(runtime.adapter, self._log)

            working_dir = runtime.working_dir
            loop_logger = logging.getLogger("opencode_infinity.tui_loop")
            cli_log_state = {"window_start": 0.0, "count": 0, "suppressed": 0}

            def _on_round_begin(
                round_num: int,
                active_session_id: str,
                active_config: core.AppConfig,
                current_prompt: str,
            ) -> None:
                with self._lock:
                    self.round_count = round_num
                    self.session_id = active_session_id
                self._on_stats()
                self._log(
                    f"▶ Round {round_num} | Session: {active_session_id} | "
                    f"Prompt: {core.truncate_text(current_prompt, 60)}"
                )
                self._log("  ⏳ 正在呼叫 AI CLI（首次回應可能需要數分鐘，請稍候）…")

            def _on_cli_output(line: str) -> None:
                clean = core._strip_ansi(line)
                if clean.startswith("[stderr] "):
                    clean = clean[9:]
                clean = clean.strip()
                if not clean:
                    return
                lower = clean.lower()
                if (
                    "service=" in lower
                    and "info" in lower
                    and not any(
                        token in lower
                        for token in ("error", "warn", "fail", "timeout")
                    )
                ):
                    now = time.monotonic()
                    if now - cli_log_state["window_start"] > 1.0:
                        if cli_log_state["suppressed"]:
                            self._log(
                                f"  | ... opencode 內部日誌 (+{cli_log_state['suppressed']} 行已摺疊)"
                            )
                        cli_log_state["window_start"] = now
                        cli_log_state["count"] = 0
                        cli_log_state["suppressed"] = 0
                    if cli_log_state["count"] >= 4:
                        cli_log_state["suppressed"] += 1
                        return
                    cli_log_state["count"] += 1
                self._log(f"  | {core.truncate_text(clean, 1200)}")

            hooks = core._ExecutionLoopHooks(
                should_stop=stop_event.is_set,
                on_round_begin=_on_round_begin,
                on_round_success=lambda round_num, result: self._on_round_success(
                    round_num, result, working_dir
                ),
                on_round_failure=lambda round_num, result: self._log(
                    core._format_round_failure_message(round_num, result)
                ),
                on_session_switched=lambda new_session_id: self._log(
                    f"✅ 切換到新 Session: {new_session_id}"
                ),
                on_session_switch_attempt=lambda: self._log("🔀 觸發 Session 切換..."),
                on_session_switch_failed=lambda message: self._log(
                    f"⚠️ Session 切換失敗: {message}"
                ),
                on_max_rounds_reached=lambda max_rounds: self._log(
                    f"🏁 已達最大輪次 {max_rounds}，停止執行"
                ),
                on_abort=lambda reason: self._log(f"⛔ {reason}，停止執行"),
                on_reloaded=lambda summary: self._log(f"🔄 設定已熱重載: {summary}"),
                on_reload_failed=self._log,
                on_command_preview=lambda command: self._log(
                    f"  執行命令: {core._format_command_preview(command)}"
                ),
                on_token_usage=self._log,
                on_cli_output=_on_cli_output,
                on_iteration_end=self._sync_stats,
                interruptible_delay=True,
            )

            stats, _, _, _ = core._run_execution_loop(
                config_loader=runtime.config_loader,
                config=runtime.config,
                adapter=runtime.adapter,
                executor=runtime.executor,
                session_manager=runtime.session_manager,
                session_id=session_id,
                app_logger=loop_logger,
                hooks=hooks,
            )
            self._sync_stats(stats)

            with self._lock:
                elapsed = time.monotonic() - self.start_time
                round_count = self.round_count
                session_count = self.session_count
            self._log(
                f"🏁 執行結束 - 輪次: {round_count}, Session: {session_count}, "
                f"耗時: {core._format_elapsed_time(elapsed)}"
            )
        except Exception as exc:
            self._log(f"❌ 執行異常: {type(exc).__name__}: {exc}")
            if getattr(core.sys, "frozen", False):
                core._desktop_log(f"tui_run_task error: {type(exc).__name__}: {exc}")
        finally:
            with self._lock:
                self.running = False
            self._on_stats()
