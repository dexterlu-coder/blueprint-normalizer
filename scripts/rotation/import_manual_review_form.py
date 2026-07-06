from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORM_PATH = ROOT / "outputs" / "rotation-detection" / "manual_review" / "review_form.csv"
GROUND_TRUTH_JSON = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth.json"
GROUND_TRUTH_CSV = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth.csv"
BACKUP_JSON = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth.before_manual_import.json"


PRECISE_TO_COARSE = {
    "下方": "bottom",
    "右下方": "bottom",
    "左侧": "left",
    "左方": "left",
    "上方": "top",
    "左上方": "top",
    "右侧": "right",
    "右方": "right",
    "右上方": "right",
    "bottom": "bottom",
    "left": "left",
    "top": "top",
    "right": "right",
}

ROTATION_BY_COARSE = {
    "bottom": 0,
    "left": 90,
    "top": 180,
    "right": 270,
}


def read_form_rows(path: Path) -> list[dict]:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "gbk"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError as error:
            last_error = error
    raise SystemExit(f"Cannot read review form with utf-8-sig or gbk: {last_error}")


def load_ground_truth(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Ground truth file does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_status(value: str) -> str:
    text = value.strip().lower()
    if text in {"正确", "confirmed", "confirm", "ok", "yes", "y"}:
        return "confirmed"
    if text in {"错误", "corrected", "correction", "wrong", "no", "n"}:
        return "corrected"
    return text


def normalize_position(value: str) -> str:
    text = value.strip()
    if text not in PRECISE_TO_COARSE:
        raise SystemExit(f"Unsupported precise title block position: {text!r}")
    return text


def corrected_rotation(row: dict, coarse_position: str) -> int:
    explicit = row.get("正确旋转角度", "").strip()
    if explicit:
        return int(explicit)
    return ROTATION_BY_COARSE[coarse_position]


def update_records(records: list[dict], form_rows: list[dict]) -> list[dict]:
    by_sample = {record["sample"]: record for record in records}
    updated: list[dict] = []

    for row in form_rows:
        sample = row["样本编号"].strip()
        if sample not in by_sample:
            raise SystemExit(f"Review form sample not found in ground truth: {sample}")

        status = normalize_status(row["人工判断"])
        if status not in {"confirmed", "corrected"}:
            raise SystemExit(f"Unsupported review status for {sample}: {row['人工判断']!r}")

        precise_position = normalize_position(row["正确标题栏位置"])
        coarse_position = PRECISE_TO_COARSE[precise_position]
        rotation = corrected_rotation(row, coarse_position)

        record = dict(by_sample[sample])
        if status == "confirmed":
            # The user confirmed the original rotation and coarse position, while
            # adding a more precise title-block location.
            if rotation != int(record["rotation_degrees"]):
                raise SystemExit(
                    f"Confirmed row has conflicting rotation for {sample}: "
                    f"{rotation} != {record['rotation_degrees']}"
                )
        else:
            record["title_block_position"] = coarse_position
            record["rotation_degrees"] = rotation

        record["precise_title_block_position"] = precise_position
        record["source_level"] = "manual_review_full"
        record["source_basis"] = f"review_form_{status}"
        record["verified_by_human"] = True
        note = row.get("备注", "").strip()
        record["note"] = note or "User manually reviewed rotation and precise title-block position."
        updated.append(record)

    missing = sorted(set(by_sample) - {row["样本编号"].strip() for row in form_rows})
    if missing:
        raise SystemExit(f"Ground truth samples missing from review form: {', '.join(missing)}")

    return sorted(updated, key=lambda item: item["sample"])


def write_outputs(records: list[dict]) -> None:
    if GROUND_TRUTH_JSON.exists() and not BACKUP_JSON.exists():
        BACKUP_JSON.write_text(GROUND_TRUTH_JSON.read_text(encoding="utf-8"), encoding="utf-8")

    GROUND_TRUTH_JSON.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    with GROUND_TRUTH_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = [
            "sample",
            "title_block_position",
            "precise_title_block_position",
            "rotation_degrees",
            "source_level",
            "source_basis",
            "verified_by_human",
            "note",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    records = update_records(load_ground_truth(GROUND_TRUTH_JSON), read_form_rows(FORM_PATH))
    write_outputs(records)
    precise_positions = sorted({record["precise_title_block_position"] for record in records})
    print(f"Imported records: {len(records)}")
    print(f"Human verified records: {sum(1 for record in records if record['verified_by_human'])}")
    print(f"Precise positions: {', '.join(precise_positions)}")
    print(f"Ground truth JSON: {GROUND_TRUTH_JSON.relative_to(ROOT)}")
    print(f"Ground truth CSV: {GROUND_TRUTH_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
