from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_POSTPROCESS_DIR = ROOT / "local_data" / "yolo_postprocess" / "round2_first_train"
DEFAULT_REPORT = DEFAULT_POSTPROCESS_DIR / "postprocess_report.json"
DEFAULT_MANIFEST = DEFAULT_POSTPROCESS_DIR / "failure_case_manifest.json"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_OVERLAY_DIR = (
    ROOT
    / "local_data"
    / "review_inbox"
    / "archive"
    / "round2_overlay_review_20260626_approved"
    / "overlays"
)
REVIEW_DIR_NAME = "yolo_postprocess_failure_review"

ISSUE_LABELS = {
    "multi_candidate": "多候选框",
    "part_false_positive": "疑似零件误检",
    "manual_rejected": "人工判定不可接受",
    "partial_title_block": "标题栏未完整覆盖",
    "out_of_page_bounds": "预测框越界",
    "boundary_too_large": "预测框范围过大",
    "missing_title_block": "缺少标题栏候选",
    "positive_control": "正例对照",
}


def as_posix(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def rel_path(target: Path, base: Path) -> str:
    return Path(os.path.relpath(target, base)).as_posix()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def ensure_safe_output(current_dir: Path, review_dir: Path, force: bool) -> None:
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


def report_records_by_key(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (record["split"], record["sample"]): record
        for record in report.get("records", [])
    }


def issue_summary(reason: str, record: dict[str, Any] | None) -> str:
    issues: list[str] = []
    if record:
        issues.extend(record.get("issue_types", []))
    issues.extend(reason.split(";") if reason else [])
    labels = [ISSUE_LABELS.get(issue, issue) for issue in dict.fromkeys(issues) if issue]
    return "；".join(labels)


def copy_optional(source: Path, target: Path) -> str | None:
    if not source.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return as_posix(target)


def copy_review_assets(
    manifest_record: dict[str, Any],
    review_dir: Path,
    overlay_dir: Path,
) -> dict[str, str | None]:
    split = manifest_record["split"]
    sample = manifest_record["sample"]
    prefix = f"{split}_{sample}"

    prediction_source = resolve_path(Path(manifest_record["prediction_image"]))
    dataset_source = resolve_path(Path(manifest_record["dataset_image"]))
    prediction_label_source = resolve_path(Path(manifest_record["prediction_label"]))
    ground_truth_label_source = resolve_path(Path(manifest_record["ground_truth_label"]))
    overlay_source = overlay_dir / f"{sample}_overlay.png"

    assets = {
        "prediction_image": copy_optional(prediction_source, review_dir / "images" / "prediction" / f"{prefix}.jpg"),
        "dataset_image": copy_optional(dataset_source, review_dir / "images" / "source" / f"{prefix}.png"),
        "label_overlay": copy_optional(overlay_source, review_dir / "images" / "label_overlay" / f"{prefix}.png"),
        "prediction_label": copy_optional(prediction_label_source, review_dir / "labels" / "prediction" / f"{prefix}.txt"),
        "ground_truth_label": copy_optional(
            ground_truth_label_source,
            review_dir / "labels" / "ground_truth" / f"{prefix}.txt",
        ),
    }
    missing = [name for name, copied in assets.items() if copied is None and name.endswith("image")]
    if missing:
        raise FileNotFoundError(f"Missing required image assets for {split}/{sample}: {', '.join(missing)}")
    return assets


def build_records(
    manifest: list[dict[str, Any]],
    report: dict[str, Any],
    review_dir: Path,
    overlay_dir: Path,
) -> list[dict[str, Any]]:
    records_by_key = report_records_by_key(report)
    records: list[dict[str, Any]] = []
    for index, manifest_record in enumerate(manifest, start=1):
        split = manifest_record["split"]
        sample = manifest_record["sample"]
        report_record = records_by_key.get((split, sample))
        assets = copy_review_assets(manifest_record, review_dir, overlay_dir)
        records.append(
            {
                "index": index,
                "split": split,
                "sample": sample,
                "status": manifest_record["status"],
                "group": manifest_record["suggested_review_group"],
                "reason": manifest_record["reason"],
                "issue_summary": issue_summary(manifest_record["reason"], report_record),
                "prediction_count": report_record.get("prediction_count") if report_record else "",
                "manual_acceptance": report_record.get("manual_acceptance") if report_record else "",
                "manual_problem_type": report_record.get("manual_problem_type") if report_record else "",
                "notes": report_record.get("notes") if report_record else "",
                "assets": assets,
                "source_paths": {
                    "prediction_image": manifest_record["prediction_image"],
                    "prediction_label": manifest_record["prediction_label"],
                    "dataset_image": manifest_record["dataset_image"],
                    "ground_truth_label": manifest_record["ground_truth_label"],
                },
                "issue_types": report_record.get("issue_types", []) if report_record else [],
            }
        )
    return records


def image_panel(title: str, path: str | None, html_base: Path) -> str:
    if not path:
        return ""
    absolute = resolve_path(Path(path))
    image_src = html.escape(rel_path(absolute, html_base))
    return f"""
          <figure>
            <figcaption>{html.escape(title)}</figcaption>
            <a href="{image_src}" target="_blank" rel="noreferrer">
              <img src="{image_src}" alt="{html.escape(title)}" />
            </a>
          </figure>"""


def write_html(path: Path, records: list[dict[str, Any]]) -> None:
    cards = []
    for record in records:
        group_label = "失败/需复查" if record["group"] == "failure" else "正例对照"
        panels = [
            image_panel("预测结果", record["assets"]["prediction_image"], path.parent),
            image_panel("数据集原图", record["assets"]["dataset_image"], path.parent),
            image_panel("人工标注参考", record["assets"]["label_overlay"], path.parent),
        ]
        cards.append(
            f"""
      <section class="sheet">
        <div class="meta">
          <div>
            <strong>{record["index"]}. {html.escape(record["split"])} / {html.escape(record["sample"])}</strong>
            <span class="badge">{html.escape(group_label)}</span>
          </div>
          <div class="status">{html.escape(record["status"])} · {html.escape(str(record["prediction_count"]))} 个预测框</div>
        </div>
        <div class="issues">{html.escape(record["issue_summary"])}</div>
        <div class="gallery">
          {"".join(panels)}
        </div>
      </section>"""
        )

    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>YOLO/OBB 后处理失败样本复查</title>
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
    h1 {{
      margin: 0;
      font-size: 20px;
      line-height: 1.35;
    }}
    .hint {{
      margin-top: 5px;
      color: #5f6368;
      font-size: 14px;
    }}
    main {{
      display: grid;
      gap: 14px;
      padding: 14px;
    }}
    .sheet {{
      background: #fff;
      border: 1px solid #d8dde3;
      border-radius: 6px;
      overflow: hidden;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      border-bottom: 1px solid #edf0f2;
      font-size: 14px;
    }}
    .badge {{
      display: inline-block;
      margin-left: 8px;
      padding: 2px 7px;
      border: 1px solid #c8d7ee;
      border-radius: 999px;
      color: #174ea6;
      background: #eef4ff;
      font-size: 12px;
    }}
    .status {{
      color: #5f6368;
    }}
    .issues {{
      padding: 8px 12px;
      color: #3c4043;
      background: #fbfcfe;
      border-bottom: 1px solid #edf0f2;
      font-size: 14px;
    }}
    .gallery {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 10px;
      padding: 10px;
    }}
    figure {{
      margin: 0;
      border: 1px solid #e4e7eb;
      border-radius: 6px;
      overflow: hidden;
      background: #fafafa;
    }}
    figcaption {{
      padding: 7px 9px;
      border-bottom: 1px solid #e4e7eb;
      color: #5f6368;
      background: #fff;
      font-size: 13px;
    }}
    img {{
      display: block;
      width: 100%;
      height: min(72vh, 820px);
      min-height: 420px;
      object-fit: contain;
      background: #fafafa;
    }}
  </style>
</head>
<body>
  <header>
    <h1>YOLO/OBB 后处理失败样本复查</h1>
    <div class="hint">请对照图片填写 review_form.csv；重点判断问题类型、最终候选、是否需要补标或修正原标注。</div>
  </header>
  <main>
    {"".join(cards)}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        "序号",
        "数据集",
        "样本编号",
        "后处理状态",
        "问题类型",
        "问题类型是否正确",
        "最终候选是否可接受",
        "是否需要补标",
        "是否需要修正原标注",
        "备注",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "序号": record["index"],
                    "数据集": record["split"],
                    "样本编号": record["sample"],
                    "后处理状态": record["status"],
                    "问题类型": record["issue_summary"],
                    "问题类型是否正确": "",
                    "最终候选是否可接受": "",
                    "是否需要补标": "",
                    "是否需要修正原标注": "",
                    "备注": "",
                }
            )


def write_readme(path: Path, total: int) -> None:
    path.write_text(
        "\n".join(
            [
                "# 当前待审核任务",
                "",
                "任务：YOLO/OBB 后处理失败样本复查。",
                "",
                "请打开：",
                "",
                "- `yolo_postprocess_failure_review/review_index.html`",
                "- `yolo_postprocess_failure_review/review_form.csv`",
                "",
                f"本轮需要复查 {total} 条样本，其中包含失败样本和正例对照。",
                "",
                "只需要判断问题类型、最终候选、是否需要补标或修正原标注；不需要查看机器报告。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build(args: argparse.Namespace) -> dict[str, Any]:
    report_path = resolve_path(args.report)
    manifest_path = resolve_path(args.manifest)
    output_dir = resolve_path(args.output_dir)
    overlay_dir = resolve_path(args.overlay_dir)
    review_dir = output_dir / REVIEW_DIR_NAME

    ensure_safe_output(output_dir, review_dir, args.force)
    review_dir.mkdir(parents=True, exist_ok=True)

    report = load_json(report_path)
    manifest = load_json(manifest_path)
    records = build_records(manifest, report, review_dir, overlay_dir)

    write_html(review_dir / "review_index.html", records)
    write_csv(review_dir / "review_form.csv", records)
    machine_report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "report": as_posix(report_path),
        "manifest": as_posix(manifest_path),
        "review_dir": as_posix(review_dir),
        "total": len(records),
        "records": records,
    }
    write_json(review_dir / "machine_report.json", machine_report)
    write_readme(output_dir / "README.md", len(records))

    return {
        "review_dir": as_posix(review_dir),
        "review_index": as_posix(review_dir / "review_index.html"),
        "review_form": as_posix(review_dir / "review_form.csv"),
        "machine_report": as_posix(review_dir / "machine_report.json"),
        "total": len(records),
        "failure": sum(1 for record in records if record["group"] == "failure"),
        "positive_control": sum(1 for record in records if record["group"] == "positive_control"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build YOLO postprocess failure review pack.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--overlay-dir", type=Path, default=DEFAULT_OVERLAY_DIR)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

