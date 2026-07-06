from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_RECORDS_PATH = (
    ROOT / "local_data" / "title_block_arbitration" / "arbitration_records.jsonl"
)
DEFAULT_GROUND_TRUTH_PATHS = [
    ROOT / "local_data" / "ground_truth" / "rotation_ground_truth.json",
    ROOT / "local_data" / "ground_truth" / "rotation_ground_truth_augmented_90.json",
    ROOT
    / "local_data"
    / "ground_truth"
    / "rotation_ground_truth_augmented_90_unclear.json",
]
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "title_block_arbitration" / "evaluation"


@dataclass
class EvaluationRow:
    record_id: str
    sample_id: str
    dataset_name: str
    prediction_dir: str
    decision_status: str
    review_route: str
    predicted_position: str
    expected_position: str
    predicted_rotation_degrees: int | None
    expected_rotation_degrees: int | None
    position_correct: bool
    rotation_correct: bool
    truth_source_level: str
    truth_source_basis: str
    verified_by_human: bool


@dataclass
class MissingTruthRow:
    record_id: str
    sample_id: str
    dataset_name: str
    prediction_dir: str
    decision_status: str
    review_route: str
    predicted_position: str
    predicted_rotation_degrees: int | None


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def load_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    resolved = resolve_path(path)
    records: list[dict[str, Any]] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{resolved}:{line_number}: invalid JSONL") from exc
    return records


def load_ground_truth(paths: list[Path]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    truth: dict[str, dict[str, Any]] = {}
    loaded_paths: list[str] = []
    for path in paths:
        resolved = resolve_path(path)
        if not resolved.exists():
            continue
        loaded_paths.append(as_posix(resolved) or str(resolved))
        for row in load_json(resolved):
            sample = row.get("sample")
            if sample:
                truth[sample] = row
    return truth, loaded_paths


def to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_rows(
    records: list[dict[str, Any]],
    truth_by_sample: dict[str, dict[str, Any]],
) -> tuple[list[EvaluationRow], list[MissingTruthRow]]:
    rows: list[EvaluationRow] = []
    missing: list[MissingTruthRow] = []

    for record in records:
        sample_id = record["sample_id"]
        page = record.get("page") or {}
        arbitration = record.get("arbitration") or {}
        rotation = record.get("rotation") or {}
        routing = record.get("review_routing") or {}

        predicted_position = arbitration.get("title_block_position") or ""
        predicted_rotation = to_int_or_none(rotation.get("detected_rotation_degrees"))
        common = {
            "record_id": record.get("record_id", ""),
            "sample_id": sample_id,
            "dataset_name": page.get("dataset_name", ""),
            "prediction_dir": page.get("prediction_dir", ""),
            "decision_status": arbitration.get("decision_status", ""),
            "review_route": routing.get("route", ""),
            "predicted_position": predicted_position,
            "predicted_rotation_degrees": predicted_rotation,
        }

        truth = truth_by_sample.get(sample_id)
        if not truth:
            missing.append(MissingTruthRow(**common))
            continue

        expected_position = truth.get("title_block_position") or ""
        expected_rotation = to_int_or_none(truth.get("rotation_degrees"))
        rows.append(
            EvaluationRow(
                **common,
                expected_position=expected_position,
                expected_rotation_degrees=expected_rotation,
                position_correct=predicted_position == expected_position,
                rotation_correct=predicted_rotation == expected_rotation,
                truth_source_level=truth.get("source_level", ""),
                truth_source_basis=truth.get("source_basis", ""),
                verified_by_human=bool(truth.get("verified_by_human")),
            )
        )

    return rows, missing


def accuracy(correct: int, total: int) -> float | None:
    if total == 0:
        return None
    return round(correct / total, 6)


def grouped_accuracy(rows: list[EvaluationRow], group_key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[EvaluationRow]] = {}
    for row in rows:
        key = str(getattr(row, group_key))
        groups.setdefault(key, []).append(row)

    summary: dict[str, dict[str, Any]] = {}
    for key, group_rows in sorted(groups.items()):
        total = len(group_rows)
        position_correct = sum(1 for row in group_rows if row.position_correct)
        rotation_correct = sum(1 for row in group_rows if row.rotation_correct)
        summary[key] = {
            "total": total,
            "position_correct": position_correct,
            "position_accuracy": accuracy(position_correct, total),
            "rotation_correct": rotation_correct,
            "rotation_accuracy": accuracy(rotation_correct, total),
        }
    return summary


def summarize(
    rows: list[EvaluationRow],
    missing: list[MissingTruthRow],
    records: list[dict[str, Any]],
    ground_truth_paths: list[str],
) -> dict[str, Any]:
    record_count = len(records)
    rows_with_truth = len(rows)
    position_correct = sum(1 for row in rows if row.position_correct)
    rotation_correct = sum(1 for row in rows if row.rotation_correct)
    unique_samples = sorted({record["sample_id"] for record in records})
    unique_samples_with_truth = sorted({row.sample_id for row in rows})
    unique_position_errors = sorted(
        {row.sample_id for row in rows if not row.position_correct}
    )
    unique_rotation_errors = sorted(
        {row.sample_id for row in rows if not row.rotation_correct}
    )

    decision_counts: Counter[str] = Counter(
        (record.get("arbitration") or {}).get("decision_status", "") for record in records
    )
    route_counts: Counter[str] = Counter(
        (record.get("review_routing") or {}).get("route", "") for record in records
    )
    truth_source_counts: Counter[str] = Counter(row.truth_source_level for row in rows)

    return {
        "record_count": record_count,
        "records_with_truth": rows_with_truth,
        "missing_truth_count": len(missing),
        "position_correct_records": position_correct,
        "position_accuracy": accuracy(position_correct, rows_with_truth),
        "rotation_correct_records": rotation_correct,
        "rotation_accuracy": accuracy(rotation_correct, rows_with_truth),
        "unique_sample_count": len(unique_samples),
        "unique_samples_with_truth": len(unique_samples_with_truth),
        "unique_position_error_count": len(unique_position_errors),
        "unique_rotation_error_count": len(unique_rotation_errors),
        "unique_position_error_samples": unique_position_errors,
        "unique_rotation_error_samples": unique_rotation_errors,
        "decision_status_counts": dict(sorted(decision_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "truth_source_counts": dict(sorted(truth_source_counts.items())),
        "by_decision_status": grouped_accuracy(rows, "decision_status"),
        "by_truth_source_level": grouped_accuracy(rows, "truth_source_level"),
        "scope_note": (
            "This evaluates current arbitration records against existing project ground truth; "
            "it does not prove unknown-drawing industrial generalization accuracy."
        ),
        "dry_run_gate": {
            "ready_for_pdf_dry_run": len(missing) == 0
            and position_correct == rows_with_truth
            and rotation_correct == rows_with_truth,
            "not_ready_for_unattended_batch_write": True,
            "reason": (
                "Evaluation supports the next dry-run stage only; PDF rewriting and file "
                "renaming still require separate dry-run validation."
            ),
        },
        "inputs": {
            "ground_truth_paths": ground_truth_paths,
        },
    }


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[Any], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def build(args: argparse.Namespace) -> dict[str, Any]:
    records = load_jsonl(args.records)
    truth, ground_truth_paths = load_ground_truth(args.ground_truth)
    rows, missing = build_rows(records, truth)
    summary = summarize(rows, missing, records, ground_truth_paths)

    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "accuracy_summary.json"
    details_path = output_dir / "accuracy_details.csv"
    errors_path = output_dir / "accuracy_errors.csv"
    missing_path = output_dir / "accuracy_missing_truth.csv"

    errors = [
        row for row in rows if not row.position_correct or not row.rotation_correct
    ]
    write_json(summary_path, summary)
    write_csv(details_path, rows, list(EvaluationRow.__dataclass_fields__.keys()))
    write_csv(errors_path, errors, list(EvaluationRow.__dataclass_fields__.keys()))
    write_csv(missing_path, missing, list(MissingTruthRow.__dataclass_fields__.keys()))

    return {
        "output_dir": as_posix(output_dir),
        "accuracy_summary": as_posix(summary_path),
        "accuracy_details": as_posix(details_path),
        "accuracy_errors": as_posix(errors_path),
        "accuracy_missing_truth": as_posix(missing_path),
        "summary": summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate title block arbitration records against project ground truth."
    )
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS_PATH)
    parser.add_argument(
        "--ground-truth", nargs="+", type=Path, default=DEFAULT_GROUND_TRUTH_PATHS
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    result = build(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

