#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Sequence

from zfish.cli import register_commands


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Utility commands for zebrafish agglomeration workflows."
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True
    register_commands(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = args.func(args)
    return int(result) if result is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
