"""Execution-plan model for the future PDF rotation MVP run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .runtime_config import MvpRunConfig


@dataclass(frozen=True)
class ExecutionStep:
    step_id: str
    title: str
    description: str
    reads_pdf: bool = False
    writes_files: bool = False
    calls_external_command: bool = False
    calls_model_endpoint: bool = False
    touches_review_inbox: bool = False
    enabled_for_dry_run: bool = False

    @property
    def has_side_effects(self) -> bool:
        return (
            self.reads_pdf
            or self.writes_files
            or self.calls_external_command
            or self.calls_model_endpoint
            or self.touches_review_inbox
        )

    def as_report(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "reads_pdf": self.reads_pdf,
            "writes_files": self.writes_files,
            "calls_external_command": self.calls_external_command,
            "calls_model_endpoint": self.calls_model_endpoint,
            "touches_review_inbox": self.touches_review_inbox,
            "enabled_for_dry_run": self.enabled_for_dry_run,
            "has_side_effects": self.has_side_effects,
        }


@dataclass(frozen=True)
class MvpExecutionPlan:
    steps: tuple[ExecutionStep, ...]

    def side_effect_summary(self) -> dict[str, Any]:
        return {
            "step_count": len(self.steps),
            "dry_run_enabled_step_count": sum(1 for step in self.steps if step.enabled_for_dry_run),
            "future_run_reads_pdf": any(step.reads_pdf for step in self.steps),
            "future_run_writes_files": any(step.writes_files for step in self.steps),
            "future_run_calls_external_command": any(step.calls_external_command for step in self.steps),
            "future_run_calls_model_endpoint": any(step.calls_model_endpoint for step in self.steps),
            "future_run_touches_review_inbox": any(step.touches_review_inbox for step in self.steps),
            "side_effect_step_ids": [step.step_id for step in self.steps if step.has_side_effects],
        }

    def as_report(self) -> dict[str, Any]:
        return {
            "purpose": "Describe the future run steps; dry-run does not execute these side-effecting steps.",
            "summary": self.side_effect_summary(),
            "steps": [step.as_report() for step in self.steps],
        }


def build_execution_plan(run_config: MvpRunConfig) -> MvpExecutionPlan:
    paths = {key: setting.as_report() for key, setting in run_config.paths.items()}
    qwen_ready = run_config.qwen.base_url_present and run_config.qwen.api_key_present and bool(run_config.qwen.model)

    return MvpExecutionPlan(
        steps=(
            ExecutionStep(
                step_id="load_config",
                title="Load config",
                description=f"Use {run_config.config_source} config at {run_config.config_path}.",
                enabled_for_dry_run=True,
            ),
            ExecutionStep(
                step_id="collect_input_pdfs",
                title="Collect input PDFs",
                description=f"Plan to enumerate PDFs under {paths['input_dir']['resolved']}.",
            ),
            ExecutionStep(
                step_id="prepare_work_dirs",
                title="Prepare work directories",
                description=(
                    "Plan to prepare output, work, and log directories from configured paths: "
                    f"output={paths['output_dir']['resolved']}, work={paths['work_dir']['resolved']}, "
                    f"log={paths['log_dir']['resolved']}."
                ),
                writes_files=True,
            ),
            ExecutionStep(
                step_id="split_pdf_pages",
                title="Split PDF pages",
                description="Plan to split source PDFs into per-page intermediate PDFs.",
                reads_pdf=True,
                writes_files=True,
            ),
            ExecutionStep(
                step_id="render_pages_with_ghostscript",
                title="Render pages with Ghostscript",
                description="Plan to render per-page PDFs into images for visual model inspection.",
                reads_pdf=True,
                writes_files=True,
                calls_external_command=True,
            ),
            ExecutionStep(
                step_id="request_rotation_vlm",
                title="Request rotation VLM",
                description=f"Plan to call configured Qwen model for rotation decisions; qwen_ready={qwen_ready}.",
                calls_model_endpoint=True,
            ),
            ExecutionStep(
                step_id="correct_or_copy_pdf",
                title="Correct or copy PDF",
                description="Plan to rotate pages when needed or copy already-upright PDFs.",
                reads_pdf=True,
                writes_files=True,
            ),
            ExecutionStep(
                step_id="crop_title_block",
                title="Crop title block",
                description="Plan to crop title-block candidate images from corrected page renders.",
                writes_files=True,
            ),
            ExecutionStep(
                step_id="request_drawing_number_vlm",
                title="Request drawing-number VLM",
                description=f"Plan to call configured Qwen model for drawing-number extraction; qwen_ready={qwen_ready}.",
                calls_model_endpoint=True,
            ),
            ExecutionStep(
                step_id="publish_final_pdfs",
                title="Publish final PDFs",
                description="Plan to publish corrected PDFs using drawing-number based filenames.",
                reads_pdf=True,
                writes_files=True,
            ),
            ExecutionStep(
                step_id="write_reports",
                title="Write reports",
                description="Plan to write machine-readable run reports and human review handoff notes.",
                writes_files=True,
            ),
        )
    )
