from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


REVIEW_NAME = "title_block_crop_recovery_review"
DEFAULT_CURRENT_DIR = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_ARCHIVE_ROOT = ROOT / "local_data" / "review_inbox" / "archive"
DEFAULT_SUMMARY_ROOT = ROOT / "local_data" / "title_block_crop_recovery_review"

FORM_FIELDS = ["序号", "样本编号", "修复后crop判断", "问题类型", "备注"]
CORRECT_JUDGMENTS = {"正确", "完整", "完整覆盖", "已完整覆盖"}
TOO_LARGE_ISSUE = "范围太大"


def ensure_inside(path: Path, parent: Path) -> Path:
    resolved_path = path.resolve()
    resolved_parent = parent.resolve()
    try:
        resolved_path.relative_to(resolved_parent)
    except ValueError as exc:
        raise ValueError(f"{resolved_path} is outside {resolved_parent}") from exc
    return resolved_path


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


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


def classify_row(row: dict[str, str]) -> list[str]:
    issue_type = row.get("问题类型", "")
    note = row.get("备注", "")
    labels: list[str] = []
    if row.get("修复后crop判断", "") in CORRECT_JUDGMENTS:
        labels.append("完整性正确")
    if issue_type == TOO_LARGE_ISSUE or "范围太大" in note:
        labels.append("范围太大")
    if "左半边" in note or "不是标题栏" in note or "图纸" in note:
        labels.append("包含非标题栏图纸区域")
    return labels or ["未分层"]


def build_summary_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    summary_rows: list[dict[str, str]] = []
    for row in rows:
        labels = classify_row(row)
        summary_rows.append(
            {
                "序号": row.get("序号", ""),
                "样本编号": row.get("样本编号", ""),
                "修复后crop判断": row.get("修复后crop判断", ""),
                "问题类型": row.get("问题类型", ""),
                "备注": row.get("备注", ""),
                "问题分层": "；".join(labels),
            }
        )
    return summary_rows


def build_summary(
    rows: list[dict[str, str]],
    encoding: str,
    manifest: list[dict[str, Any]],
    archive_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, str]], str]:
    missing_fields = [field for field in FORM_FIELDS if any(field not in row for row in rows)]
    judgment_counts = Counter(row.get("修复后crop判断", "") or "空" for row in rows)
    issue_counts = Counter(row.get("问题类型", "") or "空" for row in rows)
    layer_counts: Counter[str] = Counter()
    samples_by_layer: dict[str, list[str]] = {}
    noted_rows: list[dict[str, str]] = []

    for row in rows:
        sample_id = row.get("样本编号", "")
        labels = classify_row(row)
        for label in labels:
            layer_counts[label] += 1
            samples_by_layer.setdefault(label, []).append(sample_id)
        if row.get("备注", "") or row.get("问题类型", ""):
            noted_rows.append(
                {
                    "样本编号": sample_id,
                    "修复后crop判断": row.get("修复后crop判断", ""),
                    "问题类型": row.get("问题类型", ""),
                    "备注": row.get("备注", ""),
                }
            )

    too_large_samples = samples_by_layer.get("范围太大", [])
    machine_summary = {
        "review_name": REVIEW_NAME,
        "archive_dir": as_posix(archive_dir),
        "review_form_encoding": encoding,
        "record_count": len(rows),
        "manifest_count": len(manifest),
        "missing_form_fields": missing_fields,
        "judgment_counts": dict(judgment_counts),
        "issue_type_counts": dict(issue_counts),
        "layer_counts": dict(layer_counts),
        "all_correct_count": judgment_counts.get("正确", 0),
        "too_large_count": len(too_large_samples),
        "too_large_samples": too_large_samples,
        "noted_rows": noted_rows,
        "next_step": "调研并设计完整性 crop 与 OCR 用细 ROI 的关系，避免粗 crop 给图号 OCR 增加不必要噪声。",
        "modified_pdf": False,
        "renamed_pdf": False,
    }
    human_summary = build_human_summary(machine_summary)
    return machine_summary, build_summary_rows(rows), human_summary


def build_human_summary(summary: dict[str, Any]) -> str:
    too_large_samples = summary["too_large_samples"]
    lines = [
        "# 修复后标题栏 crop 复核结果摘要",
        "",
        "## 结论",
        "",
        f"- 审核样本：{summary['record_count']} 条。",
        f"- 判断为正确：{summary['all_correct_count']} 条。",
        f"- 标注范围太大：{summary['too_large_count']} 条。",
        "- 典型备注：左半边不是标题栏，而是图纸。",
        "",
        "## 范围太大样本",
        "",
    ]
    if too_large_samples:
        lines.append("- " + "、".join(too_large_samples) + "。")
    else:
        lines.append("- 无。")
    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 当前修复策略已经解决标题栏完整覆盖问题。",
            "- 但大量样本包含非标题栏图纸区域，后续若直接送入图号 OCR，可能增加候选噪声和规则复杂度。",
            "- 下一步应调研并设计完整性 crop 与 OCR 用细 ROI 的双轨策略。",
            "",
        ]
    )
    return "\n".join(lines)


def unique_archive_dir(archive_root: Path, archive_name: str | None) -> Path:
    if archive_name:
        candidate = archive_root / archive_name
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = archive_root / f"{REVIEW_NAME}_{timestamp}_reviewed"
    if candidate.exists():
        raise FileExistsError(f"archive target already exists: {candidate}")
    return candidate


def reset_current_readme(current_dir: Path, archive_dir: Path) -> None:
    current_dir.mkdir(parents=True, exist_ok=True)
    archive_rel = as_posix(archive_dir)
    readme = (
        "# 当前审核入口\n\n"
        "当前没有待用户审核、填写或标注的文件。\n\n"
        f"上一轮修复后标题栏 crop 复核已归档到 `{archive_rel}`。\n"
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
            ["序号", "样本编号", "修复后crop判断", "问题类型", "备注", "问题分层"],
        )
        (target_root / "human_summary.md").write_text(human_summary, encoding="utf-8")

    reset_current_readme(current_dir, archive_dir)
    return machine_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive recovered title-block crop review results.")
    parser.add_argument("--current-dir", type=Path, default=DEFAULT_CURRENT_DIR)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--summary-root", type=Path, default=DEFAULT_SUMMARY_ROOT)
    parser.add_argument("--archive-name", default=None)
    return parser.parse_args()


def main() -> int:
    summary = archive_review(parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

