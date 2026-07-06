"""CLI wiring for the PDF rotation MVP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import build_dry_run_report


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "pdf-rotation-mvp",
        help="Inspect and run the PDF rotation and drawing-number MVP.",
    )
    command_subparsers = parser.add_subparsers(dest="pdf_rotation_mvp_command")

    dry_run_parser = command_subparsers.add_parser(
        "dry-run",
        help="Check configuration and path semantics without reading PDFs or calling models.",
    )
    dry_run_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Config path. Defaults to blueprint-normalizer.toml discovery candidates.",
    )
    dry_run_parser.set_defaults(func=_cmd_dry_run)
    return parser


def _cmd_dry_run(args: argparse.Namespace) -> int:
    report = build_dry_run_report(args.config)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2

