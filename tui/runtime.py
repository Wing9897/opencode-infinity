"""Background execution bridge for the TUI."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

import opencode_infinity as core

from tui import i18n
from tui.messages import StatsUpdated


def _should_show_cli_line(line: str) -> bool:
    """Drop opencode internal INFO noise; keep user-visible CLI output."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("timestamp="):
        return False
    return True


def stats_message_from_snapshot(snap: dict[str, Any]) -> StatsUpdated:
    """Build a StatsUpdated message from a RunController snapshot."""
    elapsed = (
        time.monotonic() - snap["start_time"]
        if snap["start_time"] > 0 and snap["running"]
        else 0.0
    )
    return StatsUpdated(
        running=snap["running"],
        round_count=snap["round_count"],
        session_count=snap["session_count"],
        session_id=snap["session_id"],
        config_name=snap["config_name"],
        working_dir=snap["working_dir"],
        elapsed_seconds=elapsed,
    )


class RunController:
    """Manage a single background execution loop."""

    def __init__(
        self,
        on_log: Callable[[str, str], None],
        on_stats: Callable[[], None],
    ) -> None:
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
        self._executor: Optional[core.Executor] = None

    def _log_cli(self, line: str) -> None:
        if _should_show_cli_line(line):
            self._on_log(line, "cli")

    def _log_event(self, message: str) -> None:
        """Errors and stop/finish only — keep console quiet."""
        self._on_log(message, "app")

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
                raise RuntimeError(i18n.t("err_already_running"))
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
        self._on_stats()
        return session_id

    def stop(self) -> None:
        with self._lock:
            stop_event = self._stop_event
            executor = self._executor
        if stop_event:
            stop_event.set()
        if executor is not None:
            try:
                executor.cancel_active()
            except OSError:
                pass

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

    def _run_task(
        self,
        config_name: str,
        session_id: str,
        stop_event: threading.Event,
        working_dir_override: Optional[str],
    ) -> None:
        try:
            try:
                runtime = core._bootstrap_runtime(
                    config_name, working_dir_override=working_dir_override
                )
            except (core.ConfigError, OSError, ValueError) as exc:
                self._log_event(i18n.t("log_config_load_failed", error=exc))
                return
            except core.CLIAdapterError as exc:
                self._log_event(i18n.t("log_cli_adapter_failed", error=exc))
                return

            with self._lock:
                self.working_dir = (
                    str(runtime.working_dir) if runtime.working_dir else ""
                )
                self._executor = runtime.executor

            loop_logger = logging.getLogger("opencode_infinity.tui_loop")

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

            def _on_cli_output(line: str) -> None:
                clean = core._strip_ansi(line)
                if clean.startswith("[stderr] "):
                    clean = clean[9:]
                self._log_cli(clean)

            hooks = core._ExecutionLoopHooks(
                should_stop=stop_event.is_set,
                on_round_begin=_on_round_begin,
                on_round_success=lambda round_num, result: self._on_stats(),
                on_round_failure=lambda round_num, result: self._log_event(
                    core._format_round_failure_message(round_num, result)
                ),
                on_session_switch_failed=lambda message: self._log_event(
                    i18n.t("log_session_switch_failed", message=message)
                ),
                on_max_rounds_reached=lambda max_rounds: self._log_event(
                    i18n.t("log_max_rounds", max_rounds=max_rounds)
                ),
                on_abort=lambda reason: self._log_event(
                    i18n.t("log_aborted", reason=reason)
                ),
                on_reload_failed=self._log_event,
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

            if stop_event.is_set():
                self._log_event(i18n.t("log_stopped"))
        except Exception as exc:
            self._log_event(
                i18n.t("log_error", type=type(exc).__name__, message=exc)
            )
            if getattr(core.sys, "frozen", False):
                core._desktop_log(f"tui_run_task error: {type(exc).__name__}: {exc}")
        finally:
            with self._lock:
                self.running = False
                self._executor = None
            self._on_stats()
