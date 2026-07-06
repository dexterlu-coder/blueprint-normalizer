from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ManifestRecord:
    dataset: str
    sample: str
    source_sample: str
    image_path: Path
    label_path: Path | None
    title_block_position: str
    precise_title_block_position: str
    rotation_degrees: int
    suggested_split: str


@dataclass(frozen=True)
class ObbLabel:
    class_id: int
    points: list[tuple[float, float]]
    raw_line: str
    line_number: int


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def load_manifest(path: Path) -> list[ManifestRecord]:
    resolved = resolve_path(path)
    records: list[ManifestRecord] = []
    with resolved.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(
                ManifestRecord(
                    dataset=row["dataset"],
                    sample=row["sample"],
                    source_sample=row.get("source_sample") or row["sample"],
                    image_path=resolve_path(Path(row["image_path"])),
                    label_path=resolve_path(Path(row["label_path"])) if row.get("label_path") else None,
                    title_block_position=row["title_block_position"],
                    precise_title_block_position=row.get("precise_title_block_position", ""),
                    rotation_degrees=int(row["rotation_degrees"]),
                    suggested_split=row.get("suggested_split", ""),
                )
            )
    return records


def label_path_for(record: ManifestRecord, labels_dir: Path) -> Path:
    if record.label_path is not None:
        return record.label_path
    return resolve_path(labels_dir) / f"{record.sample}.txt"


def parse_obb_label_line(line: str, line_number: int) -> ObbLabel:
    parts = line.split()
    if len(parts) != 9:
        raise ValueError(f"line {line_number}: expected 9 fields, got {len(parts)}")

    try:
        class_id = int(parts[0])
    except ValueError as exc:
        raise ValueError(f"line {line_number}: class id is not an integer") from exc

    try:
        coords = [float(value) for value in parts[1:]]
    except ValueError as exc:
        raise ValueError(f"line {line_number}: coordinates must be numeric") from exc

    points = [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
    return ObbLabel(class_id=class_id, points=points, raw_line=line, line_number=line_number)


def load_obb_labels(path: Path) -> list[ObbLabel]:
    labels: list[ObbLabel] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            labels.append(parse_obb_label_line(line, line_number))
    return labels


def polygon_area(points: list[tuple[float, float]]) -> float:
    area = 0.0
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def normalized_to_pixels(points: list[tuple[float, float]], width: int, height: int) -> list[tuple[int, int]]:
    return [
        (
            int(round(max(0.0, min(1.0, x)) * (width - 1))),
            int(round(max(0.0, min(1.0, y)) * (height - 1))),
        )
        for x, y in points
    ]
