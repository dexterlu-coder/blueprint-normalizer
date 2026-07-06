from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover - local fallback for older environments
    from PyPDF2 import PdfReader, PdfWriter

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "aliyun_vlm_mvp"
DEFAULT_SOURCE_PDF = ROOT / "local_data" / "source_pdfs" / "JS2207-00-00升降平台.pdf"
RECORD_VERSION = "aliyun-vlm-mvp-request-v0.2"
DEFAULT_MAX_LONG_SIDE = 1600
DEFAULT_JPEG_QUALITY = 85

PROMPT = """你是机械图纸标题栏定位和图号读取助手。

请只根据图片中可见内容判断，不要猜测看不清的图号。

任务：
1. 只判断当前原始图片屏幕坐标下标题栏所在位置。
2. 读取标题栏中的图号候选，并选择最可信图号。
3. 无法确定时必须设置 needs_human_review=true。

重要规则：
- 不要判断图纸旋转角度。
- 不要输出 current_clockwise_degrees 或 correction_clockwise_degrees。
- 不要把图片想象旋转到正确阅读方向后再判断位置。
- 标题栏位置必须按当前图片屏幕坐标判断：图片顶部就是 top，图片底部就是 bottom，图片左侧就是 left，图片右侧就是 right。
- 如果标题栏位于当前图片右上角，就返回 top_right；即使你认为正确阅读方向下它应该在右下角，也不能改成 bottom_right。
- 有些机械图纸按纸张竖向绘制，标题栏会位于当前图片下方，并横向占满或接近占满图纸宽度；这种情况必须返回 bottom_edge，不要强行返回 bottom_left 或 bottom_right。
- 如果标题栏横跨当前图片顶部、左侧或右侧边缘，应分别返回 top_edge、left_edge、right_edge，不要强行返回角位置。
- 只有标题栏主体集中在角落时，才返回 bottom_right、bottom_left、top_right 或 top_left。
- 真正标题栏通常贴近或贴住图纸外框，并包含图号/图名/名称/材料/比例/设计/制图/校对/审核/批准/日期/单位等字段组合。
- 零件表格、明细表、技术要求表、局部说明表不是标题栏；即使它们靠近右下角或包含表格线，也不能当作标题栏。
- 如果图片中只有零件表格、明细表或其他非标题栏表格，找不到可确认标题栏，title_block_position 必须返回 no_title_block，并设置 needs_human_review=true。

只返回 JSON，不返回 Markdown，不返回额外说明。JSON 必须符合以下字段结构：

{
  "page_orientation": {
    "title_block_position": "bottom_right",
    "confidence": 0.0,
    "evidence": []
  },
  "drawing_number": {
    "candidates": [],
    "selected": "",
    "confidence": 0.0,
    "evidence": []
  },
  "quality_gate": {
    "needs_human_review": true,
    "review_reasons": []
  }
}

字段约束：
- title_block_position 优先使用 bottom_edge、top_edge、left_edge、right_edge、bottom_right、top_right、top_left、bottom_left、no_title_block、unknown。
- 不要使用 bottom、top、left、right 这类旧字段；若标题栏沿边展开，请使用对应的 *_edge。
- confidence 必须是 0 到 1 之间的数字。
- selected 看不清时填空字符串，并设置 needs_human_review=true。
"""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["page_orientation", "drawing_number", "quality_gate"],
    "properties": {
        "page_orientation": {
            "type": "object",
            "required": [
                "title_block_position",
                "confidence",
                "evidence",
            ],
            "properties": {
                "title_block_position": {
                    "enum": [
                        "bottom_edge",
                        "top_edge",
                        "left_edge",
                        "right_edge",
                        "bottom_right",
                        "top_right",
                        "top_left",
                        "bottom_left",
                        "no_title_block",
                        "unknown",
                    ]
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
        },
        "drawing_number": {
            "type": "object",
            "required": ["candidates", "selected", "confidence", "evidence"],
            "properties": {
                "candidates": {"type": "array", "items": {"type": "string"}},
                "selected": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
        },
        "quality_gate": {
            "type": "object",
            "required": ["needs_human_review", "review_reasons"],
            "properties": {
                "needs_human_review": {"type": "boolean"},
                "review_reasons": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def safe_reset_child_dir(path: Path, allowed_root: Path) -> None:
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


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


def split_pdf(source_pdf: Path, output_dir: Path, limit_pages: int | None) -> list[dict[str, Any]]:
    resolved = resolve_path(source_pdf)
    if not resolved.exists():
        raise FileNotFoundError(f"Source PDF not found: {resolved}")

    single_page_dir = output_dir / "single_page_pdfs"
    safe_reset_child_dir(single_page_dir, output_dir)

    reader = PdfReader(str(resolved))
    page_count = len(reader.pages)
    selected_count = min(page_count, limit_pages) if limit_pages else page_count
    records: list[dict[str, Any]] = []
    source_stem = resolved.stem
    for index in range(selected_count):
        page_number = index + 1
        sample_id = f"{source_stem}_page_{page_number:03d}"
        page_pdf = single_page_dir / f"{sample_id}.pdf"
        writer = PdfWriter()
        writer.add_page(reader.pages[index])
        with page_pdf.open("wb") as handle:
            writer.write(handle)
        records.append(
            {
                "task_id": sample_id,
                "source_type": "pdf",
                "source_path": as_posix(resolved),
                "page_number": page_number,
                "single_page_pdf_path": as_posix(page_pdf),
                "rendered_image_path": None,
            }
        )
    return records


def render_pdf_pages(records: list[dict[str, Any]], output_dir: Path, dpi: int) -> None:
    gs = find_ghostscript()
    rendered_dir = output_dir / "rendered_pages"
    safe_reset_child_dir(rendered_dir, output_dir)
    log_dir = output_dir / "logs" / "ghostscript"
    for record in records:
        page_pdf = resolve_path(Path(record["single_page_pdf_path"]))
        png_path = rendered_dir / f"{record['task_id']}.png"
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
        run_command(command, log_dir / f"{record['task_id']}.log")
        record["rendered_image_path"] = as_posix(png_path)


def collect_png_inputs(input_dir: Path, limit_pages: int | None) -> list[dict[str, Any]]:
    resolved = resolve_path(input_dir)
    if not resolved.exists():
        raise FileNotFoundError(f"Input PNG directory not found: {resolved}")
    images = sorted(
        [
            path
            for path in resolved.iterdir()
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ]
    )
    if limit_pages:
        images = images[:limit_pages]
    records = []
    for index, image_path in enumerate(images, start=1):
        records.append(
            {
                "task_id": image_path.stem,
                "source_type": "image",
                "source_path": as_posix(image_path),
                "page_number": index,
                "single_page_pdf_path": None,
                "rendered_image_path": as_posix(image_path),
            }
        )
    return records


def prepare_input_image(
    source_image: Path,
    output_path: Path,
    max_long_side: int,
    jpeg_quality: int,
    image_format: str = "jpeg",
    no_resize: bool = False,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_image) as image:
        image = image.convert("RGB")
        original_width, original_height = image.size
        long_side = max(original_width, original_height)
        scale = 1.0 if no_resize else (min(1.0, max_long_side / long_side) if long_side else 1.0)
        if scale < 1.0:
            new_size = (max(1, round(original_width * scale)), max(1, round(original_height * scale)))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        else:
            new_size = image.size
        if image_format == "png":
            image.save(output_path, format="PNG", optimize=True)
        else:
            image.save(output_path, format="JPEG", quality=jpeg_quality, optimize=True)

    return {
        "input_image_path": as_posix(output_path),
        "input_image_format": image_format,
        "no_resize": no_resize,
        "original_width": original_width,
        "original_height": original_height,
        "prepared_width": new_size[0],
        "prepared_height": new_size[1],
        "jpeg_quality": jpeg_quality,
        "max_long_side": max_long_side,
        "bytes": output_path.stat().st_size,
    }


def data_url_for(path: Path, mime_type: str = "image/jpeg") -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_request(task: dict[str, Any], model: str, image_data_url: str) -> dict[str, Any]:
    return {
        "custom_id": task["task_id"],
        "method": "POST",
        "url": "/chat/completions",
        "body": {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
    }


def build_requests(
    records: list[dict[str, Any]],
    output_dir: Path,
    model: str,
    max_long_side: int,
    jpeg_quality: int,
    image_format: str = "jpeg",
    no_resize: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    input_image_dir = output_dir / "vlm_input_images"
    safe_reset_child_dir(input_image_dir, output_dir)
    requests: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for record in records:
        rendered_value = record.get("rendered_image_path")
        if not rendered_value:
            raise ValueError(f"Missing rendered image for task {record['task_id']}")
        rendered_path = resolve_path(Path(rendered_value))
        extension = "png" if image_format == "png" else "jpg"
        mime_type = "image/png" if image_format == "png" else "image/jpeg"
        prepared_path = input_image_dir / f"{record['task_id']}.{extension}"
        image_meta = prepare_input_image(
            rendered_path,
            prepared_path,
            max_long_side,
            jpeg_quality,
            image_format=image_format,
            no_resize=no_resize,
        )
        image_data_url = data_url_for(prepared_path, mime_type=mime_type)
        request = build_request(record, model, image_data_url)
        requests.append(request)
        manifest_rows.append(
            {
                **record,
                **image_meta,
                "provider_mode": "aliyun_openai_compatible",
                "model": model,
                "request_custom_id": request["custom_id"],
                "response_schema_path": "local_data/aliyun_vlm_mvp/vlm_response_schema.json",
            }
        )
    return requests, manifest_rows


def env_status() -> dict[str, Any]:
    names = ["DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "ALIYUN_VLM_MODEL"]
    return {name: {"present": bool(os.environ.get(name))} for name in names}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build dry-run Aliyun VLM MVP request package.")
    parser.add_argument("--source-pdf", type=Path, default=DEFAULT_SOURCE_PDF)
    parser.add_argument("--input-image-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit-pages", type=int, default=5)
    parser.add_argument("--render-dpi", type=int, default=150)
    parser.add_argument("--max-image-long-side", type=int, default=DEFAULT_MAX_LONG_SIDE)
    parser.add_argument("--jpeg-quality", type=int, default=DEFAULT_JPEG_QUALITY)
    parser.add_argument("--image-format", choices=["jpeg", "png"], default="jpeg")
    parser.add_argument("--no-resize", action="store_true")
    parser.add_argument("--model", default=os.environ.get("ALIYUN_VLM_MODEL", "MODEL_NOT_SET"))
    parser.add_argument("--dry-run-build-requests", action="store_true", default=True)
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.input_image_dir:
        records = collect_png_inputs(args.input_image_dir, args.limit_pages)
    else:
        records = split_pdf(args.source_pdf, output_dir, args.limit_pages)
        render_pdf_pages(records, output_dir, args.render_dpi)

    requests, manifest_rows = build_requests(
        records,
        output_dir,
        args.model,
        args.max_image_long_side,
        args.jpeg_quality,
        image_format=args.image_format,
        no_resize=args.no_resize,
    )

    prompt_path = output_dir / "vlm_prompt.md"
    schema_path = output_dir / "vlm_response_schema.json"
    requests_path = output_dir / "vlm_requests.jsonl"
    manifest_json_path = output_dir / "vlm_request_manifest.json"
    manifest_csv_path = output_dir / "vlm_request_manifest.csv"
    summary_path = output_dir / "vlm_mvp_summary.json"

    prompt_path.write_text(PROMPT, encoding="utf-8")
    write_json(schema_path, RESPONSE_SCHEMA)
    write_jsonl(requests_path, requests)
    write_json(manifest_json_path, manifest_rows)
    write_csv(
        manifest_csv_path,
        manifest_rows,
        [
            "task_id",
            "source_type",
            "source_path",
            "page_number",
            "single_page_pdf_path",
            "rendered_image_path",
            "input_image_path",
            "input_image_format",
            "no_resize",
            "original_width",
            "original_height",
            "prepared_width",
            "prepared_height",
            "jpeg_quality",
            "max_long_side",
            "bytes",
            "provider_mode",
            "model",
            "request_custom_id",
            "response_schema_path",
        ],
    )
    summary = {
        "record_version": RECORD_VERSION,
        "dry_run_build_requests": True,
        "network_call_executed": False,
        "modified_pdf": False,
        "renamed_pdf": False,
        "task_count": len(records),
        "request_count": len(requests),
        "output_dir": as_posix(output_dir),
        "requests_path": as_posix(requests_path),
        "manifest_json_path": as_posix(manifest_json_path),
        "manifest_csv_path": as_posix(manifest_csv_path),
        "prompt_path": as_posix(prompt_path),
        "response_schema_path": as_posix(schema_path),
        "env_status": env_status(),
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
