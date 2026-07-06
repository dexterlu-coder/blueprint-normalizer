from __future__ import annotations

import argparse
import csv
import html
import os
from pathlib import Path

from scripts.common.obb_utils import ROOT, load_manifest, resolve_path


DEFAULT_MANIFEST = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "smoke_manifest.csv"
DEFAULT_OVERLAY_DIR = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "overlays"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "yolo_obb_annotation_pack" / "smoke" / "overlay_review"


def rel_path(target: Path, base: Path) -> str:
    return Path(os.path.relpath(target, base)).as_posix()


def write_review_csv(path: Path, records: list[dict]) -> None:
    fieldnames = ["序号", "样本编号", "红框是否正确", "备注"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for index, record in enumerate(records, start=1):
            writer.writerow(
                {
                    "序号": index,
                    "样本编号": record["sample"],
                    "红框是否正确": "",
                    "备注": "",
                }
            )


def write_html(path: Path, records: list[dict]) -> None:
    cards = []
    for index, record in enumerate(records, start=1):
        image_src = html.escape(rel_path(record["overlay_path"], path.parent))
        cards.append(
            f"""
      <section class="sheet">
        <div class="meta">
          <strong>{index}. {html.escape(record["sample"])}</strong>
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
  <title>YOLO/OBB 标题栏 overlay 复查</title>
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
    <h1>YOLO/OBB 标题栏 overlay 复查</h1>
    <div class="hint">只检查红框是否准确框住标题栏主体；结果填写到 review_form.csv。</div>
  </header>
  <main>
    {"".join(cards)}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def build(args: argparse.Namespace) -> dict:
    manifest = load_manifest(resolve_path(args.manifest))
    overlay_dir = resolve_path(args.overlay_dir)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    missing: list[str] = []
    for record in manifest:
        overlay_path = overlay_dir / f"{record.sample}_overlay.png"
        if not overlay_path.exists():
            missing.append(record.sample)
            continue
        records.append(
            {
                "sample": record.sample,
                "position": record.precise_title_block_position or record.title_block_position,
                "rotation_degrees": record.rotation_degrees,
                "overlay_path": overlay_path,
            }
        )

    if missing:
        raise FileNotFoundError(f"Missing overlay images: {', '.join(missing)}")

    write_html(output_dir / "review_index.html", records)
    write_review_csv(output_dir / "review_form.csv", records)

    return {
        "output_dir": str(output_dir),
        "review_index": str(output_dir / "review_index.html"),
        "review_form": str(output_dir / "review_form.csv"),
        "total": len(records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an OBB overlay manual review page.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--overlay-dir", type=Path, default=DEFAULT_OVERLAY_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    summary = build(args)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

