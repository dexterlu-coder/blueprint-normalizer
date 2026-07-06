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


REVIEW_NAME = "fine_roi_tightening_review"
DEFAULT_CURRENT_DIR = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_ARCHIVE_ROOT = ROOT / "local_data" / "review_inbox" / "archive"
DEFAULT_SUMMARY_ROOT = ROOT / "local_data" / "fine_roi_tightening_review"
DEFAULT_TIGHTENING_RECORDS = ROOT / "local_data" / "ocr_fine_roi_tightening_experiment" / "tightening_records.jsonl"

FORM_FIELDS = ["序号", "样本编号", "新版ROI判断", "相对旧ROI是否更好", "问题类型", "备注"]


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


def normalize_row(row: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        clean_key = str(key).strip().lstrip("\ufeff")
        normalized[clean_key] = "" if value is None else str(value).strip()
    return normalized


def read_csv_compatible(path: Path) -> tuple[list[dict[str, str]], str]:
    resolved = resolve_path(path)
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with resolved.open("r", encoding=encoding, newline="") as handle:
                rows = [normalize_row(row) for row in csv.DictReader(handle)]
            return rows, encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"unsupported CSV encoding: {resolved}")


def load_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


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


def unique_archive_dir(archive_root: Path, archive_name: str | None) -> Path:
    if archive_name:
        candidate = archive_root / archive_name
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = archive_root / f"{REVIEW_NAME}_{timestamp}_reviewed"
    if candidate.exists():
        raise FileExistsError(f"archive target already exists: {candidate}")
    return candidate


def tightening_by_sample(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record.get("sample_id")): record for record in records}


def classify_row(row: dict[str, str]) -> list[str]:
    judgment = row.get("新版ROI判断", "")
    relative = row.get("相对旧ROI是否更好", "")
    issue_type = row.get("问题类型", "")
    note = row.get("备注", "")
    labels: list[str] = []
    if judgment == "正确" and relative == "更好":
        labels.append("新版ROI通过")
    if judgment == "范围太小" or "太小" in judgment or issue_type == "裁掉标题栏":
        labels.append("收窄过度")
    if "旧ROI的高度更好" in note or "高度更好" in note:
        labels.append("保留旧高度")
    if "左右范围合适" in note:
        labels.append("采用新版左右范围")
    if issue_type:
        labels.append(issue_type)
    return labels or ["未分层"]


def build_summary_rows(rows: list[dict[str, str]], records_by_sample: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    summary_rows: list[dict[str, Any]] = []
    for row in rows:
        sample = row.get("样本编号", "")
        machine = records_by_sample.get(sample, {})
        labels = classify_row(row)
        summary_rows.append(
            {
                "序号": row.get("序号", ""),
                "样本编号": sample,
                "新版ROI判断": row.get("新版ROI判断", ""),
                "相对旧ROI是否更好": row.get("相对旧ROI是否更好", ""),
                "问题类型": row.get("问题类型", ""),
                "备注": row.get("备注", ""),
                "问题分层": "；".join(labels),
                "面积减少比例": machine.get("area_reduction_ratio", ""),
                "基础ROI类型": machine.get("base_roi_name", ""),
                "顶部收窄比例": machine.get("top_trim_ratio", ""),
                "左侧收窄比例": machine.get("left_trim_ratio", ""),
            }
        )
    return summary_rows


def build_summary(
    rows: list[dict[str, str]],
    encoding: str,
    manifest: list[dict[str, Any]],
    archive_dir: Path,
    tightening_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    missing_fields = [field for field in FORM_FIELDS if any(field not in row for row in rows)]
    records_by_sample = tightening_by_sample(tightening_records)
    judgment_counts = Counter(row.get("新版ROI判断", "") or "空" for row in rows)
    relative_counts = Counter(row.get("相对旧ROI是否更好", "") or "空" for row in rows)
    issue_counts = Counter(row.get("问题类型", "") or "空" for row in rows)
    layer_counts: Counter[str] = Counter()
    samples_by_layer: dict[str, list[str]] = {}
    noted_rows: list[dict[str, str]] = []

    for row in rows:
        sample = row.get("样本编号", "")
        labels = classify_row(row)
        for label in labels:
            layer_counts[label] += 1
            samples_by_layer.setdefault(label, []).append(sample)
        if row.get("备注") or row.get("问题类型"):
            noted_rows.append(
                {
                    "样本编号": sample,
                    "新版ROI判断": row.get("新版ROI判断", ""),
                    "相对旧ROI是否更好": row.get("相对旧ROI是否更好", ""),
                    "问题类型": row.get("问题类型", ""),
                    "备注": row.get("备注", ""),
                }
            )

    accepted_samples = [
        row.get("样本编号", "")
        for row in rows
        if row.get("新版ROI判断") == "正确" and row.get("相对旧ROI是否更好") == "更好"
    ]
    needs_adjustment_samples = samples_by_layer.get("收窄过度", [])
    sample001_rule = {
        "sample_id": "sample_001",
        "rule": "保留旧 ROI 高度，采用新版左右范围；不要无条件套用上侧减少。",
        "reason": "人工标记新版 ROI 范围太小、更差、裁掉标题栏，但左右范围合适。",
    } if "sample_001" in needs_adjustment_samples else None

    machine_summary = {
        "review_name": REVIEW_NAME,
        "archive_dir": as_posix(archive_dir),
        "review_form_encoding": encoding,
        "record_count": len(rows),
        "manifest_count": len(manifest),
        "tightening_record_count": len(tightening_records),
        "missing_form_fields": missing_fields,
        "judgment_counts": dict(judgment_counts),
        "relative_counts": dict(relative_counts),
        "issue_type_counts": dict(issue_counts),
        "layer_counts": dict(layer_counts),
        "accepted_count": len(accepted_samples),
        "accepted_samples": accepted_samples,
        "needs_adjustment_count": len(needs_adjustment_samples),
        "needs_adjustment_samples": needs_adjustment_samples,
        "noted_rows": noted_rows,
        "rule_recommendations": [
            "将 31 条人工确认正确且更好的新版 ROI 作为收窄策略可接受样本。",
            "将高度收窄与左右收窄拆开，避免对所有样本无条件上侧减少。",
            "对 sample_001 采用新版左右范围但保留旧 ROI 高度。",
        ],
        "sample001_rule": sample001_rule,
        "modified_pdf": False,
        "renamed_pdf": False,
    }
    human_summary = build_human_summary(machine_summary)
    return machine_summary, build_summary_rows(rows, records_by_sample), human_summary


def build_human_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# 细 ROI 收窄复核结果摘要",
        "",
        "## 结论",
        "",
        f"- 审核样本：{summary['record_count']} 条。",
        f"- 新版 ROI 正确且更好：{summary['accepted_count']} 条。",
        f"- 需要调整：{summary['needs_adjustment_count']} 条。",
        "- 当前收窄策略整体有效，但不能无条件套用上侧减少。",
        "",
        "## 需要调整样本",
        "",
    ]
    needs = summary.get("needs_adjustment_samples") or []
    if needs:
        lines.append("- " + "、".join(needs) + "。")
    else:
        lines.append("- 无。")
    sample_rule = summary.get("sample001_rule")
    if sample_rule:
        lines.extend(
            [
                "",
                "## sample_001 规则",
                "",
                f"- {sample_rule['rule']}",
                f"- 原因：{sample_rule['reason']}",
            ]
        )
    lines.extend(
        [
            "",
            "## 后续建议",
            "",
            "- 固化细 ROI 收窄策略前，先把高度收窄与左右收窄拆开。",
            "- 大多数样本可以采用本轮新版 ROI 收窄结果。",
            "- 审核完成前仍不处理图号识别正确性，不重建 63 条命名审核包。",
            "",
        ]
    )
    return "\n".join(lines)


def reset_current_readme(current_dir: Path, archive_dir: Path, summary_root: Path) -> None:
    current_dir.mkdir(parents=True, exist_ok=True)
    readme = (
        "# 当前审核入口\n\n"
        "当前没有待用户审核、填写或标注的文件。\n\n"
        f"上一轮细 ROI 收窄复核已归档到 `{as_posix(archive_dir)}`。\n\n"
        f"收窄复核摘要已生成在 `{as_posix(summary_root)}`。\n"
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

    rows, encoding = read_csv_compatible(review_dir / "review_form.csv")
    manifest = load_json(review_dir / "review_manifest.json")
    tightening_records = load_jsonl(args.tightening_records)

    if len(rows) != 32:
        raise ValueError(f"expected 32 review rows, got {len(rows)}")
    if len(manifest) != 32:
        raise ValueError(f"expected 32 manifest records, got {len(manifest)}")
    if len(tightening_records) != 32:
        raise ValueError(f"expected 32 tightening records, got {len(tightening_records)}")

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
        tightening_records=tightening_records,
    )

    for target_root in (archive_dir, summary_root):
        write_json(target_root / "filled_review_summary.json", machine_summary)
        write_csv(
            target_root / "filled_review_summary.csv",
            summary_rows,
            [
                "序号",
                "样本编号",
                "新版ROI判断",
                "相对旧ROI是否更好",
                "问题类型",
                "备注",
                "问题分层",
                "面积减少比例",
                "基础ROI类型",
                "顶部收窄比例",
                "左侧收窄比例",
            ],
        )
        (target_root / "human_summary.md").write_text(human_summary, encoding="utf-8")

    reset_current_readme(current_dir, archive_dir, summary_root)
    return machine_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive fine ROI tightening review results.")
    parser.add_argument("--current-dir", type=Path, default=DEFAULT_CURRENT_DIR)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--summary-root", type=Path, default=DEFAULT_SUMMARY_ROOT)
    parser.add_argument("--tightening-records", type=Path, default=DEFAULT_TIGHTENING_RECORDS)
    parser.add_argument("--archive-name", default=None)
    return parser.parse_args()


def main() -> int:
    summary = archive_review(parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

