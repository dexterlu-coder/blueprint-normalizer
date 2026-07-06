from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
from pathlib import Path
from typing import Any

from PIL import Image

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_DRY_RUN_RECORDS = (
    ROOT
    / "local_data"
    / "full_63_title_block_ocr_dry_run"
    / "pdf_correction_dry_run_v2"
    / "dry_run_records.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_MACHINE_OUTPUT_DIR = ROOT / "local_data" / "full_63_naming_review_pack"


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


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def machine_group(record: dict[str, Any]) -> str:
    route = (record.get("review_routing") or {}).get("route")
    if route == "auto_dry_run_ready":
        return "机器建议通过"
    return "异常需处理"


def priority(record: dict[str, Any]) -> tuple[int, str]:
    route = (record.get("review_routing") or {}).get("route") or ""
    sample = record.get("sample_id") or ""
    if route != "auto_dry_run_ready":
        return (0, sample)
    return (1, sample)


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


def build_corrected_asset(
    source_value: str | None,
    target_dir: Path,
    sample_id: str,
    suffix: str,
    correction_degrees: Any,
) -> str | None:
    if not source_value:
        return None
    source = resolve_path(Path(source_value))
    if not source.exists():
        return None
    degrees = parse_right_angle_degrees(correction_degrees)
    if degrees is None:
        return None
    target = target_dir / f"{safe_name(sample_id)}_{suffix}_corrected.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        corrected = rotate_clockwise(image, degrees)
        corrected.save(target, format="PNG")
    return as_posix(target)


def record_to_review_item(record: dict[str, Any], review_dir: Path) -> dict[str, Any]:
    sample_id = record.get("sample_id") or ""
    input_data = record.get("input") or {}
    crop = record.get("title_block_crop") or {}
    ocr = record.get("ocr") or {}
    drawing = record.get("drawing_number") or {}
    rename = record.get("rename_plan") or {}
    routing = record.get("review_routing") or {}
    arbitration = record.get("arbitration") or {}
    correction_degrees = arbitration.get("correction_degrees")

    corrected_page_asset = build_corrected_asset(
        input_data.get("rendered_image_path"),
        review_dir / "assets" / "pages_corrected",
        sample_id,
        "page",
        correction_degrees,
    )
    corrected_crop_asset = build_corrected_asset(
        crop.get("crop_path"),
        review_dir / "assets" / "crops_corrected",
        sample_id,
        "crop",
        correction_degrees,
    )
    reasons = routing.get("route_reasons") or []

    return {
        "record_id": record.get("record_id"),
        "sample_id": sample_id,
        "machine_group": machine_group(record),
        "route": routing.get("route"),
        "route_reasons": reasons,
        "title_block_position": arbitration.get("title_block_position"),
        "correction_degrees": correction_degrees,
        "selected_drawing_number": drawing.get("selected_candidate"),
        "filename_safe_value": rename.get("filename_safe_value"),
        "ocr_text_excerpt": ocr.get("ocr_text_excerpt"),
        "drawing_number_status": drawing.get("selection_status"),
        "page_asset": corrected_page_asset,
        "crop_asset": corrected_crop_asset,
        "corrected_page_asset": corrected_page_asset,
        "corrected_crop_asset": corrected_crop_asset,
        "source_page_path": input_data.get("rendered_image_path"),
        "source_crop_path": crop.get("crop_path"),
        "can_rename": bool(rename.get("can_rename")),
        "human_decision": "",
        "human_confirmed_drawing_number": "",
        "human_note": "",
    }


def form_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        rows.append(
            {
                "序号": index,
                "样本编号": item["sample_id"],
                "机器候选图号": item["selected_drawing_number"] or "",
                "机器拟文件名": item["filename_safe_value"] or "",
                "旋转判断": "",
                "人工判断": "",
                "人工确认图号": "",
                "备注": "",
            }
        )
    return rows


def html_badge(text: str, kind: str) -> str:
    return f'<span class="badge {kind}">{html.escape(text)}</span>'


def human_hint(item: dict[str, Any]) -> str:
    if item.get("selected_drawing_number"):
        return "请核对候选图号和拟文件名"
    return "请查看标题栏并填写图号"


def item_card(item: dict[str, Any], review_dir: Path, index: int) -> str:
    page_src = rel_path(resolve_path(Path(item["page_asset"])), review_dir) if item.get("page_asset") else ""
    crop_src = rel_path(resolve_path(Path(item["crop_asset"])), review_dir) if item.get("crop_asset") else ""
    number = item.get("selected_drawing_number") or "未识别"
    filename = item.get("filename_safe_value") or "未生成"
    ocr_excerpt = item.get("ocr_text_excerpt") or ""
    hint = human_hint(item)

    page_html = (
        f'<a href="{html.escape(page_src)}" target="_blank"><img src="{html.escape(page_src)}" alt="校正后页面预览"></a>'
        if page_src
        else '<div class="missing">校正后页面预览缺失</div>'
    )
    crop_html = (
        f'<a href="{html.escape(crop_src)}" target="_blank"><img src="{html.escape(crop_src)}" alt="校正后标题栏 crop"></a>'
        if crop_src
        else '<div class="missing">校正后标题栏 crop 缺失</div>'
    )

    return f"""
    <section class="card">
      <div class="card-head">
        <h2>{index}. {html.escape(item["sample_id"])}</h2>
        <div>{html_badge(hint, "neutral")}</div>
      </div>
      <div class="images">
        <figure>
          {page_html}
          <figcaption>校正后页面预览</figcaption>
        </figure>
        <figure>
          {crop_html}
          <figcaption>校正后标题栏 crop</figcaption>
        </figure>
      </div>
      <dl>
        <dt>机器候选图号</dt><dd>{html.escape(number)}</dd>
        <dt>机器拟文件名</dt><dd>{html.escape(filename)}</dd>
        <dt>校正角度</dt><dd>{html.escape(str(item.get("correction_degrees")))} 度</dd>
      </dl>
      <p class="ocr">{html.escape(ocr_excerpt)}</p>
    </section>
    """


def write_html(path: Path, items: list[dict[str, Any]]) -> None:
    cards = "\n".join(item_card(item, path.parent, index) for index, item in enumerate(items, start=1))
    machine_suggested = sum(1 for item in items if item["machine_group"] == "机器建议通过")
    exception_count = len(items) - machine_suggested
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>63 条图号命名人工审核</title>
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
      max-width: 1320px;
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
    .images {{
      display: grid;
      grid-template-columns: minmax(360px, 2fr) minmax(260px, 1fr);
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
      height: min(58vh, 680px);
      min-height: 320px;
      object-fit: contain;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
    }}
    figcaption {{
      padding-top: 6px;
      color: #52606d;
      font-size: 13px;
    }}
    dl {{
      display: grid;
      grid-template-columns: 130px 1fr;
      gap: 8px 12px;
      margin: 14px 0 0;
      font-size: 14px;
    }}
    dt {{ color: #52606d; }}
    dd {{ margin: 0; font-weight: 600; overflow-wrap: anywhere; }}
    .ocr {{
      margin: 12px 0 0;
      padding: 10px;
      background: #f8fafc;
      border-left: 4px solid #94a3b8;
      color: #334155;
      line-height: 1.6;
      font-size: 13px;
    }}
    .badge {{
      display: inline-block;
      margin-left: 8px;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
    }}
    .ok {{ background: #e3f8e8; color: #1f7a3d; }}
    .warn {{ background: #fff2d8; color: #9a5b00; }}
    .neutral {{ background: #edf2f7; color: #3e4c59; }}
    .missing {{
      display: grid;
      place-items: center;
      min-height: 320px;
      background: #fff7ed;
      border: 1px solid #fed7aa;
      color: #9a3412;
    }}
    @media (max-width: 900px) {{
      .images {{ grid-template-columns: 1fr; }}
      img {{ height: auto; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>63 条图号命名人工审核</h1>
    <div class="summary">
      <span>总数：{len(items)}</span>
      <span>机器建议通过：{machine_suggested}</span>
      <span>异常需处理：{exception_count}</span>
      <span>填写：review_form.csv</span>
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


def write_readme(path: Path, total: int, machine_suggested: int, exception_count: int) -> None:
    path.write_text(
        "\n".join(
            [
                "# 当前待审核任务",
                "",
                "任务：63 条图号命名人工审核。",
                "",
                "请打开：",
                "",
                "- `naming_review/review_index.html`",
                "- `naming_review/review_form.csv`",
                "",
                f"本轮共 {total} 条：机器建议通过 {machine_suggested} 条，异常需处理 {exception_count} 条。",
                "",
                "页面和标题栏 crop 已按机器校正角度旋转显示，请逐条确认旋转方向、机器候选图号和拟文件名是否可用。",
                "",
                "人工判断建议填写：",
                "",
                "- `通过`：机器图号可用。",
                "- `修正`：填写人工确认图号。",
                "- `打回`：当前图号不可信，需要后续增强 OCR、重新 crop 或专项处理。",
                "",
                "本入口只用于审核，不会生成或重命名 PDF。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build(args: argparse.Namespace) -> dict[str, Any]:
    dry_run_records_path = resolve_path(args.dry_run_records)
    output_dir = resolve_path(args.output_dir)
    machine_output_dir = resolve_path(args.machine_output_dir)
    review_dir = output_dir / "naming_review"

    source_records = load_jsonl(dry_run_records_path)
    source_records = sorted(source_records, key=priority)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    review_dir.mkdir(parents=True, exist_ok=True)
    machine_output_dir.mkdir(parents=True, exist_ok=True)

    items = [record_to_review_item(record, review_dir) for record in source_records]
    machine_suggested = sum(1 for item in items if item["machine_group"] == "机器建议通过")
    exception_count = len(items) - machine_suggested
    missing_assets = [
        item
        for item in items
        if not item.get("page_asset") or not item.get("crop_asset")
    ]

    review_form_path = review_dir / "review_form.csv"
    review_index_path = review_dir / "review_index.html"
    review_manifest_path = review_dir / "review_manifest.json"
    machine_manifest_path = machine_output_dir / "review_manifest.json"
    summary_path = machine_output_dir / "review_summary.json"

    write_csv(
        review_form_path,
        form_rows(items),
        [
            "序号",
            "样本编号",
            "机器候选图号",
            "机器拟文件名",
            "旋转判断",
            "人工判断",
            "人工确认图号",
            "备注",
        ],
    )
    write_html(review_index_path, items)
    write_json(review_manifest_path, items)
    write_json(machine_manifest_path, items)

    summary = {
        "review_record_count": len(items),
        "machine_suggested_count": machine_suggested,
        "exception_count": exception_count,
        "missing_asset_count": len(missing_assets),
        "modified_pdf": False,
        "renamed_pdf": False,
        "output_dir": as_posix(output_dir),
        "review_index": as_posix(review_index_path),
        "review_form": as_posix(review_form_path),
    }
    write_json(summary_path, summary)
    write_readme(output_dir / "README.md", len(items), machine_suggested, exception_count)

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build full 63 naming manual review pack.")
    parser.add_argument("--dry-run-records", type=Path, default=DEFAULT_DRY_RUN_RECORDS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--machine-output-dir", type=Path, default=DEFAULT_MACHINE_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    result = build(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

