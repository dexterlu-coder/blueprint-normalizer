from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

ORIGINAL_GT = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth.json"
AUGMENTED_GT = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth_augmented_90.json"
UNCLEAR_AUGMENTED_GT = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth_augmented_90_unclear.json"
ORIGINAL_IMAGES = ROOT / "local_data" / "experiment_samples" / "all" / "png"
AUGMENTED_IMAGES = ROOT / "local_data" / "experiment_samples" / "augmented_90" / "png"
UNCLEAR_AUGMENTED_IMAGES = ROOT / "local_data" / "experiment_samples" / "augmented_90_unclear" / "png"
SMOKE_REVIEW_FORM = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "overlay_review" / "review_form.csv"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "review_inbox" / "current"

BASE_HARD_ORIGINALS = {
    "sample_001": "用户复查指出不好判断，需要补充人工参考",
    "sample_009": "历史误判样本，右侧标题栏容易受相似表格干扰",
    "sample_010": "标题栏在下方，是少数 0 度样本",
    "sample_020": "上方标题栏样本，用于补充 180 度参考",
    "sample_030": "上方标题栏样本，用于补充 180 度参考",
    "sample_040": "右上方标题栏样本，用于补充侧边标题栏参考",
    "sample_042": "历史低置信样本，线条和候选边界不够清晰",
    "sample_060": "上方标题栏样本，用于补充长图难例参考",
}


def load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_image(image_dir: Path, sample: str) -> Path:
    matches = sorted(image_dir.glob(f"*{sample}.png"))
    if not matches:
        raise FileNotFoundError(f"No PNG found for {sample} in {image_dir}")
    if len(matches) > 1:
        raise ValueError(f"Multiple PNG files found for {sample}: {matches}")
    return matches[0]


def read_user_flagged_samples(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    flagged: dict[str, str] = {}
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                for row in csv.DictReader(f):
                    sample = (row.get("样本编号") or "").strip()
                    verdict = (row.get("红框是否正确") or "").strip()
                    note = (row.get("备注") or "").strip()
                    if sample and verdict and verdict != "正确":
                        flagged[sample] = note or "用户复查标记为需要重新确认"
            return flagged
        except UnicodeDecodeError as exc:
            last_error = exc
            flagged.clear()

    if last_error:
        raise last_error
    return flagged


def original_records() -> dict[str, dict]:
    records = {}
    for record in load_json(ORIGINAL_GT):
        sample = record["sample"]
        records[sample] = {
            "dataset": "original",
            "sample": sample,
            "source_sample": sample,
            "image_path": find_image(ORIGINAL_IMAGES, sample),
            "reference_image_path": "",
            "title_block_position": record["title_block_position"],
            "precise_title_block_position": record.get("precise_title_block_position", ""),
            "rotation_degrees": record["rotation_degrees"],
        }
    return records


def augmented_records(originals: dict[str, dict]) -> list[dict]:
    records = []
    augmented_sources = [
        (AUGMENTED_GT, AUGMENTED_IMAGES, "augmented_90", "顺时针 90 度补强样本，标题栏位于左侧"),
    ]
    if UNCLEAR_AUGMENTED_GT.exists():
        augmented_sources.append(
            (
                UNCLEAR_AUGMENTED_GT,
                UNCLEAR_AUGMENTED_IMAGES,
                "augmented_90_unclear",
                "不清晰顺时针 90 度补强样本，标题栏位于左侧",
            )
        )

    for gt_path, image_dir, dataset, reason in augmented_sources:
        for record in load_json(gt_path):
            sample = record["sample"]
            source_sample = record["source_sample"]
            source = originals[source_sample]
            records.append(
                {
                    "dataset": dataset,
                    "sample": sample,
                    "source_sample": source_sample,
                    "image_path": find_image(image_dir, sample),
                    "reference_image_path": source["image_path"],
                    "title_block_position": record["title_block_position"],
                    "precise_title_block_position": record.get("precise_title_block_position", ""),
                    "rotation_degrees": record["rotation_degrees"],
                    "reason": reason,
                }
            )
    return records


def rel_path(target: Path, base: Path) -> str:
    return Path(os.path.relpath(target, base)).as_posix()


def inbox_image_name(record: dict) -> str:
    return f"{record['sample']}{Path(record['image_path']).suffix.lower()}"


def reference_image_name(record: dict) -> str:
    return f"{record['source_sample']}_reference{Path(record['reference_image_path']).suffix.lower()}"


def build_records() -> list[dict]:
    originals = original_records()
    flagged = read_user_flagged_samples(SMOKE_REVIEW_FORM)

    hard_originals = dict(BASE_HARD_ORIGINALS)
    for sample, note in flagged.items():
        hard_originals[sample] = f"用户复查标记：{note}"

    records: list[dict] = []

    for record in augmented_records(originals):
        records.append(record)

    for sample, reason in sorted(hard_originals.items()):
        if sample not in originals:
            continue
        record = dict(originals[sample])
        record["reason"] = reason
        records.append(record)

    records.sort(key=lambda r: (r["dataset"] != "augmented_90", r["sample"]))
    return records


def write_manifest_csv(path: Path, records: list[dict]) -> None:
    fieldnames = [
        "dataset",
        "sample",
        "source_sample",
        "image_path",
        "reference_image_path",
        "source_image_path",
        "source_reference_image_path",
        "title_block_position",
        "precise_title_block_position",
        "rotation_degrees",
        "reason",
        "label_class",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = {
                "dataset": record["dataset"],
                "sample": record["sample"],
                "source_sample": record["source_sample"],
                "image_path": str(record["inbox_image_path"].relative_to(ROOT)),
                "reference_image_path": (
                    str(record["inbox_reference_image_path"].relative_to(ROOT))
                    if record["inbox_reference_image_path"]
                    else ""
                ),
                "source_image_path": str(record["image_path"].relative_to(ROOT)),
                "source_reference_image_path": (
                    str(Path(record["reference_image_path"]).relative_to(ROOT))
                    if record["reference_image_path"]
                    else ""
                ),
                "title_block_position": record["title_block_position"],
                "precise_title_block_position": record["precise_title_block_position"],
                "rotation_degrees": record["rotation_degrees"],
                "reason": record["reason"],
                "label_class": "title_block",
            }
            writer.writerow(row)


def write_reference_form(path: Path, records: list[dict]) -> None:
    fieldnames = ["序号", "样本编号", "是否完成标注", "标题栏边界参考", "难点说明", "备注"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for index, record in enumerate(records, start=1):
            writer.writerow(
                {
                    "序号": index,
                    "样本编号": record["sample"],
                    "是否完成标注": "",
                    "标题栏边界参考": "",
                    "难点说明": "",
                    "备注": "",
                }
            )


def publish_images(output_dir: Path, records: list[dict]) -> list[dict]:
    to_label_dir = output_dir / "to_label"
    references_dir = output_dir / "references"
    to_label_dir.mkdir(parents=True, exist_ok=True)
    references_dir.mkdir(parents=True, exist_ok=True)

    published: list[dict] = []
    for record in records:
        row = dict(record)
        label_dst = to_label_dir / inbox_image_name(record)
        shutil.copy2(record["image_path"], label_dst)
        row["inbox_image_path"] = label_dst

        if record["reference_image_path"]:
            reference_dst = references_dir / reference_image_name(record)
            shutil.copy2(record["reference_image_path"], reference_dst)
            row["inbox_reference_image_path"] = reference_dst
        else:
            row["inbox_reference_image_path"] = ""
        published.append(row)
    return published


def write_html(path: Path, records: list[dict]) -> None:
    cards = []
    for index, record in enumerate(records, start=1):
        image_src = html.escape(rel_path(record["inbox_image_path"], path.parent))
        reference = ""
        if record["inbox_reference_image_path"]:
            reference_src = html.escape(rel_path(record["inbox_reference_image_path"], path.parent))
            reference = f"""
        <div class="reference">
          <div class="caption">原图参考</div>
          <img src="{reference_src}" alt="{html.escape(record["source_sample"])} 原图参考" />
        </div>"""

        cards.append(
            f"""
      <section class="item">
        <div class="meta">
          <strong>{index}. {html.escape(record["sample"])}</strong>
          <span>{html.escape(record["reason"])}</span>
        </div>
        <div class="images">
          <div>
            <div class="caption">需要标注</div>
            <img src="{image_src}" alt="{html.escape(record["sample"])}" />
          </div>
          {reference}
        </div>
      </section>"""
        )

    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>YOLO/OBB 第二轮 90 度与难例参考包</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, "Microsoft YaHei", sans-serif;
      color: #202124;
      background: #f3f5f7;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      padding: 12px 18px;
      background: #ffffff;
      border-bottom: 1px solid #d8dde3;
    }}
    h1 {{
      margin: 0;
      font-size: 20px;
      line-height: 1.3;
    }}
    .hint {{
      margin-top: 4px;
      color: #5f6368;
      font-size: 14px;
    }}
    main {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(720px, 1fr));
      gap: 14px;
      padding: 14px;
    }}
    .item {{
      background: #ffffff;
      border: 1px solid #d8dde3;
      border-radius: 6px;
      overflow: hidden;
    }}
    .meta {{
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 10px 12px;
      border-bottom: 1px solid #edf0f2;
      font-size: 14px;
    }}
    .meta span {{
      color: #5f6368;
    }}
    .images {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      padding: 10px;
    }}
    .reference:empty {{
      display: none;
    }}
    .caption {{
      margin-bottom: 6px;
      font-size: 13px;
      color: #5f6368;
    }}
    img {{
      display: block;
      width: 100%;
      height: min(78vh, 820px);
      min-height: 520px;
      object-fit: contain;
      background: #fafafa;
      border: 1px solid #edf0f2;
    }}
    @media (max-width: 980px) {{
      main {{
        grid-template-columns: 1fr;
      }}
      .images {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>YOLO/OBB 第二轮 90 度与难例参考包</h1>
    <div class="hint">优先标注“需要标注”图片；如边界不好判断，请在 reference_form.csv 中写详细参考。</div>
  </header>
  <main>
    {"".join(cards)}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def summarize(records: list[dict]) -> dict:
    by_dataset: dict[str, int] = {}
    by_position: dict[str, int] = {}
    for record in records:
        by_dataset[record["dataset"]] = by_dataset.get(record["dataset"], 0) + 1
        by_position[record["title_block_position"]] = by_position.get(record["title_block_position"], 0) + 1
    return {
        "total": len(records),
        "by_dataset": by_dataset,
        "by_title_block_position": by_position,
    }


def build(output_dir: Path) -> dict:
    records = build_records()
    output_dir.mkdir(parents=True, exist_ok=True)
    published_records = publish_images(output_dir, records)

    manifest_records = []
    for record in published_records:
        row = dict(record)
        row["source_image_path"] = str(record["image_path"].relative_to(ROOT))
        row["image_path"] = str(record["inbox_image_path"].relative_to(ROOT))
        if record["reference_image_path"]:
            row["source_reference_image_path"] = str(Path(record["reference_image_path"]).relative_to(ROOT))
        if record["inbox_reference_image_path"]:
            row["reference_image_path"] = str(record["inbox_reference_image_path"].relative_to(ROOT))
        row.pop("inbox_image_path", None)
        row.pop("inbox_reference_image_path", None)
        manifest_records.append(row)

    write_manifest_csv(output_dir / "round2_manifest.csv", published_records)
    (output_dir / "round2_manifest.json").write_text(
        json.dumps(manifest_records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    reference_form_status = "written"
    try:
        write_reference_form(output_dir / "reference_form.csv", published_records)
    except PermissionError:
        reference_form_status = "locked_existing_kept"
    write_html(output_dir / "review_index.html", published_records)
    (output_dir / "README.md").write_text(
        """# 当前待审核内容

本目录是固定审核入口。你每次只需要来这里找当前任务。

本轮请使用：

- `review_index.html`：查看需要标注/参考的图片。
- `to_label/`：用 ISAT 打开并标注这里面的图片。
- `references/`：需要对照时查看这里面的原图参考。
- `reference_form.csv`：填写标注完成情况、标题栏边界参考、难点说明和备注。

其他文件是机器清单或摘要，通常不需要打开。
""",
        encoding="utf-8",
    )
    (output_dir / "round2_task.md").write_text(
        """# 第二轮 90 度补强与难例参考标注

请优先标注 `review_index.html` 中每个样本的“需要标注”图片。

ISAT 标注图片统一放在：

```text
to_label/
```

要求：

- 类别仍然只使用 `title_block`。
- 只框标题栏主体，不把相连明细表、技术要求表或整张大表一起框入。
- 如果边界不好判断，请在 `reference_form.csv` 中写下你的判断依据。
- 该轮样本用于补齐顺时针 90 度和难例参考，不直接代表训练质量门已通过。
""",
        encoding="utf-8",
    )

    summary = summarize(records)
    summary.update(
        {
            "output_dir": str(output_dir),
            "review_index": str(output_dir / "review_index.html"),
            "reference_form": str(output_dir / "reference_form.csv"),
            "manifest": str(output_dir / "round2_manifest.csv"),
            "to_label_dir": str(output_dir / "to_label"),
            "references_dir": str(output_dir / "references"),
            "to_label_images": len(list((output_dir / "to_label").glob("*.png"))),
            "reference_images": len(list((output_dir / "references").glob("*.png"))),
            "reference_form_status": reference_form_status,
        }
    )
    (output_dir / "round2_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build round-2 hardcase YOLO/OBB annotation pack.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    print(json.dumps(build(args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
