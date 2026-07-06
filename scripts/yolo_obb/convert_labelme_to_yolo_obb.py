from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from scripts.common.obb_utils import ROOT, ManifestRecord, load_manifest, resolve_path


DEFAULT_MANIFEST = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "smoke_manifest.csv"
DEFAULT_LABELME_DIR = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "labelme_json"
DEFAULT_LABELS_DIR = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "labels"


def order_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) != 4:
        raise ValueError(f"expected 4 points, got {len(points)}")

    cx = sum(x for x, _ in points) / 4.0
    cy = sum(y for _, y in points) / 4.0
    return sorted(points, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


def find_json_path(record: ManifestRecord, labelme_dir: Path) -> Path | None:
    search_dirs = [labelme_dir, record.image_path.parent]
    seen: set[Path] = set()

    for directory in search_dirs:
        if directory in seen:
            continue
        seen.add(directory)

        exact = directory / f"{record.sample}.json"
        if exact.exists():
            return exact

        matches = sorted(directory.glob(f"*{record.sample}.json"))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(f"{record.sample}: multiple matching JSON files in {directory}: {matches}")
    return None


def find_labelme_shape(data: dict, sample: str) -> dict:
    matches = [
        shape
        for shape in data.get("shapes", [])
        if shape.get("label") == "title_block"
    ]
    if len(matches) != 1:
        raise ValueError(f"{sample}: expected exactly one title_block shape, got {len(matches)}")
    return matches[0]


def extract_labelme_points(data: dict, sample: str) -> tuple[int, int, list[tuple[float, float]], str]:
    image_width = data.get("imageWidth")
    image_height = data.get("imageHeight")
    if not image_width or not image_height:
        raise ValueError(f"{sample}: missing imageWidth/imageHeight")

    shape = find_labelme_shape(data, sample)
    points = [(float(x), float(y)) for x, y in shape.get("points", [])]
    return int(image_width), int(image_height), points, "labelme"


def extract_isat_points(data: dict, sample: str) -> tuple[int, int, list[tuple[float, float]], str]:
    info = data.get("info", {})
    image_width = info.get("width")
    image_height = info.get("height")
    if not image_width or not image_height:
        raise ValueError(f"{sample}: missing info.width/info.height")

    matches = [
        obj
        for obj in data.get("objects", [])
        if obj.get("category") == "title_block"
    ]
    if len(matches) != 1:
        raise ValueError(f"{sample}: expected exactly one title_block object, got {len(matches)}")

    points = [(float(x), float(y)) for x, y in matches[0].get("segmentation", [])]
    return int(image_width), int(image_height), points, "isat"


def extract_points(data: dict, sample: str) -> tuple[int, int, list[tuple[float, float]], str]:
    if "shapes" in data:
        return extract_labelme_points(data, sample)
    if "objects" in data:
        return extract_isat_points(data, sample)
    raise ValueError(f"{sample}: unsupported JSON format")


def convert_one(json_path: Path, output_path: Path, sample: str) -> dict:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    image_width, image_height, points, source_format = extract_points(data, sample)
    ordered = order_points(points)
    normalized: list[float] = []
    for x, y in ordered:
        normalized.append(max(0.0, min(1.0, x / image_width)))
        normalized.append(max(0.0, min(1.0, y / image_height)))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "0 " + " ".join(f"{value:.8f}" for value in normalized) + "\n",
        encoding="utf-8",
    )
    return {
        "sample": sample,
        "json_path": str(json_path),
        "output_path": str(output_path),
        "points": len(points),
        "source_format": source_format,
        "status": "converted",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert Labelme title_block polygons to YOLO/OBB labels.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--labelme-dir", type=Path, default=DEFAULT_LABELME_DIR)
    parser.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS_DIR)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    records = load_manifest(resolve_path(args.manifest))
    labelme_dir = resolve_path(args.labelme_dir)
    labels_dir = resolve_path(args.labels_dir)
    report: list[dict] = []
    errors: list[str] = []

    for record in records:
        json_path = find_json_path(record, labelme_dir)
        output_path = labels_dir / f"{record.sample}.txt"
        if json_path is None:
            expected = labelme_dir / f"{record.sample}.json"
            message = f"{record.sample}: missing Labelme/ISAT JSON {expected}"
            if args.allow_missing:
                report.append({"sample": record.sample, "status": "missing_json", "json_path": str(expected)})
                continue
            errors.append(message)
            continue
        try:
            report.append(convert_one(json_path, output_path, record.sample))
        except Exception as exc:
            errors.append(str(exc))

    converted_count = sum(1 for item in report if item.get("status") == "converted")
    missing_count = sum(1 for item in report if item.get("status") == "missing_json")
    report_path = labels_dir.parent / "labelme_conversion_report.json"
    report_path.write_text(
        json.dumps({"converted": report, "errors": errors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "converted": converted_count,
                "missing_json": missing_count,
                "errors": len(errors),
                "report": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

