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

from PIL import Image, ImageDraw

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_DRY_RUN_RECORDS = (
    ROOT
    / "local_data"
    / "full_63_title_block_ocr_dry_run"
    / "pdf_correction_dry_run_v2"
    / "dry_run_records.jsonl"
)
DEFAULT_REVIEW_INBOX = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_ARCHIVE_ROOT = ROOT / "local_data" / "review_inbox" / "archive"
DEFAULT_OUTPUT_ROOT = ROOT / "local_data" / "title_block_crop_quality_review"
DEFAULT_STAGE1_RESULTS = ROOT / "outputs" / "rotation-detection" / "stage1" / "results.json"
CROP_PADDING_RATIO = 0.03


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def rel_path(target: Path, base: Path) -> str:
    return Path(os.path.relpath(target, base)).as_posix()


def safe_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return safe.strip("._") or "record"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    resolved = resolve_path(path)
    records: list[dict[str, Any]] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{resolved}:{line_number}: invalid JSONL") from exc
    return records


def load_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_compatible(path: Path) -> tuple[list[dict[str, str]], str]:
    resolved = resolve_path(path)
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            with resolved.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle)), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"unsupported CSV encoding: {resolved}")


def parse_right_angle_degrees(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        degrees = int(value) % 360
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid correction_degrees: {value!r}") from exc
    if degrees not in {0, 90, 180, 270}:
        raise ValueError(f"unsupported correction_degrees: {value!r}")
    return degrees


def rotate_clockwise(image: Image.Image, degrees: int) -> Image.Image:
    if degrees == 0:
        return image.copy()
    return image.rotate(-degrees, expand=True)


def corrected_image(source_value: str | None, correction_degrees: Any) -> Image.Image | None:
    if not source_value:
        return None
    source = resolve_path(Path(source_value))
    if not source.exists():
        return None
    degrees = parse_right_angle_degrees(correction_degrees)
    if degrees is None:
        return None
    with Image.open(source) as image:
        return rotate_clockwise(image.convert("RGB"), degrees)


def save_corrected_asset(
    source_value: str | None,
    correction_degrees: Any,
    target: Path,
) -> str | None:
    image = corrected_image(source_value, correction_degrees)
    if image is None:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG")
    return as_posix(target)


def sample_from_stage1_file(filename: str) -> str:
    stem = Path(filename).stem
    if "_sample_" in stem:
        return stem.split("_sample_", 1)[0].split("__")[-1] + "_sample_" + stem.split("_sample_", 1)[1]
    if "sample_" in stem:
        index = stem.index("sample_")
        return stem[index:]
    return stem


def build_stage1_by_sample(results_path: Path) -> dict[str, dict[str, Any]]:
    rows = load_json(results_path)
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        sample = sample_from_stage1_file(row.get("file", ""))
        if sample.startswith("YKJ125-00-00-2525_"):
            sample = sample.replace("YKJ125-00-00-2525_", "", 1)
        result[sample] = row
    return result


def padded_crop_box(
    image_size: tuple[int, int],
    bbox: list[int | float],
    padding_ratio: float,
) -> tuple[int, int, int, int]:
    width, height = image_size
    left, top, right, bottom = [float(value) for value in bbox]
    box_width = max(1.0, right - left)
    box_height = max(1.0, bottom - top)
    pad_x = box_width * padding_ratio
    pad_y = box_height * padding_ratio
    left_i = max(0, int(round(left - pad_x)))
    top_i = max(0, int(round(top - pad_y)))
    right_i = min(width, int(round(right + pad_x)))
    bottom_i = min(height, int(round(bottom + pad_y)))
    return left_i, top_i, right_i, bottom_i


def corrected_size(image_size: tuple[int, int], degrees: int) -> tuple[int, int]:
    width, height = image_size
    if degrees in {90, 270}:
        return height, width
    return width, height


def transform_point_clockwise(
    x: float,
    y: float,
    image_size: tuple[int, int],
    degrees: int,
) -> tuple[float, float]:
    width, height = image_size
    if degrees == 0:
        return x, y
    if degrees == 90:
        return height - y, x
    if degrees == 180:
        return width - x, height - y
    if degrees == 270:
        return y, width - x
    raise ValueError(f"unsupported correction_degrees: {degrees}")


def transform_box_clockwise(
    box: tuple[int, int, int, int],
    image_size: tuple[int, int],
    degrees: int,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    points = [
        transform_point_clockwise(left, top, image_size, degrees),
        transform_point_clockwise(right, top, image_size, degrees),
        transform_point_clockwise(right, bottom, image_size, degrees),
        transform_point_clockwise(left, bottom, image_size, degrees),
    ]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    out_width, out_height = corrected_size(image_size, degrees)
    return (
        max(0, min(out_width, int(round(min(xs))))),
        max(0, min(out_height, int(round(min(ys))))),
        max(0, min(out_width, int(round(max(xs))))),
        max(0, min(out_height, int(round(max(ys))))),
    )


def source_image_size(source_value: str | None) -> tuple[int, int] | None:
    if not source_value:
        return None
    source = resolve_path(Path(source_value))
    if not source.exists():
        return None
    with Image.open(source) as image:
        return image.size


def current_crop_box(
    source_value: str | None,
    stage1: dict[str, Any] | None,
    correction_degrees: Any,
) -> tuple[tuple[int, int, int, int] | None, tuple[int, int, int, int] | None]:
    image_size = source_image_size(source_value)
    bbox = ((stage1 or {}).get("best_candidate") or {}).get("bbox")
    degrees = parse_right_angle_degrees(correction_degrees)
    if image_size is None or not bbox or degrees is None:
        return None, None
    original_box = padded_crop_box(image_size, bbox, CROP_PADDING_RATIO)
    corrected_box = transform_box_clockwise(original_box, image_size, degrees)
    return original_box, corrected_box


def save_overlay(
    page_asset: Path,
    target: Path,
    crop_box: tuple[int, int, int, int] | None,
) -> str | None:
    if not page_asset.exists() or crop_box is None:
        return None
    with Image.open(page_asset) as page_source:
        page = page_source.convert("RGB")
        draw = ImageDraw.Draw(page)
        box = crop_box
        for offset in range(6):
            draw.rectangle(
                (
                    box[0] + offset,
                    box[1] + offset,
                    max(box[0], box[2] - offset),
                    max(box[1], box[3] - offset),
                ),
                outline=(220, 38, 38),
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        page.save(target, format="PNG")
    return as_posix(target)


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def archive_current_review_inbox(current_dir: Path, archive_root: Path) -> dict[str, Any]:
    current = resolve_path(current_dir)
    archive_base = resolve_path(archive_root)
    archive_base.mkdir(parents=True, exist_ok=True)
    archive_dir = archive_base / f"naming_review_partial_{timestamp()}"

    if not current.exists():
        return {
            "archived": False,
            "reason": "current_review_inbox_missing",
            "archive_dir": as_posix(archive_dir),
        }

    if archive_dir.exists():
        raise FileExistsError(f"archive already exists: {archive_dir}")

    shutil.copytree(current, archive_dir)
    form_path = archive_dir / "naming_review" / "review_form.csv"
    rows: list[dict[str, str]] = []
    encoding = None
    if form_path.exists():
        rows, encoding = read_csv_compatible(form_path)
    filled_rows = [
        row
        for row in rows
        if any(
            (row.get(field) or "").strip()
            for field in ("旋转判断", "人工判断", "人工确认图号", "备注")
        )
    ]
    summary = {
        "archived": True,
        "archive_dir": as_posix(archive_dir),
        "review_form": as_posix(form_path) if form_path.exists() else None,
        "review_form_encoding": encoding,
        "review_form_row_count": len(rows),
        "filled_row_count": len(filled_rows),
        "rotation_correct_count": sum(
            1 for row in filled_rows if (row.get("旋转判断") or "").strip() == "正确"
        ),
        "manual_error_count": sum(
            1 for row in filled_rows if (row.get("人工判断") or "").strip() == "错误"
        ),
        "noted_sample_ids": [
            row.get("样本编号")
            for row in filled_rows
            if (row.get("备注") or "").strip()
        ],
    }
    write_json(archive_dir / "partial_feedback_summary.json", summary)
    return summary


def priority(record: dict[str, Any]) -> tuple[int, str]:
    route = (record.get("review_routing") or {}).get("route") or ""
    sample = record.get("sample_id") or ""
    if route != "auto_dry_run_ready":
        return (0, sample)
    return (1, sample)


def review_hint(sample_id: str) -> str:
    known: dict[str, str] = {
        "sample_008": "重点看右侧图名/图号是否缺失",
        "sample_009": "重点看是否混入主体且遗漏右下图号栏",
        "sample_022": "重点看右侧图名/图号是否缺失",
        "sample_032": "重点看右侧图名/图号是否缺失",
        "sample_016": "重点看右侧图号尾部是否被截断",
        "sample_006": "重点看右侧图号尾部是否被截断",
        "sample_035": "重点看字迹浅和短横线",
        "sample_039": "重点看字迹浅和短横线",
        "sample_042": "重点看字迹浅、叠影和是否需人工兜底",
    }
    return known.get(sample_id, "请判断当前 crop 是否完整覆盖标题栏")


def build_review_item(
    record: dict[str, Any],
    review_dir: Path,
    stage1_by_sample: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sample_id = record.get("sample_id") or ""
    input_data = record.get("input") or {}
    crop_data = record.get("title_block_crop") or {}
    arbitration = record.get("arbitration") or {}
    correction_degrees = arbitration.get("correction_degrees")

    page_target = review_dir / "assets" / "pages_corrected" / f"{safe_name(sample_id)}_page_corrected.png"
    crop_target = review_dir / "assets" / "crops_current" / f"{safe_name(sample_id)}_crop_current.png"
    overlay_target = review_dir / "assets" / "overlays" / f"{safe_name(sample_id)}_overlay.png"

    page_asset = save_corrected_asset(
        input_data.get("rendered_image_path"),
        correction_degrees,
        page_target,
    )
    crop_asset = save_corrected_asset(
        crop_data.get("crop_path"),
        correction_degrees,
        crop_target,
    )
    overlay_asset = None
    original_crop_box, corrected_crop_box = current_crop_box(
        input_data.get("rendered_image_path"),
        stage1_by_sample.get(sample_id),
        correction_degrees,
    )
    if page_asset and crop_asset:
        overlay_asset = save_overlay(page_target, overlay_target, corrected_crop_box)

    return {
        "record_id": record.get("record_id"),
        "sample_id": sample_id,
        "page_asset": page_asset,
        "crop_asset": crop_asset,
        "overlay_asset": overlay_asset,
        "source_page_path": input_data.get("rendered_image_path"),
        "source_crop_path": crop_data.get("crop_path"),
        "current_crop_box_px": original_crop_box,
        "corrected_crop_box_px": corrected_crop_box,
        "title_block_position": arbitration.get("title_block_position"),
        "correction_degrees": correction_degrees,
        "review_hint": review_hint(sample_id),
    }


def form_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "序号": index,
            "样本编号": item["sample_id"],
            "当前crop判断": "",
            "问题类型": "",
            "备注": "",
        }
        for index, item in enumerate(items, start=1)
    ]


def image_link(asset: str | None, review_dir: Path, label: str) -> str:
    if not asset:
        return f'<div class="missing">{html.escape(label)}缺失</div>'
    src = rel_path(resolve_path(Path(asset)), review_dir)
    escaped = html.escape(src)
    return f'<a href="{escaped}" target="_blank"><img src="{escaped}" alt="{html.escape(label)}"></a>'


def item_card(item: dict[str, Any], review_dir: Path, index: int) -> str:
    page_html = image_link(item.get("page_asset"), review_dir, "校正后整页")
    crop_html = image_link(item.get("crop_asset"), review_dir, "当前标题栏 crop")
    overlay_html = image_link(item.get("overlay_asset"), review_dir, "当前 crop 位置示意")
    return f"""
    <section class="card">
      <div class="card-head">
        <h2>{index}. {html.escape(item["sample_id"])}</h2>
        <span>{html.escape(item.get("review_hint") or "")}</span>
      </div>
      <div class="images">
        <figure>
          {page_html}
          <figcaption>校正后整页</figcaption>
        </figure>
        <figure>
          {crop_html}
          <figcaption>当前标题栏 crop</figcaption>
        </figure>
        <figure>
          {overlay_html}
          <figcaption>当前 crop 位置示意</figcaption>
        </figure>
      </div>
    </section>
    """


def write_html(path: Path, items: list[dict[str, Any]]) -> None:
    cards = "\n".join(item_card(item, path.parent, index) for index, item in enumerate(items, start=1))
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>标题栏 crop 完整性审核</title>
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
      padding: 14px 18px;
      background: #fff;
      border-bottom: 1px solid #d8dde3;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 20px;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      color: #52606d;
      font-size: 14px;
    }}
    main {{
      max-width: 1500px;
      margin: 0 auto;
      padding: 14px;
    }}
    .card {{
      background: #fff;
      border: 1px solid #d8dde3;
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 14px;
    }}
    .card-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 12px;
    }}
    h2 {{
      margin: 0;
      font-size: 18px;
    }}
    .card-head span {{
      color: #475569;
      font-size: 14px;
      text-align: right;
    }}
    .images {{
      display: grid;
      grid-template-columns: minmax(380px, 1.4fr) minmax(300px, 1fr) minmax(380px, 1.4fr);
      gap: 12px;
      align-items: stretch;
    }}
    figure {{
      margin: 0;
      min-width: 0;
    }}
    img {{
      display: block;
      width: 100%;
      height: min(56vh, 640px);
      min-height: 300px;
      object-fit: contain;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
    }}
    figcaption {{
      padding-top: 6px;
      color: #52606d;
      font-size: 13px;
    }}
    .missing {{
      display: grid;
      place-items: center;
      min-height: 300px;
      background: #fff7ed;
      border: 1px solid #fed7aa;
      color: #9a3412;
    }}
    @media (max-width: 1100px) {{
      .images {{ grid-template-columns: 1fr; }}
      img {{ height: auto; }}
      .card-head {{ display: block; }}
      .card-head span {{ display: block; padding-top: 6px; text-align: left; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>标题栏 crop 完整性审核</h1>
    <div class="summary">
      <span>总数：{len(items)}</span>
      <span>填写：review_form.csv</span>
      <span>判断 crop 是否完整覆盖标题栏，尤其图名和图号栏</span>
    </div>
  </header>
  <main>
    {cards}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_readme(path: Path, total: int, archive_summary: dict[str, Any]) -> None:
    path.write_text(
        "\n".join(
            [
                "# 当前待审核任务",
                "",
                "任务：标题栏 crop 完整性审核。",
                "",
                "请打开：",
                "",
                "- `title_block_crop_review/review_index.html`",
                "- `title_block_crop_review/review_form.csv`",
                "",
                f"本轮共 {total} 条。",
                "",
                "请判断当前 crop 是否完整覆盖标题栏，尤其是图名和图号栏是否完整。",
                "",
                "建议填写：",
                "",
                "- `当前crop判断`：完整、右侧缺失、左侧缺失、错框、混入主体、字迹差、不确定。",
                "- `问题类型`：可填写同样的短语，或多个短语用分号分隔。",
                "- `备注`：只写人工判断需要补充的信息。",
                "",
                f"上一轮命名审核部分反馈已归档到：`{archive_summary.get('archive_dir')}`。",
                "",
                "本入口只用于审核，不会生成或重命名 PDF。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build(args: argparse.Namespace) -> dict[str, Any]:
    dry_run_records_path = resolve_path(args.dry_run_records)
    review_inbox = resolve_path(args.review_inbox)
    archive_root = resolve_path(args.archive_root)
    output_root = resolve_path(args.output_root)
    stage1_results_path = resolve_path(args.stage1_results)
    review_dir = review_inbox / "title_block_crop_review"

    archive_summary = archive_current_review_inbox(review_inbox, archive_root)

    if review_inbox.exists():
        shutil.rmtree(review_inbox)
    review_dir.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    records = sorted(load_jsonl(dry_run_records_path), key=priority)
    stage1_by_sample = build_stage1_by_sample(stage1_results_path)
    items = [build_review_item(record, review_dir, stage1_by_sample) for record in records]
    missing_assets = [
        item
        for item in items
        if not item.get("page_asset") or not item.get("crop_asset") or not item.get("overlay_asset")
    ]

    review_form_path = review_dir / "review_form.csv"
    review_index_path = review_dir / "review_index.html"
    review_manifest_path = review_dir / "review_manifest.json"
    summary_path = output_root / "review_summary.json"
    machine_manifest_path = output_root / "review_manifest.json"

    write_csv(
        review_form_path,
        form_rows(items),
        ["序号", "样本编号", "当前crop判断", "问题类型", "备注"],
    )
    write_html(review_index_path, items)
    write_json(review_manifest_path, items)
    write_json(machine_manifest_path, items)

    summary = {
        "review_record_count": len(items),
        "missing_asset_count": len(missing_assets),
        "output_dir": as_posix(review_inbox),
        "review_index": as_posix(review_index_path),
        "review_form": as_posix(review_form_path),
        "archive_summary": archive_summary,
        "stage1_results": as_posix(stage1_results_path),
        "modified_pdf": False,
        "renamed_pdf": False,
    }
    write_json(summary_path, summary)
    write_readme(review_inbox / "README.md", len(items), archive_summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build title-block crop quality review pack.")
    parser.add_argument("--dry-run-records", type=Path, default=DEFAULT_DRY_RUN_RECORDS)
    parser.add_argument("--review-inbox", type=Path, default=DEFAULT_REVIEW_INBOX)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--stage1-results", type=Path, default=DEFAULT_STAGE1_RESULTS)
    return parser.parse_args()


def main() -> int:
    result = build(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

