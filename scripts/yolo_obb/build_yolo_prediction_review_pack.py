from __future__ import annotations

import argparse
import csv
import html
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREDICTIONS_DIR = ROOT / "local_data" / "yolo_predictions"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "review_inbox" / "current"


def rel_path(target: Path, base: Path) -> str:
    return Path(os.path.relpath(target, base)).as_posix()


def prediction_count(label_path: Path) -> int:
    if not label_path.exists():
        return 0
    with label_path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def collect_records(predictions_dir: Path, splits: list[str]) -> list[dict]:
    records: list[dict] = []
    for split in splits:
        split_dir = predictions_dir / f"round2_{split}"
        label_dir = split_dir / "labels"
        if not split_dir.exists():
            raise FileNotFoundError(f"Missing prediction directory: {split_dir}")
        for image_path in sorted(split_dir.glob("*.jpg")):
            sample = image_path.stem
            records.append(
                {
                    "split": split,
                    "sample": sample,
                    "source_image": image_path,
                    "prediction_count": prediction_count(label_dir / f"{sample}.txt"),
                }
            )
    return records


def write_csv(path: Path, records: list[dict]) -> None:
    fieldnames = ["序号", "数据集", "样本编号", "预测框数量", "预测框是否可接受", "问题类型", "备注"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for index, record in enumerate(records, start=1):
            writer.writerow(
                {
                    "序号": index,
                    "数据集": record["split"],
                    "样本编号": record["sample"],
                    "预测框数量": record["prediction_count"],
                    "预测框是否可接受": "",
                    "问题类型": "",
                    "备注": "",
                }
            )


def write_html(path: Path, records: list[dict]) -> None:
    cards = []
    for index, record in enumerate(records, start=1):
        image_src = html.escape(rel_path(record["review_image"], path.parent))
        cards.append(
            f"""
      <section class="sheet">
        <div class="meta">
          <strong>{index}. {html.escape(record["split"])} / {html.escape(record["sample"])}</strong>
          <span>{record["prediction_count"]} 个预测框</span>
          <a href="{image_src}" target="_blank" rel="noreferrer">打开大图</a>
        </div>
        <img src="{image_src}" alt="{html.escape(record["sample"])}" />
      </section>"""
        )

    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>YOLO/OBB 首训预测复查</title>
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
      background: #fff;
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
      grid-template-columns: repeat(auto-fit, minmax(680px, 1fr));
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
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      border-bottom: 1px solid #edf0f2;
      font-size: 14px;
    }}
    .meta a {{
      color: #1a73e8;
      text-decoration: none;
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
    <h1>YOLO/OBB 首训预测复查</h1>
    <div class="hint">只判断预测框是否能作为标题栏检测证据；结果填写到 review_form.csv。</div>
  </header>
  <main>
    {"".join(cards)}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_readme(path: Path, total: int) -> None:
    path.write_text(
        "\n".join(
            [
                "# 当前待审核任务",
                "",
                "任务：YOLO/OBB 首训预测结果复查。",
                "",
                "请打开：",
                "",
                "- `prediction_review/review_index.html`",
                "- `prediction_review/review_form.csv`",
                "",
                f"本轮需要复查 {total} 张 val/test 预测图。",
                "",
                "只需要判断预测框是否可接受；不需要查看训练日志或机器字段。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build(args: argparse.Namespace) -> dict:
    predictions_dir = args.predictions_dir.resolve()
    output_dir = args.output_dir.resolve()
    review_dir = output_dir / "prediction_review"
    image_dir = review_dir / "images"

    records = collect_records(predictions_dir, args.splits)

    if review_dir.exists():
        shutil.rmtree(review_dir)
    image_dir.mkdir(parents=True, exist_ok=True)

    for record in records:
        review_name = f"{record['split']}_{record['sample']}.jpg"
        review_image = image_dir / review_name
        shutil.copy2(record["source_image"], review_image)
        record["review_image"] = review_image

    write_html(review_dir / "review_index.html", records)
    write_csv(review_dir / "review_form.csv", records)
    write_readme(output_dir / "README.md", len(records))

    return {
        "review_dir": str(review_dir),
        "review_index": str(review_dir / "review_index.html"),
        "review_form": str(review_dir / "review_form.csv"),
        "total": len(records),
        "splits": args.splits,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a YOLO prediction manual review pack.")
    parser.add_argument("--predictions-dir", type=Path, default=DEFAULT_PREDICTIONS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--splits", nargs="+", default=["val", "test"])
    args = parser.parse_args()

    print(build(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
