from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "outputs" / "rotation-detection" / "comparison" / "manual_results.json"
OUTPUT_DIR = ROOT / "local_data" / "ground_truth"
JSON_OUTPUT = OUTPUT_DIR / "rotation_ground_truth.json"
CSV_OUTPUT = OUTPUT_DIR / "rotation_ground_truth.csv"


@dataclass
class GroundTruthRecord:
    sample: str
    title_block_position: str
    rotation_degrees: int
    source_level: str
    source_basis: str
    verified_by_human: bool
    note: str


def source_level_from_basis(basis: str) -> tuple[str, bool]:
    if basis.startswith("manual_review"):
        return "manual_review", True
    if basis == "opencv_mcp_consensus_accepted":
        return "consensus_accepted", False
    return "unknown", False


def load_candidate_truth(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Candidate truth file does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_records(items: list[dict]) -> list[GroundTruthRecord]:
    records: list[GroundTruthRecord] = []
    for item in sorted(items, key=lambda row: row["sample"]):
        basis = item.get("basis", "")
        source_level, verified_by_human = source_level_from_basis(basis)
        note = (
            "Human-reviewed disagreement or low-confidence sample."
            if verified_by_human
            else "Accepted from OpenCV/MCP consensus; pending full human review."
        )
        records.append(
            GroundTruthRecord(
                sample=item["sample"],
                title_block_position=item["title_block_position"],
                rotation_degrees=int(item["rotation_degrees"]),
                source_level=source_level,
                source_basis=basis,
                verified_by_human=verified_by_human,
                note=note,
            )
        )
    return records


def write_outputs(records: list[GroundTruthRecord]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [asdict(record) for record in records]
    JSON_OUTPUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    with CSV_OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    records = build_records(load_candidate_truth(INPUT_PATH))
    if not records:
        raise SystemExit("No ground truth records generated.")
    write_outputs(records)

    verified_count = sum(1 for record in records if record.verified_by_human)
    print(f"Ground truth records: {len(records)}")
    print(f"Human-reviewed records: {verified_count}")
    print(f"Consensus-accepted records: {len(records) - verified_count}")
    print(f"JSON: {JSON_OUTPUT.relative_to(ROOT)}")
    print(f"CSV: {CSV_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
