#!/usr/bin/env python3
"""Run one real execution round via TUI RunController (non-interactive smoke)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import opencode_infinity as core  # noqa: E402
from tui import services  # noqa: E402
from tui.runtime import RunController  # noqa: E402

WORK = Path(r"C:\Users\Wing\Downloads\cc")
CONFIG = "opencode.yaml"
MAX_WAIT = 300


def main() -> int:
    core.init_config_dir(None)
    config_dir = core.get_tasks_config_dir()
    print(f"Config dir: {config_dir}")
    print(f"Working dir: {WORK}")
    config_path = config_dir / CONFIG
    if not config_path.is_file():
        print(f"ERROR: missing {config_path}")
        return 1

    session_id, _ = services.prepare_start(CONFIG, "", str(WORK))
    print(f"Session: {session_id}")
    print("--- starting RunController (TUI execution path) ---")

    round1_done = False

    def on_log(msg: str) -> None:
        nonlocal round1_done
        print(msg, flush=True)
        if "Round 1" in msg and "完成" in msg:
            round1_done = True

    controller = RunController(on_log=on_log, on_stats=lambda: None)
    controller.start(CONFIG, session_id, working_dir_override=str(WORK))

    start = time.monotonic()
    stop_sent = False
    while time.monotonic() - start < MAX_WAIT:
        snap = controller.snapshot()
        if not snap["running"]:
            print("--- task finished ---")
            break
        if round1_done and not stop_sent:
            print("--- round 1 done, requesting stop ---")
            controller.stop()
            stop_sent = True
        time.sleep(1)
    else:
        print("--- timeout, requesting stop ---")
        controller.stop()
        time.sleep(3)

    snap = controller.snapshot()
    draft = WORK / "output" / "articles" / "draft.md"
    print("--- summary ---")
    print(
        f"running={snap['running']} rounds={snap['round_count']} "
        f"sessions={snap['session_count']}"
    )
    if draft.is_file():
        print(f"draft.md size={draft.stat().st_size} bytes path={draft}")
    else:
        print("draft.md: not found")

    return 0 if snap["round_count"] >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
