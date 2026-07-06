from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from scripts.ocr.build_ocr_fine_roi_experiment import ocr_image
from scripts.ocr.build_pdf_correction_dry_run import sanitize_filename
from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_MEMORY_EVENTS = ROOT / "local_data" / "drawing_number_calibration_memory" / "current_session_events.csv"
DEFAULT_FINE_RECORDS = ROOT / "local_data" / "ocr_fine_roi_experiment" / "fine_roi_records.jsonl"
DEFAULT_ROI_RECORDS = ROOT / "local_data" / "ocr_fine_roi_experiment" / "fine_roi_ocr_results.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "ocr_fine_roi_tightening_experiment"
DEFAULT_REVIEW_INBOX = ROOT / "local_data" / "review_inbox" / "current"

REVIEW_NAME = "fine_roi_tightening_review"
OLD_BOX_COLOR = (220, 38, 38)
NEW_BOX_COLOR = (5, 150, 105)


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def rel_path(target: Path | str, base: Path) -> str:
    return Path(os.path.relpath(resolve_path(Path(target)), base)).as_posix()


def safe_name(value: str) -> str:
    sanitized, _ = sanitize_filename(value)
    return sanitized or "record"


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


def read_csv(path: Path) -> list[dict[str, str]]:
    resolved = resolve_path(path)
    with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {str(key).strip().lstrip("\ufeff"): "" if value is None else str(value).strip() for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def by_sample(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record.get("sample_id")): record for record in records}


def roi_records_by_sample(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for record in records:
        sample_id = str(record.get("sample_id"))
        roi_name = str(record.get("roi_name"))
        grouped.setdefault(sample_id, {})[roi_name] = record
    return grouped


def parse_adjustment_percent(suggestions: str, label: str) -> float:
    pattern = rf"{re.escape(label)}约?(\d{{1,3}})%"
    match = re.search(pattern, suggestions)
    if not match:
        return 0.0
    return max(0.0, min(80.0, float(match.group(1)))) / 100.0


def select_base_roi(
    event: dict[str, str],
    fine_record: dict[str, Any],
    sample_rois: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    tags = event.get("roi_note_tags", "")
    old_best_name = str(fine_record.get("best_roi_name") or "")
    if "prefer_bottom_right_blue_roi" in tags and "bottom_right_band_roi" in sample_rois:
        return sample_rois["bottom_right_band_roi"]
    if old_best_name in sample_rois:
        return sample_rois[old_best_name]
    usable = [record for record in sample_rois.values() if record.get("status") == "ok" and record.get("box")]
    if not usable:
        raise ValueError(f"{fine_record.get('sample_id')}: no usable ROI record")
    return usable[0]


def tighten_box(
    box: list[int],
    top_ratio: float,
    left_ratio: float,
) -> tuple[list[int], dict[str, Any]]:
    left, top, right, bottom = [int(value) for value in box]
    width = max(0, right - left)
    height = max(0, bottom - top)
    new_left = left + int(round(width * left_ratio))
    new_top = top + int(round(height * top_ratio))
    new_box = [new_left, new_top, right, bottom]
    new_width = max(0, right - new_left)
    new_height = max(0, bottom - new_top)
    rejected = False
    rejection_reasons: list[str] = []
    if new_width < max(120, int(round(width * 0.35))):
        rejected = True
        rejection_reasons.append("tightening_rejected_width_too_small")
    if new_height < max(80, int(round(height * 0.35))):
        rejected = True
        rejection_reasons.append("tightening_rejected_height_too_small")
    if rejected:
        new_box = [left, top, right, bottom]
        new_width = width
        new_height = height
    return new_box, {
        "old_width": width,
        "old_height": height,
        "new_width": new_width,
        "new_height": new_height,
        "top_trim_ratio": top_ratio,
        "left_trim_ratio": left_ratio,
        "rejected": rejected,
        "rejection_reasons": rejection_reasons,
    }


def box_area(box: list[int]) -> int:
    left, top, right, bottom = box
    return max(0, right - left) * max(0, bottom - top)


def draw_box(draw: ImageDraw.ImageDraw, box: list[int], color: tuple[int, int, int], width: int) -> None:
    left, top, right, bottom = box
    for offset in range(width):
        draw.rectangle(
            (
                left + offset,
                top + offset,
                max(left, right - offset),
                max(top, bottom - offset),
            ),
            outline=color,
        )


def build_comparison_overlay(
    image: Image.Image,
    old_box: list[int],
    new_box: list[int],
    output_path: Path,
) -> None:
    canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    draw_box(draw, old_box, OLD_BOX_COLOR, 5)
    draw_box(draw, new_box, NEW_BOX_COLOR, 7)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def save_image_crop(image: Image.Image, box: list[int], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.crop(tuple(box)).save(output_path)


def process_event(
    event: dict[str, str],
    fine_record: dict[str, Any],
    sample_rois: dict[str, dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    sample_id = event["sample_id"]
    stem = safe_name(sample_id)
    base_roi = select_base_roi(event, fine_record, sample_rois)
    old_box = [int(value) for value in base_roi["box"]]
    suggestions = event.get("roi_adjustment_suggestions", "")
    top_trim = parse_adjustment_percent(suggestions, "上侧减少")
    left_trim = parse_adjustment_percent(suggestions, "左侧向右减少")
    new_box, diagnostics = tighten_box(old_box, top_trim, left_trim)

    source_crop = resolve_path(Path(fine_record["source_crop_path"]))
    if not source_crop.exists():
        raise FileNotFoundError(f"{sample_id}: source crop not found: {source_crop}")
    with Image.open(source_crop) as image:
        coarse_image = image.convert("RGB")

    old_roi_source = resolve_path(Path(base_roi["roi_path"])) if base_roi.get("roi_path") else None
    if old_roi_source and old_roi_source.exists():
        old_roi_path = output_dir / "old_fine_rois" / f"{stem}__old_roi.png"
        old_roi_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_roi_source, old_roi_path)
    else:
        old_roi_path = output_dir / "old_fine_rois" / f"{stem}__old_roi.png"
        save_image_crop(coarse_image, old_box, old_roi_path)

    new_roi_path = output_dir / "new_fine_rois" / f"{stem}__new_roi.png"
    overlay_path = output_dir / "overlays" / f"{stem}__old_new_roi_overlay.png"
    save_image_crop(coarse_image, new_box, new_roi_path)
    build_comparison_overlay(coarse_image, old_box, new_box, overlay_path)

    with Image.open(new_roi_path) as new_image:
        new_ocr = ocr_image(new_image.convert("RGB"))

    old_area = box_area(old_box)
    new_area = box_area(new_box)
    area_ratio = round(new_area / max(1, old_area), 6)
    area_reduction_ratio = round(1.0 - area_ratio, 6)
    new_candidate = new_ocr.get("top_candidate") or ""
    old_candidate = event.get("machine_fine_candidate") or event.get("machine_coarse_candidate") or ""
    ocr_guard_status = "not_evaluated_for_human_review"
    if old_candidate and not new_candidate:
        ocr_guard_status = "new_roi_lost_previous_candidate"
    elif old_candidate and new_candidate:
        ocr_guard_status = "new_roi_has_candidate"
    elif not old_candidate and new_candidate:
        ocr_guard_status = "new_roi_added_candidate"
    else:
        ocr_guard_status = "no_candidate_before_or_after"

    return {
        "sample_id": sample_id,
        "source_crop_path": fine_record.get("source_crop_path"),
        "source_corrected_page_path": fine_record.get("source_corrected_page_path"),
        "base_roi_name": base_roi.get("roi_name"),
        "old_best_roi_name": fine_record.get("best_roi_name"),
        "used_blue_candidate": base_roi.get("roi_name") == "bottom_right_band_roi"
        and fine_record.get("best_roi_name") != "bottom_right_band_roi",
        "old_box": old_box,
        "new_box": new_box,
        "old_area": old_area,
        "new_area": new_area,
        "new_area_vs_old_area": area_ratio,
        "area_reduction_ratio": area_reduction_ratio,
        "top_trim_ratio": diagnostics["top_trim_ratio"],
        "left_trim_ratio": diagnostics["left_trim_ratio"],
        "tightening_rejected": diagnostics["rejected"],
        "rejection_reasons": diagnostics["rejection_reasons"],
        "human_note": event.get("human_note", ""),
        "roi_adjustment_suggestions": event.get("roi_adjustment_suggestions", ""),
        "old_roi_path": as_posix(old_roi_path),
        "new_roi_path": as_posix(new_roi_path),
        "comparison_overlay_path": as_posix(overlay_path),
        "new_ocr_guard": {
            "ocr_status": new_ocr.get("ocr_status"),
            "field_cluster_level": new_ocr.get("field_cluster_level"),
            "candidate_count": new_ocr.get("candidate_count"),
            "top_candidate": new_candidate,
            "previous_machine_candidate": old_candidate,
            "guard_status": ocr_guard_status,
        },
        "modified_pdf": False,
        "renamed_pdf": False,
    }


def copy_asset(source_value: str | None, target_dir: Path, target_name: str) -> str | None:
    if not source_value:
        return None
    source = resolve_path(Path(source_value))
    if not source.exists():
        return None
    target = target_dir / target_name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return as_posix(target)


def review_items(records: list[dict[str, Any]], review_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        sample = record["sample_id"]
        stem = safe_name(sample)
        coarse_asset = copy_asset(
            record.get("source_crop_path"),
            review_dir / "assets" / "coarse_crops",
            f"{stem}__coarse_crop.png",
        )
        old_asset = copy_asset(
            record.get("old_roi_path"),
            review_dir / "assets" / "old_fine_rois",
            f"{stem}__old_roi.png",
        )
        new_asset = copy_asset(
            record.get("new_roi_path"),
            review_dir / "assets" / "new_fine_rois",
            f"{stem}__new_roi.png",
        )
        overlay_asset = copy_asset(
            record.get("comparison_overlay_path"),
            review_dir / "assets" / "overlays",
            f"{stem}__old_new_roi_overlay.png",
        )
        items.append(
            {
                "index": index,
                "sample_id": sample,
                "coarse_asset": coarse_asset,
                "old_asset": old_asset,
                "new_asset": new_asset,
                "overlay_asset": overlay_asset,
                "area_reduction_ratio": record.get("area_reduction_ratio"),
                "roi_adjustment_suggestions": record.get("roi_adjustment_suggestions", ""),
                "human_note": record.get("human_note", ""),
            }
        )
    return items


def form_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "序号": item["index"],
            "样本编号": item["sample_id"],
            "新版ROI判断": "",
            "相对旧ROI是否更好": "",
            "问题类型": "",
            "备注": "",
        }
        for item in items
    ]


def review_manifest_rows(items: list[dict[str, Any]], review_dir: Path) -> list[dict[str, Any]]:
    def asset_rel(value: str | None) -> str | None:
        return rel_path(value, review_dir) if value else None

    return [
        {
            "序号": item["index"],
            "样本编号": item["sample_id"],
            "完整性crop": asset_rel(item.get("coarse_asset")),
            "旧细ROI": asset_rel(item.get("old_asset")),
            "新版ROI": asset_rel(item.get("new_asset")),
            "新旧位置对比": asset_rel(item.get("overlay_asset")),
        }
        for item in items
    ]


def image_html(asset: str | None, review_dir: Path, label: str) -> str:
    if not asset:
        return f'<div class="missing">{html.escape(label)}缺失</div>'
    src = html.escape(rel_path(asset, review_dir))
    return f'<a href="{src}" target="_blank"><img src="{src}" alt="{html.escape(label)}"></a>'


def item_card(item: dict[str, Any], review_dir: Path) -> str:
    coarse_html = image_html(item.get("coarse_asset"), review_dir, "完整性 crop")
    old_html = image_html(item.get("old_asset"), review_dir, "旧细 ROI")
    new_html = image_html(item.get("new_asset"), review_dir, "新版 ROI")
    overlay_html = image_html(item.get("overlay_asset"), review_dir, "新旧位置对比")
    reduction = float(item.get("area_reduction_ratio") or 0.0)
    return f"""
    <section class="card">
      <div class="card-head">
        <h2>{item['index']}. {html.escape(item['sample_id'])}</h2>
        <span>面积减少：{reduction:.1%}</span>
      </div>
      <div class="images">
        <figure>{coarse_html}<figcaption>完整性 crop</figcaption></figure>
        <figure>{old_html}<figcaption>旧细 ROI</figcaption></figure>
        <figure>{new_html}<figcaption>新版 ROI</figcaption></figure>
        <figure>{overlay_html}<figcaption>新旧位置对比：红框旧 ROI，绿框新版 ROI</figcaption></figure>
      </div>
      <dl>
        <dt>收窄建议</dt><dd>{html.escape(item.get('roi_adjustment_suggestions') or '')}</dd>
        <dt>上轮备注</dt><dd>{html.escape(item.get('human_note') or '')}</dd>
      </dl>
    </section>
    """


def write_review_html(path: Path, items: list[dict[str, Any]]) -> None:
    cards = "\n".join(item_card(item, path.parent) for item in items)
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>细 ROI 收窄复核</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #202124; background: #f4f6f8; }}
    header {{ position: sticky; top: 0; z-index: 2; padding: 14px 18px; background: #fff; border-bottom: 1px solid #d8dde3; }}
    h1 {{ margin: 0 0 6px; font-size: 20px; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 12px; color: #52606d; font-size: 14px; }}
    main {{ max-width: 1560px; margin: 0 auto; padding: 14px; }}
    .guide {{ background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 12px 14px; margin-bottom: 14px; color: #334155; font-size: 14px; line-height: 1.7; }}
    .guide h2 {{ margin: 0 0 8px; font-size: 16px; }}
    .guide p {{ margin: 4px 0; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; }}
    .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
    .swatch {{ width: 22px; height: 12px; border-radius: 2px; display: inline-block; }}
    .swatch-old {{ background: #dc2626; }}
    .swatch-new {{ background: #059669; }}
    .card {{ background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 14px; margin-bottom: 14px; }}
    .card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; margin-bottom: 12px; }}
    h2 {{ margin: 0; font-size: 18px; }}
    .card-head span {{ color: #475569; font-size: 14px; text-align: right; }}
    .images {{ display: grid; grid-template-columns: minmax(280px, 1fr) minmax(240px, 0.85fr) minmax(240px, 0.85fr) minmax(280px, 1fr); gap: 12px; align-items: stretch; }}
    figure {{ margin: 0; min-width: 0; }}
    img {{ display: block; width: 100%; height: min(46vh, 540px); min-height: 240px; object-fit: contain; background: #f8fafc; border: 1px solid #e2e8f0; }}
    figcaption {{ padding-top: 6px; color: #52606d; font-size: 13px; }}
    dl {{ display: grid; grid-template-columns: 100px 1fr; gap: 8px 12px; margin: 14px 0 0; font-size: 14px; }}
    dt {{ color: #52606d; }}
    dd {{ margin: 0; font-weight: 600; overflow-wrap: anywhere; }}
    .missing {{ display: grid; place-items: center; min-height: 240px; background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412; }}
    @media (max-width: 1200px) {{ .images {{ grid-template-columns: 1fr; }} img {{ height: auto; }} .card-head {{ display: block; }} .card-head span {{ display: block; padding-top: 6px; text-align: left; }} }}
  </style>
</head>
<body>
  <header>
    <h1>细 ROI 收窄复核</h1>
    <div class="summary">
      <span>总数：{len(items)}</span>
      <span>填写：review_form.csv</span>
      <span>本轮只判断 ROI 是否更好，不判断图号对错</span>
    </div>
  </header>
  <main>
    <section class="guide">
      <h2>填写说明</h2>
      <p><strong>新版ROI判断</strong>：填 正确、范围仍太大、范围太小、位置错误 或 看不清。</p>
      <p><strong>相对旧ROI是否更好</strong>：填 更好、差不多、更差 或 不确定。</p>
      <p><strong>问题类型</strong>：可填 上侧仍多、左侧仍多、裁掉图号栏、裁掉标题栏、混入主体、字太小、其他。</p>
      <p><strong>备注</strong>：只写 ROI 位置与范围问题，暂不评价图号识别正确性。</p>
      <div class="legend">
        <span><i class="swatch swatch-old"></i>红框：旧细 ROI</span>
        <span><i class="swatch swatch-new"></i>绿框：新版 ROI</span>
      </div>
    </section>
    {cards}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_review_readme(path: Path, total: int) -> None:
    path.write_text(
        "\n".join(
            [
                "# 当前待审核任务",
                "",
                "任务：细 ROI 收窄复核。",
                "",
                "请打开：",
                "",
                "- `fine_roi_tightening_review/review_index.html`",
                "- `fine_roi_tightening_review/review_form.csv`",
                "",
                f"本轮共 {total} 条。",
                "",
                "本轮只判断新版 ROI 是否比旧 ROI 更适合作为图号栏输入，暂不判断图号识别是否正确。",
                "",
                "CSV 字段填写：",
                "",
                "- `序号`、`样本编号`：不用填写。",
                "- `新版ROI判断`：填 `正确`、`范围仍太大`、`范围太小`、`位置错误` 或 `看不清`。",
                "- `相对旧ROI是否更好`：填 `更好`、`差不多`、`更差` 或 `不确定`。",
                "- `问题类型`：可填 `上侧仍多`、`左侧仍多`、`裁掉图号栏`、`裁掉标题栏`、`混入主体`、`字太小`、`其他`。",
                "- `备注`：只写 ROI 位置与范围问题，暂不评价图号识别正确性。",
                "",
                "位置示意图颜色：",
                "",
                "- 红框：旧细 ROI。",
                "- 绿框：新版 ROI。",
                "",
                "本入口只用于审核，不会生成或重命名 PDF。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_review_pack(records: list[dict[str, Any]], output_dir: Path, review_inbox: Path) -> dict[str, Any]:
    if review_inbox.exists():
        shutil.rmtree(review_inbox)
    review_dir = review_inbox / REVIEW_NAME
    review_dir.mkdir(parents=True, exist_ok=True)
    items = review_items(records, review_dir)
    write_csv(
        review_dir / "review_form.csv",
        form_rows(items),
        ["序号", "样本编号", "新版ROI判断", "相对旧ROI是否更好", "问题类型", "备注"],
    )
    write_json(review_dir / "review_manifest.json", review_manifest_rows(items, review_dir))
    write_json(output_dir / "review_manifest.json", items)
    write_review_html(review_dir / "review_index.html", items)
    write_review_readme(review_inbox / "README.md", len(items))
    missing_asset_count = sum(
        1
        for item in items
        if not item.get("coarse_asset")
        or not item.get("old_asset")
        or not item.get("new_asset")
        or not item.get("overlay_asset")
    )
    return {
        "review_record_count": len(items),
        "missing_asset_count": missing_asset_count,
        "review_inbox": as_posix(review_inbox),
        "review_index": as_posix(review_dir / "review_index.html"),
        "review_form": as_posix(review_dir / "review_form.csv"),
        "modified_pdf": False,
        "renamed_pdf": False,
    }


def summary_csv_row(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_count": summary["sample_count"],
        "avg_area_reduction_ratio": summary["avg_area_reduction_ratio"],
        "min_area_reduction_ratio": summary["min_area_reduction_ratio"],
        "max_area_reduction_ratio": summary["max_area_reduction_ratio"],
        "base_roi_counts": json.dumps(summary["base_roi_counts"], ensure_ascii=False, sort_keys=True),
        "ocr_guard_counts": json.dumps(summary["ocr_guard_counts"], ensure_ascii=False, sort_keys=True),
        "modified_pdf": summary["modified_pdf"],
        "renamed_pdf": summary["renamed_pdf"],
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    reductions = [float(record.get("area_reduction_ratio") or 0.0) for record in records]
    base_roi_counts = Counter(record.get("base_roi_name") or "unknown" for record in records)
    ocr_guard_counts = Counter((record.get("new_ocr_guard") or {}).get("guard_status") or "unknown" for record in records)
    rejected = [record["sample_id"] for record in records if record.get("tightening_rejected")]
    return {
        "sample_count": len(records),
        "avg_area_reduction_ratio": round(sum(reductions) / max(1, len(reductions)), 6),
        "min_area_reduction_ratio": round(min(reductions) if reductions else 0.0, 6),
        "max_area_reduction_ratio": round(max(reductions) if reductions else 0.0, 6),
        "base_roi_counts": dict(sorted(base_roi_counts.items())),
        "ocr_guard_counts": dict(sorted(ocr_guard_counts.items())),
        "tightening_rejected_samples": rejected,
        "modified_pdf": False,
        "renamed_pdf": False,
    }


def record_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        guard = record.get("new_ocr_guard") or {}
        rows.append(
            {
                "sample_id": record["sample_id"],
                "base_roi_name": record.get("base_roi_name"),
                "old_best_roi_name": record.get("old_best_roi_name"),
                "top_trim_ratio": record.get("top_trim_ratio"),
                "left_trim_ratio": record.get("left_trim_ratio"),
                "area_reduction_ratio": record.get("area_reduction_ratio"),
                "new_area_vs_old_area": record.get("new_area_vs_old_area"),
                "ocr_guard_status": guard.get("guard_status"),
                "new_ocr_status": guard.get("ocr_status"),
                "new_candidate_count": guard.get("candidate_count"),
                "tightening_rejected": record.get("tightening_rejected"),
                "new_roi_path": record.get("new_roi_path"),
                "comparison_overlay_path": record.get("comparison_overlay_path"),
            }
        )
    return rows


def build(args: argparse.Namespace) -> dict[str, Any]:
    memory_events = read_csv(resolve_path(args.memory_events))
    fine_records = by_sample(load_jsonl(resolve_path(args.fine_records)))
    roi_records = roi_records_by_sample(load_jsonl(resolve_path(args.roi_records)))
    output_dir = resolve_path(args.output_dir)
    review_inbox = resolve_path(args.review_inbox)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    missing_samples: list[str] = []
    for event in memory_events:
        sample_id = event.get("sample_id", "")
        fine_record = fine_records.get(sample_id)
        sample_rois = roi_records.get(sample_id, {})
        if not fine_record or not sample_rois:
            missing_samples.append(sample_id)
            continue
        records.append(process_event(event, fine_record, sample_rois, output_dir))

    if missing_samples:
        raise ValueError(f"missing input records for samples: {missing_samples}")

    summary = summarize(records)
    summary["memory_events"] = as_posix(args.memory_events)
    summary["fine_records"] = as_posix(args.fine_records)
    summary["roi_records"] = as_posix(args.roi_records)
    summary["output_dir"] = as_posix(output_dir)

    review_pack = build_review_pack(records, output_dir, review_inbox)
    summary["review_pack"] = review_pack

    write_json(output_dir / "tightening_summary.json", summary)
    write_csv(
        output_dir / "tightening_summary.csv",
        [summary_csv_row(summary)],
        [
            "sample_count",
            "avg_area_reduction_ratio",
            "min_area_reduction_ratio",
            "max_area_reduction_ratio",
            "base_roi_counts",
            "ocr_guard_counts",
            "modified_pdf",
            "renamed_pdf",
        ],
    )
    write_jsonl(output_dir / "tightening_records.jsonl", records)
    write_csv(
        output_dir / "tightening_records.csv",
        record_rows(records),
        [
            "sample_id",
            "base_roi_name",
            "old_best_roi_name",
            "top_trim_ratio",
            "left_trim_ratio",
            "area_reduction_ratio",
            "new_area_vs_old_area",
            "ocr_guard_status",
            "new_ocr_status",
            "new_candidate_count",
            "tightening_rejected",
            "new_roi_path",
            "comparison_overlay_path",
        ],
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build memory-based fine ROI tightening experiment.")
    parser.add_argument("--memory-events", type=Path, default=DEFAULT_MEMORY_EVENTS)
    parser.add_argument("--fine-records", type=Path, default=DEFAULT_FINE_RECORDS)
    parser.add_argument("--roi-records", type=Path, default=DEFAULT_ROI_RECORDS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--review-inbox", type=Path, default=DEFAULT_REVIEW_INBOX)
    return parser.parse_args()


def main() -> int:
    result = build(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

