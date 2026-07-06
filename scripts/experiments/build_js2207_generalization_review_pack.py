from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover - local fallback for older environments
    from PyPDF2 import PdfReader, PdfWriter

from scripts.ocr.build_full_63_title_block_ocr_dry_run import recover_title_block_crop
from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_SOURCE_PDF = ROOT / "local_data" / "source_pdfs" / "JS2207-00-00升降平台.pdf"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "js2207_generalization_test"
DEFAULT_REVIEW_INBOX = ROOT / "local_data" / "review_inbox" / "current"

RECORD_VERSION = "js2207-generalization-v0.1"
SOURCE_LABEL = "JS2207-00-00"
SAMPLE_PREFIX = "js2207_page"

SIDE_LABELS = {
    "bottom": "下方或右下方",
    "left": "左侧",
    "top": "上方或左上方",
    "right": "右侧或右上方",
}


Image.MAX_IMAGE_PIXELS = None


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
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return safe.strip("._") or "record"


def safe_reset_dir(path: Path, allowed_root: Path) -> None:
    resolved = path.resolve()
    allowed = allowed_root.resolve()
    if resolved == allowed:
        raise ValueError(f"Refusing to remove allowed root itself: {resolved}")
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"Refusing to remove path outside allowed root: {resolved}") from exc
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


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


def page_sample_id(page_number: int) -> str:
    return f"{SAMPLE_PREFIX}_{page_number:03d}"


def split_pdf(source_pdf: Path, output_dir: Path) -> list[dict[str, Any]]:
    reader = PdfReader(str(source_pdf))
    records: list[dict[str, Any]] = []
    pdf_dir = output_dir / "single_page_pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    for page_index, page in enumerate(reader.pages):
        page_number = page_index + 1
        sample_id = page_sample_id(page_number)
        page_pdf = pdf_dir / f"{sample_id}.pdf"
        writer = PdfWriter()
        writer.add_page(page)
        with page_pdf.open("wb") as handle:
            writer.write(handle)
        records.append(
            {
                "sample_id": sample_id,
                "page_index": page_index,
                "page_number": page_number,
                "source_pdf_path": as_posix(source_pdf),
                "single_page_pdf_path": as_posix(page_pdf),
            }
        )
    return records


def find_ghostscript() -> str:
    for executable in ("gswin64c", "gswin32c", "gs"):
        found = shutil.which(executable)
        if found:
            return found
    raise RuntimeError("Ghostscript executable not found: expected gswin64c, gswin32c, or gs")


def run_command(command: list[str], log_path: Path) -> None:
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "COMMAND:\n"
        + json.dumps(command, ensure_ascii=False)
        + "\n\nSTDOUT:\n"
        + result.stdout
        + "\n\nSTDERR:\n"
        + result.stderr,
        encoding="utf-8",
    )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-1200:]
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {tail}")


def render_pages(records: list[dict[str, Any]], output_dir: Path, dpi: int) -> None:
    gs = find_ghostscript()
    png_dir = output_dir / "rendered_png"
    log_dir = output_dir / "logs" / "ghostscript"
    png_dir.mkdir(parents=True, exist_ok=True)

    for record in records:
        sample_id = record["sample_id"]
        page_pdf = resolve_path(Path(record["single_page_pdf_path"]))
        png_path = png_dir / f"{sample_id}.png"
        command = [
            gs,
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-sDEVICE=png16m",
            f"-r{dpi}",
            "-dTextAlphaBits=4",
            "-dGraphicsAlphaBits=4",
            f"-sOutputFile={png_path}",
            str(page_pdf),
        ]
        run_command(command, log_dir / f"{sample_id}.log")
        if not png_path.exists():
            raise FileNotFoundError(f"Rendered PNG not found: {png_path}")
        record["rendered_image_path"] = as_posix(png_path)


def run_stage1_detector(output_dir: Path) -> list[dict[str, Any]]:
    input_dir = output_dir / "rendered_png"
    stage1_dir = output_dir / "stage1"
    command = [
        sys.executable,
        "-m",
        "scripts.rotation.detect_rotation_stage1",
        "--input-dir",
        str(input_dir),
        "--output-dir",
        str(stage1_dir),
    ]
    run_command(command, output_dir / "logs" / "detect_rotation_stage1.log")
    results_path = stage1_dir / "results.json"
    if not results_path.exists():
        raise FileNotFoundError(f"Stage1 results not found: {results_path}")
    return json.loads(results_path.read_text(encoding="utf-8"))


def stage1_by_sample(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in results:
        sample_id = Path(row.get("file", "")).stem
        rows[sample_id] = row
    return rows


def build_crop_assets(records: list[dict[str, Any]], output_dir: Path) -> None:
    crop_dir = output_dir / "title_block_crop_recovery"
    for record in records:
        blockers: list[str] = []
        stage1 = record.get("stage1") or {}
        best_candidate = stage1.get("best_candidate") or {}
        bbox = best_candidate.get("bbox")
        correction = stage1.get("correction_clockwise_degrees")
        image_path_value = record.get("rendered_image_path")
        if not bbox:
            blockers.append("missing_stage1_best_candidate_bbox")
        if correction is None:
            blockers.append("missing_correction_clockwise_degrees")
        if not image_path_value:
            blockers.append("missing_rendered_image_path")
        elif not resolve_path(Path(image_path_value)).exists():
            blockers.append("rendered_image_path_not_found")

        crop_recovery: dict[str, Any] = {
            "status": "blocked" if blockers else "not_attempted",
            "blockers": blockers,
            "crop_path": None,
            "corrected_page_path": None,
            "overlay_path": None,
            "modified_pdf": False,
            "renamed_pdf": False,
        }
        if not blockers:
            try:
                with Image.open(resolve_path(Path(image_path_value))) as image:
                    recovered = recover_title_block_crop(
                        image=image.convert("RGB"),
                        bbox=bbox,
                        correction_degrees=int(correction),
                        output_dir=crop_dir,
                        record_id=record["sample_id"],
                    )
                metadata = recovered["metadata"]
                crop_recovery = {
                    "status": "ok",
                    "blockers": [],
                    "crop_path": as_posix(recovered["crop_path"]),
                    "corrected_page_path": as_posix(recovered["corrected_page_path"]),
                    "overlay_path": as_posix(recovered["overlay_path"]),
                    "crop_strategy": metadata.get("crop_strategy"),
                    "modified_pdf": False,
                    "renamed_pdf": False,
                }
            except Exception as exc:  # Keep the page reviewable even if crop recovery fails.
                crop_recovery["status"] = "failed"
                crop_recovery["blockers"] = [f"crop_recovery_failed:{type(exc).__name__}"]
                crop_recovery["error"] = str(exc)
        record["crop_recovery"] = crop_recovery


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
        sample_id = record["sample_id"]
        stem = safe_name(sample_id)
        crop_recovery = record.get("crop_recovery") or {}
        stage1 = record.get("stage1") or {}
        raw_asset = copy_asset(
            record.get("rendered_image_path"),
            review_dir / "assets" / "rendered_pages",
            f"{stem}__rendered.png",
        )
        corrected_asset = copy_asset(
            crop_recovery.get("corrected_page_path"),
            review_dir / "assets" / "corrected_pages",
            f"{stem}__corrected.png",
        )
        crop_asset = copy_asset(
            crop_recovery.get("crop_path"),
            review_dir / "assets" / "title_block_crops",
            f"{stem}__title_block_crop.png",
        )
        overlay_asset = copy_asset(
            crop_recovery.get("overlay_path"),
            review_dir / "assets" / "overlays",
            f"{stem}__title_block_overlay.png",
        )
        items.append(
            {
                "index": index,
                "page_number": record["page_number"],
                "sample_id": sample_id,
                "raw_asset": raw_asset,
                "corrected_asset": corrected_asset,
                "crop_asset": crop_asset,
                "overlay_asset": overlay_asset,
                "machine_title_block_position": stage1.get("title_block_position")
                or SIDE_LABELS.get(stage1.get("title_block_side", ""), ""),
                "machine_rotation_degrees": stage1.get("clockwise_rotation_degrees"),
                "machine_correction_degrees": stage1.get("correction_clockwise_degrees"),
                "machine_needs_review": bool(stage1.get("needs_review")),
                "crop_status": crop_recovery.get("status"),
            }
        )
    return items


def asset_rel(value: str | None, review_dir: Path) -> str | None:
    if not value:
        return None
    return rel_path(value, review_dir)


def review_manifest_rows(items: list[dict[str, Any]], review_dir: Path) -> list[dict[str, Any]]:
    return [
        {
            "序号": item["index"],
            "页码": item["page_number"],
            "样本编号": item["sample_id"],
            "机器标题栏位置": item["machine_title_block_position"],
            "机器旋转角度": item["machine_rotation_degrees"],
            "原始渲染图": asset_rel(item.get("raw_asset"), review_dir),
            "校正后整页": asset_rel(item.get("corrected_asset"), review_dir),
            "标题栏crop": asset_rel(item.get("crop_asset"), review_dir),
            "位置示意图": asset_rel(item.get("overlay_asset"), review_dir),
        }
        for item in items
    ]


def form_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "序号": item["index"],
            "页码": item["page_number"],
            "样本编号": item["sample_id"],
            "机器标题栏位置": item["machine_title_block_position"],
            "机器旋转角度": item["machine_rotation_degrees"],
            "机器判断旋转是否正确": "",
            "机器标题栏位置是否正确": "",
            "正确标题栏位置": "",
            "正确旋转角度": "",
            "备注": "",
        }
        for item in items
    ]


def image_html(asset: str | None, review_dir: Path, label: str) -> str:
    if not asset:
        return f'<div class="missing">{html.escape(label)}缺失</div>'
    src = html.escape(rel_path(asset, review_dir))
    return f'<a href="{src}" target="_blank"><img src="{src}" alt="{html.escape(label)}"></a>'


def yes_no(value: bool) -> str:
    return "是" if value else "否"


def item_card(item: dict[str, Any], review_dir: Path) -> str:
    raw_html = image_html(item.get("raw_asset"), review_dir, "原始渲染图")
    corrected_html = image_html(item.get("corrected_asset"), review_dir, "校正后整页")
    crop_html = image_html(item.get("crop_asset"), review_dir, "标题栏 crop")
    overlay_html = image_html(item.get("overlay_asset"), review_dir, "位置示意图")
    return f"""
    <section class="card">
      <div class="card-head">
        <h2>{item['index']}. 第 {item['page_number']} 页</h2>
        <span>机器判断：标题栏在 {html.escape(str(item.get('machine_title_block_position') or '未知'))}；当前旋转 {html.escape(str(item.get('machine_rotation_degrees')))} 度；建议校正 {html.escape(str(item.get('machine_correction_degrees')))} 度；需复核：{yes_no(item.get('machine_needs_review', False))}</span>
      </div>
      <div class="images">
        <figure>{raw_html}<figcaption>原始渲染图</figcaption></figure>
        <figure>{corrected_html}<figcaption>机器校正后整页</figcaption></figure>
        <figure>{crop_html}<figcaption>标题栏 crop</figcaption></figure>
        <figure>{overlay_html}<figcaption>标题栏位置示意</figcaption></figure>
      </div>
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
  <title>JS2207 旋转与标题栏泛化测试审核</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #202124; background: #f4f6f8; }}
    header {{ position: sticky; top: 0; z-index: 2; padding: 14px 18px; background: #fff; border-bottom: 1px solid #d8dde3; }}
    h1 {{ margin: 0 0 6px; font-size: 20px; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 12px; color: #52606d; font-size: 14px; }}
    main {{ max-width: 1600px; margin: 0 auto; padding: 14px; }}
    .guide {{ background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 12px 14px; margin-bottom: 14px; color: #334155; font-size: 14px; line-height: 1.7; }}
    .guide h2 {{ margin: 0 0 8px; font-size: 16px; }}
    .guide p {{ margin: 4px 0; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; }}
    .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
    .swatch {{ width: 22px; height: 12px; border-radius: 2px; display: inline-block; }}
    .swatch-red {{ background: #dc2626; }}
    .swatch-yellow {{ background: #f59e0b; }}
    .card {{ background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 14px; margin-bottom: 14px; }}
    .card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; margin-bottom: 12px; }}
    h2 {{ margin: 0; font-size: 18px; }}
    .card-head span {{ color: #475569; font-size: 14px; text-align: right; max-width: 760px; }}
    .images {{ display: grid; grid-template-columns: minmax(300px, 1.2fr) minmax(300px, 1.2fr) minmax(260px, 1fr) minmax(300px, 1.2fr); gap: 12px; align-items: stretch; }}
    figure {{ margin: 0; min-width: 0; }}
    img {{ display: block; width: 100%; height: min(48vh, 560px); min-height: 260px; object-fit: contain; background: #f8fafc; border: 1px solid #e2e8f0; }}
    figcaption {{ padding-top: 6px; color: #52606d; font-size: 13px; }}
    .missing {{ display: grid; place-items: center; min-height: 260px; background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412; }}
    @media (max-width: 1200px) {{ .images {{ grid-template-columns: 1fr; }} img {{ height: auto; }} .card-head {{ display: block; }} .card-head span {{ display: block; padding-top: 6px; text-align: left; }} }}
  </style>
</head>
<body>
  <header>
    <h1>JS2207 旋转与标题栏泛化测试审核</h1>
    <div class="summary">
      <span>总数：{len(items)}</span>
      <span>填写：review_form.csv</span>
      <span>本轮只审核旋转方向和标题栏位置，不审核图号</span>
    </div>
  </header>
  <main>
    <section class="guide">
      <h2>填写说明</h2>
      <p><strong>机器判断旋转是否正确</strong>：看“机器校正后整页”是否已经转到正常阅读方向，填 正确、错误 或 不确定。</p>
      <p><strong>机器标题栏位置是否正确</strong>：看“标题栏 crop”和“标题栏位置示意”是否框到真实标题栏，填 正确、错误 或 不确定。</p>
      <p><strong>正确标题栏位置</strong>：只有机器位置错误时填写，可填 下方、右侧、上方、左侧、右下方、右上方、左上方 或 左下方。</p>
      <p><strong>正确旋转角度</strong>：只有机器旋转错误时填写，填页面当前相对正确方向已顺时针旋转的角度：0、90、180 或 270。</p>
      <div class="legend">
        <span><i class="swatch swatch-red"></i>红框：本轮标题栏 crop</span>
        <span><i class="swatch swatch-yellow"></i>黄框：原始检测候选框参考</span>
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
                "任务：JS2207 旋转方向与标题栏位置泛化测试审核。",
                "",
                "请打开：",
                "",
                "- `js2207_generalization_review/review_index.html`",
                "- `js2207_generalization_review/review_form.csv`",
                "",
                f"本轮共 {total} 页。",
                "",
                "填写规则：",
                "",
                "- `序号`、`页码`、`样本编号`、`机器标题栏位置`、`机器旋转角度`：不用填写。",
                "- `机器判断旋转是否正确`：看 HTML 中的“机器校正后整页”是否为正常阅读方向，填 `正确`、`错误` 或 `不确定`。",
                "- `机器标题栏位置是否正确`：看“标题栏 crop”和“标题栏位置示意”是否框到真实标题栏，填 `正确`、`错误` 或 `不确定`。",
                "- `正确标题栏位置`：只有机器标题栏位置错误时填写，可填 `下方`、`右侧`、`上方`、`左侧`、`右下方`、`右上方`、`左上方` 或 `左下方`。",
                "- `正确旋转角度`：只有机器旋转错误时填写，填页面当前相对正确方向已顺时针旋转的角度：`0`、`90`、`180` 或 `270`。",
                "- `备注`：简短写原因，例如标题栏漏裁、框到明细表、校正后仍倒置、看不清。",
                "",
                "本轮只审核旋转方向和标题栏位置，不审核图号识别。",
                "",
                "本入口只用于审核，不会生成正式旋正 PDF，也不会重命名 PDF。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_review_pack(records: list[dict[str, Any]], review_inbox: Path) -> dict[str, Any]:
    safe_reset_dir(review_inbox, ROOT / "local_data" / "review_inbox")
    review_dir = review_inbox / "js2207_generalization_review"
    review_dir.mkdir(parents=True, exist_ok=True)
    items = review_items(records, review_dir)
    form_path = review_dir / "review_form.csv"
    index_path = review_dir / "review_index.html"
    manifest_path = review_dir / "review_manifest.json"
    write_csv(
        form_path,
        form_rows(items),
        [
            "序号",
            "页码",
            "样本编号",
            "机器标题栏位置",
            "机器旋转角度",
            "机器判断旋转是否正确",
            "机器标题栏位置是否正确",
            "正确标题栏位置",
            "正确旋转角度",
            "备注",
        ],
    )
    write_json(manifest_path, review_manifest_rows(items, review_dir))
    write_review_html(index_path, items)
    write_review_readme(review_inbox / "README.md", len(items))

    missing_asset_count = sum(
        1
        for item in items
        if not item.get("raw_asset")
        or not item.get("corrected_asset")
        or not item.get("crop_asset")
        or not item.get("overlay_asset")
    )
    return {
        "review_record_count": len(items),
        "missing_asset_count": missing_asset_count,
        "review_inbox": as_posix(review_inbox),
        "review_index": as_posix(index_path),
        "review_form": as_posix(form_path),
        "review_manifest": as_posix(manifest_path),
        "modified_pdf": False,
        "renamed_pdf": False,
    }


def attach_stage1_results(records: list[dict[str, Any]], stage1_results: list[dict[str, Any]]) -> None:
    by_sample = stage1_by_sample(stage1_results)
    for record in records:
        stage1 = by_sample.get(record["sample_id"])
        if stage1 is None:
            record["stage1"] = {"status": "missing"}
        else:
            record["stage1"] = {"status": "ok", **stage1}


def summarize(records: list[dict[str, Any]], review_pack: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    needs_review_count = sum(1 for record in records if (record.get("stage1") or {}).get("needs_review"))
    crop_ok_count = sum(1 for record in records if (record.get("crop_recovery") or {}).get("status") == "ok")
    return {
        "record_version": RECORD_VERSION,
        "source_label": SOURCE_LABEL,
        "page_count": len(records),
        "stage1_result_count": sum(1 for record in records if (record.get("stage1") or {}).get("status") == "ok"),
        "stage1_needs_review_count": needs_review_count,
        "crop_ok_count": crop_ok_count,
        "crop_issue_count": len(records) - crop_ok_count,
        "review_pack": review_pack,
        "output_dir": as_posix(output_dir),
        "algorithm_changes": False,
        "js2207_specific_optimization": False,
        "dry_run_only": True,
        "modified_pdf": False,
        "renamed_pdf": False,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    source_pdf = resolve_path(args.source_pdf)
    output_dir = resolve_path(args.output_dir)
    review_inbox = resolve_path(args.review_inbox)
    if not source_pdf.exists():
        raise FileNotFoundError(f"Source PDF not found: {source_pdf}")

    safe_reset_dir(output_dir, ROOT / "local_data")
    records = split_pdf(source_pdf, output_dir)
    render_pages(records, output_dir, args.dpi)
    stage1_results = run_stage1_detector(output_dir)
    attach_stage1_results(records, stage1_results)
    build_crop_assets(records, output_dir)

    records_path = output_dir / "js2207_generalization_records.jsonl"
    write_jsonl(records_path, records)
    write_csv(
        output_dir / "js2207_generalization_summary.csv",
        [
            {
                "page_number": record["page_number"],
                "sample_id": record["sample_id"],
                "machine_title_block_position": (record.get("stage1") or {}).get("title_block_position", ""),
                "machine_rotation_degrees": (record.get("stage1") or {}).get("clockwise_rotation_degrees", ""),
                "machine_correction_degrees": (record.get("stage1") or {}).get("correction_clockwise_degrees", ""),
                "needs_review": (record.get("stage1") or {}).get("needs_review", ""),
                "crop_status": (record.get("crop_recovery") or {}).get("status", ""),
                "single_page_pdf_path": record.get("single_page_pdf_path", ""),
                "rendered_image_path": record.get("rendered_image_path", ""),
            }
            for record in records
        ],
        [
            "page_number",
            "sample_id",
            "machine_title_block_position",
            "machine_rotation_degrees",
            "machine_correction_degrees",
            "needs_review",
            "crop_status",
            "single_page_pdf_path",
            "rendered_image_path",
        ],
    )
    review_pack = build_review_pack(records, review_inbox)
    summary = summarize(records, review_pack, output_dir)
    summary["records"] = as_posix(records_path)
    write_json(output_dir / "js2207_generalization_summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build JS2207 generalization test review pack.")
    parser.add_argument("--source-pdf", type=Path, default=DEFAULT_SOURCE_PDF)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--review-inbox", type=Path, default=DEFAULT_REVIEW_INBOX)
    parser.add_argument("--dpi", type=int, default=150)
    return parser.parse_args()


def main() -> int:
    result = build(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

