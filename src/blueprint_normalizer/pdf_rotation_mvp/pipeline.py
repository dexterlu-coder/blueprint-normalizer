"""Non-networking scaffolding for the PDF rotation MVP pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .execution_plan import build_execution_plan
from .runtime_config import load_mvp_run_config


def no_side_effects() -> dict[str, bool]:
    return {
        "reads_env_file": False,
        "reads_pdf_files": False,
        "calls_model_endpoint": False,
        "calls_ghostscript": False,
        "creates_directories": False,
        "writes_review_inbox_current": False,
    }


def build_dry_run_report(config: str | Path | None = None) -> dict[str, Any]:
    """Build a side-effect-free report for the future MVP run.

    This function intentionally does not create directories, read PDFs, load
    legacy .env files, call Ghostscript, or call the model endpoint.
    """

    run_config = load_mvp_run_config(config)
    execution_plan = build_execution_plan(run_config)

    return {
        "ok": run_config.config_ok,
        "mode": "pdf_rotation_mvp_dry_run",
        "side_effects": no_side_effects(),
        "config": run_config.config_report(),
        "qwen": run_config.qwen.as_report(),
        "paths": run_config.paths_report(),
        "runtime": run_config.runtime.as_report(),
        "execution_plan": execution_plan.as_report(),
        "next_step": "Run command is not enabled in this stage.",
    }


def build_run_disabled_report(config: str | Path | None = None) -> dict[str, Any]:
    """Build the package-level run report without executing side effects."""

    run_config = load_mvp_run_config(config)
    execution_plan = build_execution_plan(run_config)
    blockers = ["run_not_enabled"]
    if not run_config.config_ok:
        blockers.append("config_not_ok")

    return {
        "ok": False,
        "mode": "pdf_rotation_mvp_run_disabled",
        "run_enabled": False,
        "blockers": blockers,
        "side_effects": no_side_effects(),
        "config": run_config.config_report(),
        "qwen": run_config.qwen.as_report(),
        "paths": run_config.paths_report(),
        "runtime": run_config.runtime.as_report(),
        "execution_plan": execution_plan.as_report(),
        "next_step": "Enable side-effecting run stages only after each boundary has tests and rollback coverage.",
    }
