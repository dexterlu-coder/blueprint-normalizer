from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


REVIEW_NAME = "title_block_crop_review"
DEFAULT_CURRENT_DIR = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_ARCHIVE_ROOT = ROOT / "local_data" / "review_inbox" / "archive"
DEFAULT_SUMMARY_ROOT = ROOT / "local_data" / "title_block_crop_quality_review"

FORM_FIELDS = ["序号", "样本编号", "当前crop判断", "问题类型", "备注"]
COMPLETE_JUDGMENTS = {"已完整识别", "完整覆盖"}
INCOMPLETE_JUDGMENTS = {"未完整识别", "未完整覆盖"}
VISUAL_CHECK_SAMPLES = {
    "sample_006": "右侧少量截断，图号/比例栏贴近或越出旧框。",
    "sample_008": "旧框只覆盖左下技术要求和签字区，右侧图名/图号栏缺失。",
    "sample_009": "旧框混入底部零件视图，真实右下标题栏未完整进入。",
    "sample_016": "右侧标题栏外框和图号尾部存在截断风险。",
    "sample_035": "crop 基本完整，但图号区域偏浅，短横线容易漏读。",
    "sample_042": "crop 基本完整，但图号区域浅且有叠影。",
}


def ensure_inside(path: Path, parent: Path) -> Path:
    resolved_path = path.resolve()
    resolved_parent = parent.resolve()
    try:
        resolved_path.relative_to(resolved_parent)
    except ValueError as exc:
        raise ValueError(f"{resolved_path} is outside {resolved_parent}") from exc
    return resolved_path


def read_csv_compatible(path: Path) -> tuple[list[dict[str, str]], str]:
    resolved = resolve_path(path)
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with resolved.open("r", encoding=encoding, newline="") as handle:
                rows = list(csv.DictReader(handle))
            return [normalize_row(row) for row in rows], encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"unsupported CSV encoding: {resolved}")


def normalize_row(row: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        clean_key = str(key).strip().lstrip("\ufeff")
        normalized[clean_key] = "" if value is None else str(value).strip()
    return normalized


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_manifest(path: Path) -> list[dict[str, Any]]:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def rewrite_manifest_asset_paths(manifest: list[dict[str, Any]], archived_review_dir: Path) -> list[dict[str, Any]]:
    rewritten: list[dict[str, Any]] = []
    for item in manifest:
        copy = dict(item)
        sample_id = copy.get("sample_id", "")
        if sample_id:
            copy["page_asset"] = (
                archived_review_dir
                / "assets"
                / "pages_corrected"
                / f"{sample_id}_page_corrected.png"
            ).relative_to(ROOT).as_posix()
            copy["crop_asset"] = (
                archived_review_dir
                / "assets"
                / "crops_current"
                / f"{sample_id}_crop_current.png"
            ).relative_to(ROOT).as_posix()
            copy["overlay_asset"] = (
                archived_review_dir
                / "assets"
                / "overlays"
                / f"{sample_id}_overlay.png"
            ).relative_to(ROOT).as_posix()
        rewritten.append(copy)
    return rewritten


def classify_row(row: dict[str, str]) -> list[str]:
    judgment = row.get("当前crop判断", "")
    issue_type = row.get("问题类型", "")
    note = row.get("备注", "")
    labels: list[str] = []
    if judgment in COMPLETE_JUDGMENTS:
        labels.append("完整")
    if judgment in INCOMPLETE_JUDGMENTS:
        labels.append("未完整")
    if "右侧" in issue_type or "右侧" in note or "图号未完整" in note:
        labels.append("右侧或图号尾部缺失")
    if "一半" in note:
        labels.append("只覆盖半截标题栏")
    if "位置判断错误" in note or "零件图" in note or "错" in issue_type:
        labels.append("错框或混入主体")
    if "字迹" in note or "不清" in note or "浅" in note or "后处理" in note:
        labels.append("图像质量问题")
    return labels or ["未分层"]


def build_summary(
    rows: list[dict[str, str]],
    encoding: str,
    manifest: list[dict[str, Any]],
    archive_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, str]], str]:
    missing_fields = [field for field in FORM_FIELDS if any(field not in row for row in rows)]
    judgment_counts = Counter(row.get("当前crop判断", "") or "空" for row in rows)
    issue_counts = Counter(row.get("问题类型", "") or "空" for row in rows)
    normalized_judgment_counts = Counter(
        normalized_judgment(row.get("当前crop判断", "")) for row in rows
    )
    sample_by_class: dict[str, list[str]] = defaultdict(list)
    noted_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, str]] = []

    for row in rows:
        sample_id = row.get("样本编号", "")
        labels = classify_row(row)
        for label in labels:
            sample_by_class[label].append(sample_id)
        if row.get("备注", ""):
            noted_rows.append(
                {
                    "样本编号": sample_id,
                    "当前crop判断": row.get("当前crop判断", ""),
                    "问题类型": row.get("问题类型", ""),
                    "备注": row.get("备注", ""),
                }
            )
        summary_rows.append(
            {
                "序号": row.get("序号", ""),
                "样本编号": sample_id,
                "当前crop判断": row.get("当前crop判断", ""),
                "问题类型": row.get("问题类型", ""),
                "备注": row.get("备注", ""),
                "问题分层": "；".join(labels),
            }
        )

    complete_samples = [
        row.get("样本编号", "")
        for row in rows
        if row.get("当前crop判断", "") in COMPLETE_JUDGMENTS
    ]
    incomplete_samples = [
        row.get("样本编号", "")
        for row in rows
        if row.get("当前crop判断", "") in INCOMPLETE_JUDGMENTS
    ]

    machine_summary = {
        "review_name": REVIEW_NAME,
        "archive_dir": archive_dir.relative_to(ROOT).as_posix(),
        "review_form_encoding": encoding,
        "record_count": len(rows),
        "manifest_count": len(manifest),
        "missing_form_fields": missing_fields,
        "judgment_counts": dict(judgment_counts),
        "normalized_judgment_counts": dict(normalized_judgment_counts),
        "issue_type_counts": dict(issue_counts),
        "complete_samples": complete_samples,
        "incomplete_samples": incomplete_samples,
        "samples_by_layer": {key: values for key, values in sorted(sample_by_class.items())},
        "noted_rows": noted_rows,
        "visual_check_samples": VISUAL_CHECK_SAMPLES,
        "next_step": "修复标题栏 crop 生成策略前，优先处理右侧/图号尾部缺失、半截标题栏和错框样本。",
    }

    human_summary = build_human_summary(machine_summary)
    return machine_summary, summary_rows, human_summary


def normalized_judgment(value: str) -> str:
    if value in COMPLETE_JUDGMENTS:
        return "完整"
    if value in INCOMPLETE_JUDGMENTS:
        return "未完整"
    return value or "空"


def build_human_summary(summary: dict[str, Any]) -> str:
    judgment = summary["normalized_judgment_counts"]
    issue_counts = summary["issue_type_counts"]
    samples_by_layer = summary["samples_by_layer"]
    noted_rows = summary["noted_rows"]

    lines = [
        "# 标题栏 crop 完整性审核结果摘要",
        "",
        "## 结论",
        "",
        f"- 审核样本：{summary['record_count']} 条。",
        f"- 完整：{judgment.get('完整', 0)} 条。",
        f"- 未完整：{judgment.get('未完整', 0)} 条。",
        f"- 主要问题类型：{format_issue_counts(issue_counts)}。",
        "",
        "## 问题分层",
        "",
    ]

    for label in ("右侧或图号尾部缺失", "只覆盖半截标题栏", "错框或混入主体", "图像质量问题"):
        samples = samples_by_layer.get(label, [])
        if samples:
            lines.append(f"- {label}：{', '.join(samples)}。")

    lines.extend(["", "## 备注样本", ""])
    if noted_rows:
        for row in noted_rows:
            lines.append(
                f"- {row['样本编号']}：{row['备注']}。"
            )
    else:
        lines.append("- 无。")

    lines.extend(["", "## 抽样视觉核对", ""])
    for sample_id, conclusion in VISUAL_CHECK_SAMPLES.items():
        lines.append(f"- {sample_id}：{conclusion}")

    lines.extend(
        [
            "",
            "## 下一步建议",
            "",
            "- 先修复 crop 生成策略，尤其是向右侧图名/图号栏扩展和错框样本重选。",
            "- 浅字、短横线不清的问题应在 crop 完整性修复后，再进入 OCR 图像预处理小实验。",
            "- 当前结果只用于 crop 质量修复，不作为最终图号命名结论。",
            "",
        ]
    )
    return "\n".join(lines)


def format_issue_counts(issue_counts: dict[str, int]) -> str:
    non_empty = [(key, value) for key, value in issue_counts.items() if key != "空" and value]
    if not non_empty:
        return "无"
    return "，".join(f"{key} {value} 条" for key, value in non_empty)


def unique_archive_dir(archive_root: Path, archive_name: str | None) -> Path:
    if archive_name:
        candidate = archive_root / archive_name
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = archive_root / f"title_block_crop_review_{timestamp}_reviewed"
    if candidate.exists():
        raise FileExistsError(f"archive target already exists: {candidate}")
    return candidate


def reset_current_readme(current_dir: Path, archive_dir: Path) -> None:
    current_dir.mkdir(parents=True, exist_ok=True)
    archive_rel = archive_dir.relative_to(ROOT).as_posix()
    readme = (
        "# 当前审核入口\n\n"
        "当前没有待用户审核、填写或标注的文件。\n\n"
        f"上一轮标题栏 crop 完整性审核已归档到 `{archive_rel}`。\n"
    )
    (current_dir / "README.md").write_text(readme, encoding="utf-8")


def archive_review(args: argparse.Namespace) -> dict[str, Any]:
    current_dir = ensure_inside(resolve_path(args.current_dir), ROOT)
    archive_root = ensure_inside(resolve_path(args.archive_root), ROOT)
    summary_root = ensure_inside(resolve_path(args.summary_root), ROOT)
    review_dir = ensure_inside(current_dir / REVIEW_NAME, current_dir)
    archive_dir = ensure_inside(unique_archive_dir(archive_root, args.archive_name), archive_root)

    if not review_dir.exists():
        raise FileNotFoundError(f"review directory does not exist: {review_dir}")

    form_path = review_dir / "review_form.csv"
    manifest_path = review_dir / "review_manifest.json"
    rows, encoding = read_csv_compatible(form_path)
    manifest = load_manifest(manifest_path)

    if len(rows) != 63:
        raise ValueError(f"expected 63 review rows, got {len(rows)}")
    if len(manifest) != 63:
        raise ValueError(f"expected 63 manifest records, got {len(manifest)}")

    archive_dir.mkdir(parents=True)
    current_readme = current_dir / "README.md"
    if current_readme.exists():
        shutil.copy2(current_readme, archive_dir / "README.md")

    archived_review_dir = archive_dir / REVIEW_NAME
    shutil.move(str(review_dir), str(archived_review_dir))
    manifest = rewrite_manifest_asset_paths(manifest, archived_review_dir)
    write_json(archived_review_dir / "review_manifest.json", manifest)

    machine_summary, summary_rows, human_summary = build_summary(
        rows=rows,
        encoding=encoding,
        manifest=manifest,
        archive_dir=archive_dir,
    )

    for target_root in (archive_dir, summary_root):
        write_json(target_root / "filled_review_summary.json", machine_summary)
        write_csv(
            target_root / "filled_review_summary.csv",
            summary_rows,
            ["序号", "样本编号", "当前crop判断", "问题类型", "备注", "问题分层"],
        )
        (target_root / "human_summary.md").write_text(human_summary, encoding="utf-8")

    reset_current_readme(current_dir, archive_dir)
    return machine_summary


def refresh_archived_review(args: argparse.Namespace) -> dict[str, Any]:
    archive_dir = ensure_inside(resolve_path(args.source_archive_dir), ROOT)
    summary_root = ensure_inside(resolve_path(args.summary_root), ROOT)
    review_dir = ensure_inside(archive_dir / REVIEW_NAME, archive_dir)

    if not review_dir.exists():
        raise FileNotFoundError(f"archived review directory does not exist: {review_dir}")

    rows, encoding = read_csv_compatible(review_dir / "review_form.csv")
    manifest = load_manifest(review_dir / "review_manifest.json")
    manifest = rewrite_manifest_asset_paths(manifest, review_dir)
    write_json(review_dir / "review_manifest.json", manifest)

    if len(rows) != 63:
        raise ValueError(f"expected 63 review rows, got {len(rows)}")
    if len(manifest) != 63:
        raise ValueError(f"expected 63 manifest records, got {len(manifest)}")

    machine_summary, summary_rows, human_summary = build_summary(
        rows=rows,
        encoding=encoding,
        manifest=manifest,
        archive_dir=archive_dir,
    )

    for target_root in (archive_dir, summary_root):
        write_json(target_root / "filled_review_summary.json", machine_summary)
        write_csv(
            target_root / "filled_review_summary.csv",
            summary_rows,
            ["序号", "样本编号", "当前crop判断", "问题类型", "备注", "问题分层"],
        )
        (target_root / "human_summary.md").write_text(human_summary, encoding="utf-8")

    return machine_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-dir", type=Path, default=DEFAULT_CURRENT_DIR)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--summary-root", type=Path, default=DEFAULT_SUMMARY_ROOT)
    parser.add_argument("--archive-name", default=None)
    parser.add_argument("--source-archive-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.source_archive_dir:
        summary = refresh_archived_review(args)
    else:
        summary = archive_review(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

