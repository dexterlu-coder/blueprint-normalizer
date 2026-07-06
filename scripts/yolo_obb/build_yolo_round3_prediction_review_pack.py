from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


PREDICTIONS_DIR = ROOT / "local_data" / "yolo_predictions"
ROUND3_SUMMARY = ROOT / "local_data" / "yolo_obb_dataset_round3" / "dataset_summary.json"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "review_inbox" / "current"
REVIEW_DIR_NAME = "round3_prediction_review"

PREDICTION_GROUPS = [
    {
        "group": "round3_hardcase_train",
        "prediction_dir": "round3_train",
        "samples": "hardcase_train",
        "reason": "round3 hard-case 训练样本回归",
    },
    {
        "group": "round3_protective_val",
        "prediction_dir": "round3_val",
        "samples": "all",
        "reason": "round3 保护性正例验证",
    },
    {
        "group": "round2_test_regression",
        "prediction_dir": "round3_round2_test",
        "samples": "all",
        "reason": "round2 test 回归检查",
    },
    {
        "group": "round2_val_regression",
        "prediction_dir": "round3_round2_val",
        "samples": "all",
        "reason": "round2 val 回归检查",
    },
]


def as_posix(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def rel_path(target: Path, base: Path) -> str:
    return Path(os.path.relpath(target, base)).as_posix()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def prediction_count(label_path: Path) -> int:
    if not label_path.exists():
        return 0
    with label_path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


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


def hardcase_train_samples() -> set[str]:
    summary = load_json(ROUND3_SUMMARY)
    return {
        row["sample"]
        for row in summary.get("records", [])
        if row.get("role") == "hardcase_train"
    }


def collect_records(predictions_dir: Path) -> list[dict[str, Any]]:
    hardcase_samples = hardcase_train_samples()
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for spec in PREDICTION_GROUPS:
        pred_dir = predictions_dir / spec["prediction_dir"]
        label_dir = pred_dir / "labels"
        if not pred_dir.exists():
            raise FileNotFoundError(f"Missing prediction directory: {as_posix(pred_dir)}")

        for image_path in sorted(pred_dir.glob("*.jpg")):
            sample = image_path.stem
            if spec["samples"] == "hardcase_train" and sample not in hardcase_samples:
                continue
            key = (spec["group"], sample)
            if key in seen:
                continue
            seen.add(key)
            label_path = label_dir / f"{sample}.txt"
            count = prediction_count(label_path)
            records.append(
                {
                    "group": spec["group"],
                    "prediction_dir": spec["prediction_dir"],
                    "sample": sample,
                    "source_image": image_path,
                    "source_label": label_path,
                    "prediction_count": count,
                    "needs_attention": count != 1,
                    "reason": spec["reason"],
                }
            )

    records.sort(key=lambda row: (not row["needs_attention"], row["group"], row["sample"]))
    return records


def copy_assets(records: list[dict[str, Any]], review_dir: Path) -> list[dict[str, Any]]:
    copied = []
    for record in records:
        row = dict(record)
        prefix = f"{record['group']}_{record['sample']}"
        image_dst = review_dir / "images" / f"{prefix}.jpg"
        label_dst = review_dir / "labels" / f"{prefix}.txt"
        image_dst.parent.mkdir(parents=True, exist_ok=True)
        label_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(record["source_image"], image_dst)
        if record["source_label"].exists():
            shutil.copy2(record["source_label"], label_dst)
            row["review_label"] = label_dst
        else:
            row["review_label"] = ""
        row["review_image"] = image_dst
        copied.append(row)
    return copied


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        "序号",
        "复查组",
        "样本编号",
        "预测框数量",
        "预测框是否可接受",
        "问题类型",
        "备注",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for index, record in enumerate(records, start=1):
            writer.writerow(
                {
                    "序号": index,
                    "复查组": record["group"],
                    "样本编号": record["sample"],
                    "预测框数量": record["prediction_count"],
                    "预测框是否可接受": "",
                    "问题类型": "",
                    "备注": "",
                }
            )


def write_html(path: Path, records: list[dict[str, Any]]) -> None:
    cards = []
    for index, record in enumerate(records, start=1):
        image_src = html.escape(rel_path(record["review_image"], path.parent))
        attention = "需重点看" if record["needs_attention"] else "常规复查"
        cards.append(
            f"""
      <section class="sheet">
        <div class="meta">
          <div>
            <strong>{index}. {html.escape(record["group"])} / {html.escape(record["sample"])}</strong>
            <span class="badge">{html.escape(attention)}</span>
          </div>
          <span>{record["prediction_count"]} 个预测框</span>
          <a href="{image_src}" target="_blank" rel="noreferrer">打开大图</a>
        </div>
        <div class="reason">{html.escape(record["reason"])}</div>
        <img src="{image_src}" alt="{html.escape(record["sample"])}" />
      </section>"""
        )

    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>YOLO/OBB round3 预测复查</title>
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
    main {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(700px, 1fr));
      gap: 14px;
      padding: 14px;
    }}
    .sheet {{ background: #fff; border: 1px solid #d8dde3; border-radius: 6px; overflow: hidden; }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      border-bottom: 1px solid #edf0f2;
      font-size: 14px;
    }}
    .meta a {{ color: #1a73e8; text-decoration: none; }}
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
    .reason {{
      padding: 8px 12px;
      color: #3c4043;
      background: #fbfcfe;
      border-bottom: 1px solid #edf0f2;
      font-size: 14px;
    }}
    img {{
      display: block;
      width: 100%;
      height: min(82vh, 920px);
      min-height: 620px;
      object-fit: contain;
      background: #fafafa;
    }}
  </style>
</head>
<body>
  <header>
    <h1>YOLO/OBB round3 预测复查</h1>
    <div class="hint">重点确认预测框是否只框真实标题栏；多框样本排在最前。</div>
  </header>
  <main>
    {"".join(cards)}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_readme(path: Path, total: int, attention_count: int) -> None:
    path.write_text(
        "\n".join(
            [
                "# 当前待审核任务",
                "",
                "任务：YOLO/OBB round3 预测结果复查。",
                "",
                "请打开：",
                "",
                "- `round3_prediction_review/review_index.html`",
                "- `round3_prediction_review/review_form.csv`",
                "",
                f"本轮需要复查 {total} 张预测图，其中 {attention_count} 张预测框数量不是 1，已排在前面。",
                "",
                "只需要判断预测框是否可接受；误检零件、漏框、多框或框过大都请写到问题类型/备注。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build(args: argparse.Namespace) -> dict[str, Any]:
    predictions_dir = resolve_path(args.predictions_dir)
    output_dir = resolve_path(args.output_dir)
    review_dir = output_dir / REVIEW_DIR_NAME
    ensure_safe_output(output_dir, review_dir, args.force)
    review_dir.mkdir(parents=True, exist_ok=True)

    records = collect_records(predictions_dir)
    records = copy_assets(records, review_dir)
    write_html(review_dir / "review_index.html", records)
    write_csv(review_dir / "review_form.csv", records)
    machine_report = {
        "total": len(records),
        "attention_count": sum(1 for row in records if row["needs_attention"]),
        "records": [
            {
                "group": row["group"],
                "sample": row["sample"],
                "prediction_count": row["prediction_count"],
                "needs_attention": row["needs_attention"],
                "source_image": as_posix(row["source_image"]),
                "source_label": as_posix(row["source_label"]),
                "review_image": as_posix(row["review_image"]),
                "review_label": as_posix(row["review_label"]) if row["review_label"] else "",
                "reason": row["reason"],
            }
            for row in records
        ],
    }
    (review_dir / "machine_report.json").write_text(
        json.dumps(machine_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_readme(output_dir / "README.md", len(records), machine_report["attention_count"])
    return {
        "review_dir": as_posix(review_dir),
        "review_index": as_posix(review_dir / "review_index.html"),
        "review_form": as_posix(review_dir / "review_form.csv"),
        "machine_report": as_posix(review_dir / "machine_report.json"),
        "total": len(records),
        "attention_count": machine_report["attention_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build YOLO/OBB round3 prediction review pack.")
    parser.add_argument("--predictions-dir", type=Path, default=PREDICTIONS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

