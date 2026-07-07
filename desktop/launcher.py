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

    try:
        positional, options = opencode_infinity._parse_launch_options(sys.argv[1:])
    except opencode_infinity.ConfigError as exc:
        opencode_infinity._show_fatal_error("OpenCode Infinity", str(exc))
        raise SystemExit(1) from exc

    if positional:
        opencode_infinity._show_fatal_error(
            "OpenCode Infinity",
            f"Unexpected arguments: {' '.join(positional)}",
        )
        raise SystemExit(1)

    opencode_infinity.init_config_dir(options.config_dir)
    port = options.port if options.port_explicit else opencode_infinity.DEFAULT_DESKTOP_PORT
    opencode_infinity._start_desktop(port=port)


if __name__ == "__main__":
    main()
