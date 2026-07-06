from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = ROOT / "outputs" / "rotation-detection" / "stage1" / "results.json"
GROUND_TRUTH_PATH = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth.json"
OUTPUT_DIR = ROOT / "outputs" / "rotation-detection" / "evaluation"
SUMMARY_OUTPUT = OUTPUT_DIR / "evaluation_summary.json"
DETAILS_OUTPUT = OUTPUT_DIR / "evaluation_details.csv"
ERRORS_OUTPUT = OUTPUT_DIR / "errors.csv"
REVIEW_OUTPUT = OUTPUT_DIR / "review_required.csv"


@dataclass
class EvaluationRow:
    sample: str
    file: str
    expected_position: str
    expected_rotation_degrees: int
    predicted_position: str
    predicted_rotation_degrees: int
    confidence: float
    needs_review: bool
    source_level: str
    source_basis: str
    verified_by_human: bool
    correct: bool


def sample_from_file(filename: str) -> str:
    stem = Path(filename).stem
    if stem.startswith("aug90_"):
        return stem
    match = re.search(r"sample_(\d+)", filename)
    if not match:
        raise ValueError(f"Cannot parse sample id from filename: {filename}")
    return f"sample_{match.group(1)}"


def load_json(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Required file does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate rotation detection results.")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    if not args.results.is_absolute():
        args.results = ROOT / args.results
    if not args.ground_truth.is_absolute():
        args.ground_truth = ROOT / args.ground_truth
    if not args.output_dir.is_absolute():
        args.output_dir = ROOT / args.output_dir
    return args


def build_rows(results: list[dict], truth: list[dict]) -> list[EvaluationRow]:
    truth_by_sample = {row["sample"]: row for row in truth}
    rows: list[EvaluationRow] = []

    for result in sorted(results, key=lambda row: row["file"]):
        sample = sample_from_file(result["file"])
        if sample not in truth_by_sample:
            raise SystemExit(f"No ground truth found for {sample}")
        expected = truth_by_sample[sample]
        predicted_rotation = int(result["clockwise_rotation_degrees"])
        expected_rotation = int(expected["rotation_degrees"])
        rows.append(
            EvaluationRow(
                sample=sample,
                file=result["file"],
                expected_position=expected["title_block_position"],
                expected_rotation_degrees=expected_rotation,
                predicted_position=result["title_block_side"],
                predicted_rotation_degrees=predicted_rotation,
                confidence=float(result["confidence"]),
                needs_review=bool(result["needs_review"]),
                source_level=expected["source_level"],
                source_basis=expected["source_basis"],
                verified_by_human=bool(expected["verified_by_human"]),
                correct=predicted_rotation == expected_rotation,
            )
        )
    return rows


def summarize(rows: list[EvaluationRow]) -> dict:
    total = len(rows)
    correct = sum(1 for row in rows if row.correct)
    errors = total - correct
    review_required = sum(1 for row in rows if row.needs_review)
    human_verified = sum(1 for row in rows if row.verified_by_human)
    consensus_accepted = total - human_verified
    confidences = [row.confidence for row in rows]
    return {
        "total": total,
        "correct": correct,
        "errors": errors,
        "accuracy": round(correct / total, 6) if total else 0.0,
        "review_required": review_required,
        "human_verified_ground_truth": human_verified,
        "consensus_accepted_ground_truth": consensus_accepted,
        "min_confidence": min(confidences) if confidences else None,
        "max_confidence": max(confidences) if confidences else None,
        "average_confidence": round(sum(confidences) / total, 6) if total else None,
        "error_samples": [row.sample for row in rows if not row.correct],
        "review_samples": [row.sample for row in rows if row.needs_review],
    }


def write_csv(path: Path, rows: list[EvaluationRow]) -> None:
    fieldnames = list(EvaluationRow.__dataclass_fields__.keys())
    dict_rows = [asdict(row) for row in rows]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dict_rows)


def write_outputs(rows: list[EvaluationRow], summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evaluation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(output_dir / "evaluation_details.csv", rows)
    write_csv(output_dir / "errors.csv", [row for row in rows if not row.correct])
    write_csv(output_dir / "review_required.csv", [row for row in rows if row.needs_review])


def main() -> None:
    args = parse_args()
    rows = build_rows(load_json(args.results), load_json(args.ground_truth))
    if not rows:
        raise SystemExit("No evaluation rows generated.")
    summary = summarize(rows)
    write_outputs(rows, summary, args.output_dir)

    print(f"Total: {summary['total']}")
    print(f"Correct: {summary['correct']}")
    print(f"Errors: {summary['errors']}")
    print(f"Accuracy: {summary['accuracy']}")
    print(f"Review required: {summary['review_required']}")
    print(f"Min confidence: {summary['min_confidence']}")
    print(f"Max confidence: {summary['max_confidence']}")


if __name__ == "__main__":
    main()
