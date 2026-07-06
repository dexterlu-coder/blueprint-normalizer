"""Command line entry point for BlueprintNormalizer."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from . import __version__
from .config import check_config
from .paths import APP_CONFIG_FILENAME, example_config_path
from .pdf_rotation_mvp.cli import add_parser as add_pdf_rotation_mvp_parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blueprint-normalizer",
        description="Normalize mechanical drawing PDFs into reviewed, rotated, and named outputs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser("config", help="Inspect local configuration.")
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    check_parser = config_subparsers.add_parser("check", help="Validate a TOML config file.")
    check_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=f"Config path. Defaults to {APP_CONFIG_FILENAME} discovery in later stages.",
    )
    check_parser.set_defaults(func=_cmd_config_check)

    add_pdf_rotation_mvp_parser(subparsers)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


def _cmd_config_check(args: argparse.Namespace) -> int:
    config_path = args.config
    if config_path is None:
        candidate = example_config_path()
        print(f"No config was provided. Template: {candidate}")
        print(f"Create a real {APP_CONFIG_FILENAME} beside the app or pass --config.")
        return 1

    result = check_config(config_path)
    print(f"Config file: {result.path}")
    if result.ok:
        print("Status: OK")
    else:
        print("Status: FAILED")

    for warning in result.warnings:
        print(f"Warning: {warning}")
    for error in result.errors:
        print(f"Error: {error}")

    return 0 if result.ok else 2
