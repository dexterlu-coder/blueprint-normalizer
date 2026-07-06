from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from scripts.common.obb_utils import ROOT, label_path_for, load_manifest, load_obb_labels, normalized_to_pixels, resolve_path


DEFAULT_MANIFEST = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "smoke_manifest.csv"
DEFAULT_LABELS_DIR = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "labels"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "overlays"


def draw_text(image: np.ndarray, text: str, origin: tuple[int, int]) -> None:
    cv2.putText(
        image,
        text,
        origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        4,
        cv2.LINE_AA,
    )
    cv2.putText(
        image,
        text,
        origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def visualize(args: argparse.Namespace) -> dict:
    records = load_manifest(resolve_path(args.manifest))
    labels_dir = resolve_path(args.labels_dir)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "total_samples": len(records),
        "overlay_written": 0,
        "missing_images": 0,
        "missing_labels": 0,
        "empty_labels": 0,
        "parse_errors": 0,
    }
    details: list[dict] = []

    for record in records:
        detail = {
            "sample": record.sample,
            "image_path": str(record.image_path),
            "label_path": "",
            "output_path": "",
            "status": "ok",
            "label_count": 0,
            "message": "",
        }

        image = cv2.imread(str(record.image_path))
        if image is None:
            summary["missing_images"] += 1
            detail["status"] = "missing_image"
            detail["message"] = f"Image unreadable: {record.image_path}"
            details.append(detail)
            continue

        label_path = label_path_for(record, labels_dir)
        detail["label_path"] = str(label_path)

        labels = []
        if not label_path.exists():
            summary["missing_labels"] += 1
            detail["status"] = "missing_label"
            detail["message"] = "Label file missing"
        else:
            try:
                labels = load_obb_labels(label_path)
            except ValueError as exc:
                summary["parse_errors"] += 1
                detail["status"] = "parse_error"
                detail["message"] = str(exc)
                labels = []

            if label_path.exists() and not labels and detail["status"] == "ok":
                summary["empty_labels"] += 1
                detail["status"] = "empty_label"
                detail["message"] = "Label file empty"

        height, width = image.shape[:2]
        for index, label in enumerate(labels, start=1):
            points = normalized_to_pixels(label.points, width, height)
            contour = np.array(points, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(image, [contour], isClosed=True, color=(0, 0, 255), thickness=4)
            cv2.circle(image, points[0], 7, (0, 255, 255), -1)
            min_x = min(x for x, _ in points)
            min_y = min(y for _, y in points)
            draw_text(image, f"title_block #{index}", (max(8, min_x), max(28, min_y - 8)))

        if not labels:
            draw_text(image, f"{record.sample}: {detail['status']}", (24, 42))

        draw_text(
            image,
            f"{record.sample} | {record.precise_title_block_position or record.title_block_position} | {record.rotation_degrees}deg",
            (24, height - 24),
        )

        output_path = output_dir / f"{record.sample}_overlay.png"
        cv2.imwrite(str(output_path), image)
        detail["output_path"] = str(output_path)
        detail["label_count"] = len(labels)
        details.append(detail)
        summary["overlay_written"] += 1

    report = {"summary": summary, "details": details}
    (output_dir / "overlay_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Visualize YOLO/OBB labels as image overlays.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    report = visualize(args)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

