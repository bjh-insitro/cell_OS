#!/usr/bin/env python3
"""Backward-compatible wrapper for the packaged CLI entry point."""

from cell_os.cli.run_campaign import main

if __name__ == "__main__":
    raise SystemExit(main())
