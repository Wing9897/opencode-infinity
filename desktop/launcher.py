#!/usr/bin/env python3
"""Desktop entry point for OpenCode Infinity GUI builds."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    import opencode_infinity

    opencode_infinity._configure_stdio_encoding()

    argv0 = "OpenCode-Infinity-GUI" if getattr(sys, "frozen", False) else "opencode_infinity.py"
    sys.argv = [argv0, "--desktop", *sys.argv[1:]]
    opencode_infinity.main()


if __name__ == "__main__":
    main()
