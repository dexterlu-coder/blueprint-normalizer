from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, load_obb_labels, resolve_path


ROUND2_DIR = ROOT / "local_data" / "yolo_obb_dataset_round2"
ROUND2_SUMMARY = ROUND2_DIR / "dataset_summary.json"
HARDCASE_MANIFEST = ROOT / "local_data" / "yolo_hardcases" / "round3_retraining_prep" / "hardcase_manifest.json"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "yolo_obb_dataset_round3"
DEFAULT_REVIEW_INBOX = ROOT / "local_data" / "review_inbox" / "current"
REVIEW_DIR_NAME = "round3_overlay_review"

HARDCASE_TRAIN_GROUPS = {
    "part_false_positive_multi_candidate",
    "part_false_positive",
    "boundary_or_size_issue",
}
PROTECTIVE_GROUP = "protective_positive"
NORMAL_POSITIVE_LIMIT = 16


def as_posix(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def rel_path(target: Path, base: Path) -> str:
    return Path(os.path.relpath(target, base)).as_posix()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def current_inbox_is_idle(current_dir: Path) -> bool:
    if not current_dir.exists():
        return True
    entries = [entry for entry in current_dir.iterdir() if entry.name != ".gitkeep"]
    if not entries:
        return True
    if len(entries) != 1 or entries[0].name != "README.md":
        return False
    text = entries[0].read_text(encoding="utf-8", errors="ignore")
    return "当前没有待用户审核、填写或标注的文件" in text


def ensure_review_output(current_dir: Path, review_dir: Path, force: bool) -> None:
    if not current_inbox_is_idle(current_dir) and not force:
        raise RuntimeError(
            f"Current review inbox is not idle: {as_posix(current_dir)}. "
            "Archive it first or rerun with --force."
        )
    if review_dir.exists():
        if not force:
            raise RuntimeError(f"Review directory already exists: {as_posix(review_dir)}")
        resolved_review = review_dir.resolve()
        resolved_current = current_dir.resolve()
        if resolved_review == resolved_current or resolved_current not in resolved_review.parents:
            raise RuntimeError(f"Refusing to remove unexpected path: {resolved_review}")
        shutil.rmtree(resolved_review)


def write_data_yaml(output_dir: Path) -> None:
    text = "\n".join(
        [
            f"path: {output_dir.as_posix()}",
            "train: images/train",
            "val: images/val",
            "test: images/test",
            "names:",
            "  0: title_block",
            "",
        ]
    )
    (output_dir / "data.yaml").write_text(text, encoding="utf-8")


def label_count(path: Path) -> int:
    return len(load_obb_labels(path)) if path.exists() else 0


def source_sample_for(sample: str, round2_by_sample: dict[str, dict[str, Any]]) -> str:
    if sample in round2_by_sample:
        return round2_by_sample[sample].get("source_sample") or sample
    marker = "_from_"
    if marker in sample:
        return sample.split(marker, 1)[1]
    return sample


def hardcase_records(round2_by_sample: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for row in load_json(HARDCASE_MANIFEST):
        sample = row["sample"]
        group = row["group"]
        split = "val" if group == PROTECTIVE_GROUP else "train"
        round2_record = round2_by_sample.get(sample, {})
        records.append(
            {
                "dataset": round2_record.get("dataset", "round2_hardcase"),
                "sample": sample,
                "source_sample": source_sample_for(sample, round2_by_sample),
                "split": split,
                "role": "protective_positive" if group == PROTECTIVE_GROUP else "hardcase_train",
                "hardcase_group": group,
                "title_block_position": round2_record.get("title_block_position", ""),
                "precise_title_block_position": round2_record.get("precise_title_block_position", ""),
                "rotation_degrees": round2_record.get("rotation_degrees", ""),
                "reason": row["source_reason"],
                "negative_note": row.get("negative_note", ""),
                "source_image": resolve_path(Path(row["image_path"])),
                "source_label": resolve_path(Path(row["label_path"])),
            }
        )
    return records


def normal_positive_records(round2_summary: dict[str, Any], excluded_samples: set[str]) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in round2_summary["records"]
        if row["split"] == "train" and row["sample"] not in excluded_samples
    ]

    originals = [row for row in candidates if row["dataset"] == "original"]
    augmented = [row for row in candidates if row["dataset"] == "augmented_90"]
    unclear = [row for row in candidates if row["dataset"] == "augmented_90_unclear"]
    selected = originals + augmented[:10] + unclear[:4]
    selected = selected[:NORMAL_POSITIVE_LIMIT]

    records = []
    for row in selected:
        split = "train"
        sample = row["sample"]
        records.append(
            {
                "dataset": row["dataset"],
                "sample": sample,
                "source_sample": row["source_sample"],
                "split": split,
                "role": "normal_positive",
                "hardcase_group": "",
                "title_block_position": row["title_block_position"],
                "precise_title_block_position": row.get("precise_title_block_position", ""),
                "rotation_degrees": row["rotation_degrees"],
                "reason": "round2 train 普通正例补充",
                "negative_note": "",
                "source_image": ROUND2_DIR / row["image"],
                "source_label": ROUND2_DIR / row["label"],
            }
        )
    return records


def copy_dataset_records(records: list[dict[str, Any]], output_dir: Path) -> list[dict[str, Any]]:
    copied = []
    for row in records:
        image_src = resolve_path(Path(row["source_image"]))
        label_src = resolve_path(Path(row["source_label"]))
        if not image_src.exists():
            raise FileNotFoundError(f"Missing image: {image_src}")
        if not label_src.exists():
            raise FileNotFoundError(f"Missing label: {label_src}")

        split = row["split"]
        image_dst = output_dir / "images" / split / f"{row['sample']}.png"
        label_dst = output_dir / "labels" / split / f"{row['sample']}.txt"
        image_dst.parent.mkdir(parents=True, exist_ok=True)
        label_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image_src, image_dst)
        shutil.copy2(label_src, label_dst)

        copied_row = dict(row)
        copied_row["image"] = image_dst.relative_to(output_dir).as_posix()
        copied_row["label"] = label_dst.relative_to(output_dir).as_posix()
        copied_row["source_image"] = as_posix(image_src)
        copied_row["source_label"] = as_posix(label_src)
        copied_row["title_block_label_count"] = label_count(label_dst)
        copied.append(copied_row)

    for split in ("train", "val", "test"):
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    return copied


def write_manifest(path: Path, records: list[dict[str, Any]], output_dir: Path) -> None:
    fieldnames = [
        "dataset",
        "sample",
        "source_sample",
        "image_path",
        "title_block_position",
        "precise_title_block_position",
        "rotation_degrees",
        "suggested_split",
        "role",
        "hardcase_group",
        "reason",
        "negative_note",
        "label_path",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow(
                {
                    "dataset": row["dataset"],
                    "sample": row["sample"],
                    "source_sample": row["source_sample"],
                    "image_path": as_posix(output_dir / row["image"]),
                    "title_block_position": row["title_block_position"],
                    "precise_title_block_position": row["precise_title_block_position"],
                    "rotation_degrees": row["rotation_degrees"],
                    "suggested_split": row["split"],
                    "role": row["role"],
                    "hardcase_group": row["hardcase_group"],
                    "reason": row["reason"],
                    "negative_note": row["negative_note"],
                    "label_path": as_posix(output_dir / row["label"]),
                }
            )


def by_count(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in records:
        value = str(row.get(key, ""))
        counts[value] = counts.get(value, 0) + 1
    return counts


def source_split_overlap(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    source_splits: dict[str, set[str]] = {}
    for row in records:
        source_splits.setdefault(row["source_sample"], set()).add(row["split"])
    return {
        source: sorted(splits)
        for source, splits in source_splits.items()
        if len(splits) > 1
    }


def summarize(records: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    hardcase_samples = [row["sample"] for row in records if row["role"] != "normal_positive"]
    invalid_labels = [
        {"sample": row["sample"], "title_block_label_count": row["title_block_label_count"]}
        for row in records
        if row["title_block_label_count"] != 1
    ]
    overlap = source_split_overlap(records)
    return {
        "dataset_dir": as_posix(output_dir),
        "strategy": "round3_hardcase_small_dataset_with_protective_positive_val",
        "total_records": len(records),
        "by_split": by_count(records, "split"),
        "by_role": by_count(records, "role"),
        "by_hardcase_group": by_count(records, "hardcase_group"),
        "by_title_block_position": by_count(records, "title_block_position"),
        "hardcase_samples": hardcase_samples,
        "required_hardcase_count": len(load_json(HARDCASE_MANIFEST)),
        "included_hardcase_count": len(hardcase_samples),
        "invalid_labels": invalid_labels,
        "source_split_overlap_count": len(overlap),
        "source_split_overlap": overlap,
        "source_split_overlap_policy": "intentional_protective_overlap_for_val_guardrails",
        "negative_label_policy": "false-positive parts are metadata only; YOLO labels remain true title_block only",
        "quality_gate_passed": not invalid_labels and len(hardcase_samples) == len(load_json(HARDCASE_MANIFEST)),
        "classes": {"0": "title_block"},
        "records": records,
    }


def draw_overlay(image_path: Path, label_path: Path, output_path: Path, caption: str) -> None:
    import cv2
    import numpy as np

    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Image unreadable: {image_path}")
    height, width = image.shape[:2]

    for index, label in enumerate(load_obb_labels(label_path), start=1):
        points = [
            (
                int(round(max(0.0, min(1.0, x)) * (width - 1))),
                int(round(max(0.0, min(1.0, y)) * (height - 1))),
            )
            for x, y in label.points
        ]
        contour = np.array(points, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(image, [contour], isClosed=True, color=(0, 0, 255), thickness=4)
        cv2.circle(image, points[0], 7, (0, 255, 255), -1)
        min_x = min(x for x, _ in points)
        min_y = min(y for _, y in points)
        cv2.putText(
            image,
            f"title_block #{index}",
            (max(8, min_x), max(28, min_y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    cv2.putText(
        image,
        caption,
        (24, height - 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        4,
        cv2.LINE_AA,
    )
    cv2.putText(
        image,
        caption,
        (24, height - 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)


def generate_overlays(records: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    details = []
    for row in records:
        image_path = output_dir / row["image"]
        label_path = output_dir / row["label"]
        overlay_path = overlay_dir / f"{row['sample']}_overlay.png"
        caption = f"{row['sample']} | {row['role']} | {row['title_block_label_count']} label"
        draw_overlay(image_path, label_path, overlay_path, caption)
        row["overlay"] = overlay_path.relative_to(output_dir).as_posix()
        details.append({"sample": row["sample"], "overlay": as_posix(overlay_path)})

    report = {"total": len(records), "overlay_written": len(details), "details": details}
    (overlay_dir / "overlay_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def image_panel(title: str, path: Path, base: Path) -> str:
    src = html.escape(rel_path(path, base))
    return f"""
        <figure>
          <figcaption>{html.escape(title)}</figcaption>
          <a href="{src}" target="_blank" rel="noreferrer"><img src="{src}" alt="{html.escape(title)}" /></a>
        </figure>"""


def publish_review(records: list[dict[str, Any]], output_dir: Path, inbox_dir: Path, force: bool) -> dict[str, Any]:
    review_dir = inbox_dir / REVIEW_DIR_NAME
    ensure_review_output(inbox_dir, review_dir, force)
    review_dir.mkdir(parents=True, exist_ok=True)

    review_records = []
    for row in records:
        sample = row["sample"]
        image_src = output_dir / row["image"]
        overlay_src = output_dir / row["overlay"]
        image_dst = review_dir / "images" / "source" / f"{sample}.png"
        overlay_dst = review_dir / "images" / "overlay" / f"{sample}_overlay.png"
        image_dst.parent.mkdir(parents=True, exist_ok=True)
        overlay_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image_src, image_dst)
        shutil.copy2(overlay_src, overlay_dst)
        review_row = {**row, "review_image": image_dst, "review_overlay": overlay_dst}
        review_records.append(review_row)

    cards = []
    for index, row in enumerate(review_records, start=1):
        role_label = {
            "hardcase_train": "难例训练样本",
            "protective_positive": "保护性正例",
            "normal_positive": "普通正例",
        }.get(row["role"], row["role"])
        cards.append(
            f"""
      <section class="item">
        <div class="meta">
          <strong>{index}. {html.escape(row["sample"])}</strong>
          <span>{html.escape(row["split"])} · {html.escape(role_label)}</span>
        </div>
        <div class="reason">{html.escape(row["reason"])}</div>
        <div class="gallery">
          {image_panel("原图", row["review_image"], review_dir)}
          {image_panel("标题栏标注 overlay", row["review_overlay"], review_dir)}
        </div>
      </section>"""
        )

    (review_dir / "review_index.html").write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>YOLO/OBB round3 overlay 复查</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, "Microsoft YaHei", sans-serif;
      color: #202124;
      background: #f4f6f8;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      padding: 12px 18px;
      background: #fff;
      border-bottom: 1px solid #d8dde3;
    }}
    h1 {{ margin: 0; font-size: 20px; line-height: 1.35; }}
    .hint {{ margin-top: 5px; color: #5f6368; font-size: 14px; }}
    main {{ display: grid; gap: 14px; padding: 14px; }}
    .item {{ background: #fff; border: 1px solid #d8dde3; border-radius: 6px; overflow: hidden; }}
    .meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      border-bottom: 1px solid #edf0f2;
      font-size: 14px;
    }}
    .meta span {{ color: #5f6368; }}
    .reason {{
      padding: 8px 12px;
      color: #3c4043;
      background: #fbfcfe;
      border-bottom: 1px solid #edf0f2;
      font-size: 14px;
    }}
    .gallery {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
      gap: 10px;
      padding: 10px;
    }}
    figure {{ margin: 0; border: 1px solid #e4e7eb; border-radius: 6px; overflow: hidden; background: #fafafa; }}
    figcaption {{ padding: 7px 9px; border-bottom: 1px solid #e4e7eb; color: #5f6368; background: #fff; font-size: 13px; }}
    img {{ display: block; width: 100%; height: min(72vh, 820px); min-height: 420px; object-fit: contain; background: #fafafa; }}
  </style>
</head>
<body>
  <header>
    <h1>YOLO/OBB round3 overlay 复查</h1>
    <div class="hint">请确认红框只框真实标题栏；误检零件不应出现在标注中。</div>
  </header>
  <main>
    {"".join(cards)}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )

    fieldnames = ["序号", "样本编号", "数据集", "角色", "标题栏红框是否正确", "是否需要重画", "备注"]
    with (review_dir / "review_form.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for index, row in enumerate(review_records, start=1):
            writer.writerow(
                {
                    "序号": index,
                    "样本编号": row["sample"],
                    "数据集": row["split"],
                    "角色": row["role"],
                    "标题栏红框是否正确": "",
                    "是否需要重画": "",
                    "备注": "",
                }
            )

    machine = [
        {
            "sample": row["sample"],
            "split": row["split"],
            "role": row["role"],
            "source_image": as_posix(row["review_image"]),
            "overlay": as_posix(row["review_overlay"]),
            "reason": row["reason"],
            "negative_note": row["negative_note"],
        }
        for row in review_records
    ]
    (review_dir / "machine_report.json").write_text(
        json.dumps({"total": len(machine), "records": machine}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (inbox_dir / "README.md").write_text(
        "\n".join(
            [
                "# 当前待审核任务",
                "",
                "任务：YOLO/OBB round3 overlay 复查。",
                "",
                "请打开：",
                "",
                "- `round3_overlay_review/review_index.html`",
                "- `round3_overlay_review/review_form.csv`",
                "",
                "只需要确认红框是否只框真实标题栏；误检零件不应出现在标注中。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "review_dir": as_posix(review_dir),
        "review_index": as_posix(review_dir / "review_index.html"),
        "review_form": as_posix(review_dir / "review_form.csv"),
        "total": len(review_records),
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    inbox_dir = resolve_path(args.review_inbox)
    round2_summary = load_json(ROUND2_SUMMARY)
    round2_by_sample = {row["sample"]: row for row in round2_summary["records"]}

    hard_records = hardcase_records(round2_by_sample)
    normal_records = normal_positive_records(round2_summary, {row["sample"] for row in hard_records})
    records = hard_records + normal_records

    if args.clean:
        clean_dir(output_dir)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    copied = copy_dataset_records(records, output_dir)
    write_data_yaml(output_dir)
    write_manifest(output_dir / "round3_manifest.csv", copied, output_dir)
    overlay_report = generate_overlays(copied, output_dir)
    summary = summarize(copied, output_dir)
    summary["overlay_report"] = overlay_report
    review = publish_review(copied, output_dir, inbox_dir, args.force_review)
    summary["review"] = review
    (output_dir / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build YOLO/OBB round3 hard-case small dataset.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--review-inbox", type=Path, default=DEFAULT_REVIEW_INBOX)
    parser.add_argument("--clean", action="store_true", default=True)
    parser.add_argument("--force-review", action="store_true")
    args = parser.parse_args()

    summary = build(args)
    printable = {key: value for key, value in summary.items() if key != "records"}
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0 if summary["quality_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

