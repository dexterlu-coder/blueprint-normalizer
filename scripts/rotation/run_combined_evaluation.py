from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "outputs" / "rotation-detection" / "combined_evaluation"
SUMMARY_JSON = OUTPUT_DIR / "combined_summary.json"
SUMMARY_CSV = OUTPUT_DIR / "combined_summary.csv"


DATASETS = [
    {
        "name": "manual_full",
        "input_dir": ROOT / "local_data" / "experiment_samples" / "all" / "png",
        "detection_output": ROOT / "outputs" / "rotation-detection" / "stage1",
        "ground_truth": ROOT / "local_data" / "ground_truth" / "rotation_ground_truth.json",
        "evaluation_output": ROOT / "outputs" / "rotation-detection" / "evaluation",
    },
    {
        "name": "augmented_90",
        "input_dir": ROOT / "local_data" / "experiment_samples" / "augmented_90" / "png",
        "detection_output": ROOT / "outputs" / "rotation-detection" / "augmented_90",
        "ground_truth": ROOT / "local_data" / "ground_truth" / "rotation_ground_truth_augmented_90.json",
        "evaluation_output": ROOT / "outputs" / "rotation-detection" / "evaluation_augmented_90",
    },
]


def run_command(args: list[str]) -> None:
    print(" ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def run_dataset(dataset: dict) -> dict:
    run_command(
        [
            sys.executable,
            "-m",
            "scripts.rotation.detect_rotation_stage1",
            "--input-dir",
            str(dataset["input_dir"]),
            "--output-dir",
            str(dataset["detection_output"]),
        ]
    )
    run_command(
        [
            sys.executable,
            "-m",
            "scripts.rotation.evaluate_rotation_results",
            "--results",
            str(dataset["detection_output"] / "results.json"),
            "--ground-truth",
            str(dataset["ground_truth"]),
            "--output-dir",
            str(dataset["evaluation_output"]),
        ]
    )

    summary_path = dataset["evaluation_output"] / "evaluation_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["dataset"] = dataset["name"]
    return summary


def build_combined_summary(dataset_summaries: list[dict]) -> dict:
    total = sum(item["total"] for item in dataset_summaries)
    correct = sum(item["correct"] for item in dataset_summaries)
    errors = sum(item["errors"] for item in dataset_summaries)
    review_required = sum(item["review_required"] for item in dataset_summaries)
    all_confidences = []
    for item in dataset_summaries:
        if item["min_confidence"] is not None:
            all_confidences.append(item["min_confidence"])
        if item["max_confidence"] is not None:
            all_confidences.append(item["max_confidence"])

    return {
        "datasets": dataset_summaries,
        "combined": {
            "total": total,
            "correct": correct,
            "errors": errors,
            "accuracy": round(correct / total, 6) if total else 0.0,
            "review_required": review_required,
            "min_confidence_observed": min(all_confidences) if all_confidences else None,
            "max_confidence_observed": max(all_confidences) if all_confidences else None,
            "error_samples": {
                item["dataset"]: item["error_samples"]
                for item in dataset_summaries
                if item["error_samples"]
            },
            "review_samples": {
                item["dataset"]: item["review_samples"]
                for item in dataset_summaries
                if item["review_samples"]
            },
        },
    }


def write_outputs(summary: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with SUMMARY_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        fieldnames = [
            "dataset",
            "total",
            "correct",
            "errors",
            "accuracy",
            "review_required",
            "min_confidence",
            "max_confidence",
            "average_confidence",
            "error_samples",
            "review_samples",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in summary["datasets"]:
            writer.writerow(
                {
                    "dataset": item["dataset"],
                    "total": item["total"],
                    "correct": item["correct"],
                    "errors": item["errors"],
                    "accuracy": item["accuracy"],
                    "review_required": item["review_required"],
                    "min_confidence": item["min_confidence"],
                    "max_confidence": item["max_confidence"],
                    "average_confidence": item["average_confidence"],
                    "error_samples": ";".join(item["error_samples"]),
                    "review_samples": ";".join(item["review_samples"]),
                }
            )
        combined = summary["combined"]
        writer.writerow(
            {
                "dataset": "combined",
                "total": combined["total"],
                "correct": combined["correct"],
                "errors": combined["errors"],
                "accuracy": combined["accuracy"],
                "review_required": combined["review_required"],
                "min_confidence": combined["min_confidence_observed"],
                "max_confidence": combined["max_confidence_observed"],
                "average_confidence": "",
                "error_samples": json.dumps(combined["error_samples"], ensure_ascii=False),
                "review_samples": json.dumps(combined["review_samples"], ensure_ascii=False),
            }
        )


def main() -> None:
    summaries = [run_dataset(dataset) for dataset in DATASETS]
    combined_summary = build_combined_summary(summaries)
    write_outputs(combined_summary)

    combined = combined_summary["combined"]
    print(f"Combined total: {combined['total']}")
    print(f"Combined correct: {combined['correct']}")
    print(f"Combined errors: {combined['errors']}")
    print(f"Combined accuracy: {combined['accuracy']}")
    print(f"Combined review required: {combined['review_required']}")
    print(f"Summary JSON: {SUMMARY_JSON.relative_to(ROOT)}")
    print(f"Summary CSV: {SUMMARY_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
