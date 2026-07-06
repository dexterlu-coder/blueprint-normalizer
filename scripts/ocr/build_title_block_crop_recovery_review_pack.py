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


DEFAULT_DRY_RUN_RECORDS = (
    ROOT
    / "local_data"
    / "full_63_title_block_ocr_dry_run"
    / "crop_recovery_v1"
    / "full_63_ocr_arbitration_records.jsonl"
)
DEFAULT_REVIEW_INBOX = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_OUTPUT_ROOT = ROOT / "local_data" / "title_block_crop_recovery_review"


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def priority(record: dict[str, Any]) -> tuple[int, str]:
    recovery = ((record.get("ocr") or {}).get("crop_recovery") or {})
    sample = record.get("sample_id") or ""
    if sample in {"sample_006", "sample_008", "sample_009", "sample_016", "sample_022", "sample_032"}:
        return (0, sample)
    if recovery.get("bottom_band_fallback_applied"):
        return (1, sample)
    if recovery.get("right_extension_applied"):
        return (2, sample)
    return (3, sample)


def build_item(record: dict[str, Any], review_dir: Path) -> dict[str, Any]:
    sample_id = record.get("sample_id") or ""
    artifacts = record.get("artifacts") or {}
    recovery = ((record.get("ocr") or {}).get("crop_recovery") or {})
    stem = safe_name(sample_id)

    page_asset = copy_asset(
        artifacts.get("corrected_page_path") or recovery.get("corrected_page_path"),
        review_dir / "assets" / "pages_corrected",
        f"{stem}_page_corrected.png",
    )
    crop_asset = copy_asset(
        artifacts.get("title_block_crop_path") or recovery.get("crop_path"),
        review_dir / "assets" / "crops_recovered",
        f"{stem}_crop_recovered.png",
    )
    overlay_asset = copy_asset(
        artifacts.get("title_block_crop_overlay_path") or recovery.get("overlay_path"),
        review_dir / "assets" / "overlays_recovered",
        f"{stem}_overlay_recovered.png",
    )

    return {
        "record_id": record.get("record_id"),
        "sample_id": sample_id,
        "page_asset": page_asset,
        "crop_asset": crop_asset,
        "overlay_asset": overlay_asset,
        "crop_recovery": recovery,
        "ocr_text_excerpt": ((record.get("evidence") or {}).get("ocr") or {}).get("text_excerpt", ""),
        "review_hint": review_hint(sample_id, recovery),
    }


def review_hint(sample_id: str, recovery: dict[str, Any]) -> str:
    if sample_id == "sample_009":
        return "重点确认是否完整覆盖右下标题栏且不以主体零件图为主"
    if recovery.get("bottom_band_fallback_applied"):
        return "重点确认标题栏是否完整且没有包含过多主体图"
    if recovery.get("right_extension_applied"):
        return "重点确认右侧图名和图号栏是否完整"
    return "请确认修复后 crop 是否完整覆盖标题栏"


def form_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "序号": index,
            "样本编号": item["sample_id"],
            "修复后crop判断": "",
            "问题类型": "",
            "备注": "",
        }
        for index, item in enumerate(items, start=1)
    ]


def review_manifest_rows(items: list[dict[str, Any]], review_dir: Path) -> list[dict[str, Any]]:
    def asset_rel(value: str | None) -> str | None:
        if not value:
            return None
        return rel_path(resolve_path(Path(value)), review_dir)

    return [
        {
            "序号": index,
            "样本编号": item["sample_id"],
            "校正后整页": asset_rel(item.get("page_asset")),
            "修复后标题栏crop": asset_rel(item.get("crop_asset")),
            "位置示意图": asset_rel(item.get("overlay_asset")),
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
    crop_html = image_link(item.get("crop_asset"), review_dir, "修复后标题栏 crop")
    overlay_html = image_link(item.get("overlay_asset"), review_dir, "修复后 crop 位置示意")
    return f"""
    <section class="card">
      <div class="card-head">
        <h2>{index}. {html.escape(item["sample_id"])}</h2>
        <span>{html.escape(item.get("review_hint") or "")}</span>
      </div>
      <div class="images">
        <figure>{page_html}<figcaption>校正后整页</figcaption></figure>
        <figure>{crop_html}<figcaption>修复后标题栏 crop</figcaption></figure>
        <figure>{overlay_html}<figcaption>修复后 crop 位置示意</figcaption></figure>
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
  <title>修复后标题栏 crop 复核</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #202124; background: #f4f6f8; }}
    header {{ position: sticky; top: 0; z-index: 2; padding: 14px 18px; background: #fff; border-bottom: 1px solid #d8dde3; }}
    h1 {{ margin: 0 0 6px; font-size: 20px; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 12px; color: #52606d; font-size: 14px; }}
    main {{ max-width: 1500px; margin: 0 auto; padding: 14px; }}
    .card {{ background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 14px; margin-bottom: 14px; }}
    .card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; margin-bottom: 12px; }}
    h2 {{ margin: 0; font-size: 18px; }}
    .card-head span {{ color: #475569; font-size: 14px; text-align: right; }}
    .images {{ display: grid; grid-template-columns: minmax(380px, 1.4fr) minmax(300px, 1fr) minmax(380px, 1.4fr); gap: 12px; align-items: stretch; }}
    figure {{ margin: 0; min-width: 0; }}
    img {{ display: block; width: 100%; height: min(56vh, 640px); min-height: 300px; object-fit: contain; background: #f8fafc; border: 1px solid #e2e8f0; }}
    figcaption {{ padding-top: 6px; color: #52606d; font-size: 13px; }}
    .missing {{ display: grid; place-items: center; min-height: 300px; background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412; }}
    @media (max-width: 1100px) {{ .images {{ grid-template-columns: 1fr; }} img {{ height: auto; }} .card-head {{ display: block; }} .card-head span {{ display: block; padding-top: 6px; text-align: left; }} }}
  </style>
</head>
<body>
  <header>
    <h1>修复后标题栏 crop 复核</h1>
    <div class="summary">
      <span>总数：{len(items)}</span>
      <span>填写：review_form.csv</span>
      <span>红框为修复后 crop，黄框为修复前参考位置</span>
    </div>
  </header>
  <main>{cards}</main>
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
                "任务：修复后标题栏 crop 完整性复核。",
                "",
                "请打开：",
                "",
                "- `title_block_crop_recovery_review/review_index.html`",
                "- `title_block_crop_recovery_review/review_form.csv`",
                "",
                f"本轮共 {total} 条。",
                "",
                "请确认修复后 crop 是否完整覆盖标题栏，尤其图名和图号栏是否完整。",
                "",
                "本入口只用于审核，不会生成或重命名 PDF。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build(args: argparse.Namespace) -> dict[str, Any]:
    records = sorted(load_jsonl(args.dry_run_records), key=priority)
    review_inbox = resolve_path(args.review_inbox)
    output_root = resolve_path(args.output_root)
    review_dir = review_inbox / "title_block_crop_recovery_review"

    if review_inbox.exists():
        shutil.rmtree(review_inbox)
    review_dir.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    items = [build_item(record, review_dir) for record in records]
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
        ["序号", "样本编号", "修复后crop判断", "问题类型", "备注"],
    )
    write_html(review_index_path, items)
    write_json(review_manifest_path, review_manifest_rows(items, review_dir))
    write_json(machine_manifest_path, items)

    summary = {
        "review_record_count": len(items),
        "missing_asset_count": len(missing_assets),
        "output_dir": as_posix(review_inbox),
        "review_index": as_posix(review_index_path),
        "review_form": as_posix(review_form_path),
        "dry_run_records": as_posix(resolve_path(args.dry_run_records)),
        "modified_pdf": False,
        "renamed_pdf": False,
    }
    write_json(summary_path, summary)
    write_readme(review_inbox / "README.md", len(items))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build recovered title-block crop review pack.")
    parser.add_argument("--dry-run-records", type=Path, default=DEFAULT_DRY_RUN_RECORDS)
    parser.add_argument("--review-inbox", type=Path, default=DEFAULT_REVIEW_INBOX)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> int:
    result = build(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

