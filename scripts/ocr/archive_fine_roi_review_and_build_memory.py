from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import unicodedata
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


REVIEW_NAME = "fine_roi_review"
SCHEMA_VERSION = "drawing-number-calibration-memory-v1"
DEFAULT_CURRENT_DIR = ROOT / "local_data" / "review_inbox" / "current"
DEFAULT_ARCHIVE_ROOT = ROOT / "local_data" / "review_inbox" / "archive"
DEFAULT_MACHINE_RECORDS = ROOT / "local_data" / "ocr_fine_roi_experiment" / "fine_roi_records.jsonl"
DEFAULT_MEMORY_ROOT = ROOT / "local_data" / "drawing_number_calibration_memory"

FORM_FIELDS = ["序号", "样本编号", "细ROI判断", "图号判断", "人工确认图号", "备注"]
UNRESOLVED_MANUAL_VALUES = {"", "无法确认", "无法识别", "不确定", "看不清", "看不清楚"}


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


def normalize_drawing_number(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value)).strip().upper()
    normalized = normalized.replace("_", "-")
    normalized = normalized.replace("—", "-").replace("–", "-").replace("－", "-")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def is_unresolved_manual_value(value: str | None) -> bool:
    return normalize_drawing_number(value) in UNRESOLVED_MANUAL_VALUES


def canonical_drawing_judgment(value: str) -> str:
    clean = value.strip()
    if clean == "正确":
        return "correct"
    if clean in {"错误", "不正确", "有误"}:
        return "incorrect"
    if clean in {"未识别", "空白", "空", "无"}:
        return "missing"
    if clean in {"不确定", "看不清", "无法确认"}:
        return "uncertain"
    if not clean:
        return "blank"
    return "other"


def canonical_roi_judgment(value: str) -> str:
    clean = value.strip()
    mapping = {
        "正确": "correct",
        "范围太大": "too_large",
        "范围太小": "too_small",
        "位置错误": "wrong_position",
        "看不清": "unclear",
    }
    return mapping.get(clean, "other" if clean else "blank")


def record_by_sample(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record.get("sample_id")): record for record in records}


def top_candidate(machine_record: dict[str, Any] | None, key: str) -> str:
    if not machine_record:
        return ""
    section = machine_record.get(key) or {}
    return normalize_drawing_number(section.get("top_candidate"))


def candidate_score(machine_record: dict[str, Any] | None, key: str) -> float | None:
    if not machine_record:
        return None
    value = (machine_record.get(key) or {}).get("top_candidate_score")
    if value is None or value == "":
        return None
    return float(value)


def diff_operations(machine_value: str, manual_value: str) -> list[dict[str, str]]:
    if not machine_value or not manual_value or machine_value == manual_value:
        return []
    matcher = SequenceMatcher(a=machine_value, b=manual_value)
    operations: list[dict[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        machine_part = machine_value[i1:i2]
        manual_part = manual_value[j1:j2]
        operations.append(
            {
                "op": tag,
                "machine": machine_part,
                "manual": manual_part,
                "machine_span": f"{i1}:{i2}",
                "manual_span": f"{j1}:{j2}",
            }
        )
    return operations


def char_confusions(operations: list[dict[str, str]]) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for operation in operations:
        machine = operation["machine"]
        manual = operation["manual"]
        op = operation["op"]
        if op == "replace" and len(machine) == len(manual):
            for left, right in zip(machine, manual):
                pairs.append({"op": "replace", "machine": left, "manual": right})
            continue
        pairs.append({"op": op, "machine": machine, "manual": manual})
    return pairs


def parse_roi_feedback(note: str, fine_roi_judgment: str) -> tuple[list[str], list[str]]:
    text = note.strip()
    tags: list[str] = []
    suggestions: list[str] = []

    if fine_roi_judgment == "范围太大" or "范围太大" in text or "太大" in text:
        tags.append("roi_too_large")
    if "范围太小" in text:
        tags.append("roi_too_small")
    if "位置错误" in text:
        tags.append("roi_wrong_position")
    if "蓝色" in text and "更好" in text:
        tags.append("prefer_bottom_right_blue_roi")
        suggestions.append("优先评估蓝框右下区域候选")
    if "上侧" in text or "上部" in text or "上边" in text:
        tags.append("trim_top")
    if "左侧" in text:
        tags.append("trim_left")
    if "向右" in text:
        tags.append("shift_or_trim_left_toward_right")
    if "图号模糊" in text or "模糊" in text:
        tags.append("drawing_number_blurry")
    if "人工识别" in text:
        tags.append("requires_manual_identification")

    percentages = re.findall(r"(\d{1,3})\s*%", text)
    for percent in percentages:
        tags.append(f"percent_{percent}")
    if "trim_top" in tags:
        percent = percentages[0] if percentages else ""
        suggestions.append(f"上侧减少约{percent}%" if percent else "上侧适度收窄")
    if "trim_left" in tags or "shift_or_trim_left_toward_right" in tags:
        percent = percentages[0] if percentages else ""
        suggestions.append(f"左侧向右减少约{percent}%" if percent else "左侧向右适度收窄")
    if "drawing_number_blurry" in tags:
        suggestions.append("图号模糊样本保留人工识别或 VLM 兜底")

    return sorted(set(tags)), dedupe(suggestions)


def dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def classify_event_outcome(
    drawing_judgment: str,
    manual_number: str,
    fine_candidate: str,
    coarse_candidate: str,
) -> tuple[str, str | None]:
    canonical = canonical_drawing_judgment(drawing_judgment)
    manual_is_unresolved = is_unresolved_manual_value(manual_number)
    manual_normalized = normalize_drawing_number(manual_number)
    machine_candidate = fine_candidate or coarse_candidate

    if canonical == "correct":
        return "machine_confirmed", machine_candidate or None
    if canonical == "incorrect" and manual_normalized and not manual_is_unresolved:
        return "manual_corrected", manual_normalized
    if canonical == "missing" and manual_normalized and not manual_is_unresolved:
        return "manual_supplied_missing", manual_normalized
    if canonical in {"uncertain", "incorrect", "missing"}:
        return "unresolved_requires_manual_identification", None
    if manual_normalized and not manual_is_unresolved:
        return "manual_override_without_standard_judgment", manual_normalized
    return "unresolved_requires_manual_identification", None


def build_event(
    row: dict[str, str],
    machine_record: dict[str, Any] | None,
    review_session_id: str,
    archive_dir: Path,
    source_form_encoding: str,
) -> dict[str, Any]:
    sample_id = row.get("样本编号", "")
    fine_candidate = top_candidate(machine_record, "best_roi_ocr")
    coarse_candidate = top_candidate(machine_record, "coarse_ocr")
    manual_number = row.get("人工确认图号", "")
    outcome, final_number = classify_event_outcome(
        row.get("图号判断", ""),
        manual_number,
        fine_candidate,
        coarse_candidate,
    )
    compare_base = fine_candidate or coarse_candidate
    operations = diff_operations(compare_base, final_number or "")
    tags, suggestions = parse_roi_feedback(row.get("备注", ""), row.get("细ROI判断", ""))

    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": f"{review_session_id}:{sample_id}",
        "review_session_id": review_session_id,
        "sample_id": sample_id,
        "source_archive_dir": as_posix(archive_dir),
        "source_form_encoding": source_form_encoding,
        "fine_roi_judgment": row.get("细ROI判断", ""),
        "fine_roi_judgment_code": canonical_roi_judgment(row.get("细ROI判断", "")),
        "drawing_number_judgment": row.get("图号判断", ""),
        "drawing_number_judgment_code": canonical_drawing_judgment(row.get("图号判断", "")),
        "manual_confirmed_drawing_number_raw": manual_number,
        "manual_confirmed_drawing_number": normalize_drawing_number(manual_number),
        "machine_fine_candidate": fine_candidate,
        "machine_fine_candidate_score": candidate_score(machine_record, "best_roi_ocr"),
        "machine_coarse_candidate": coarse_candidate,
        "machine_coarse_candidate_score": candidate_score(machine_record, "coarse_ocr"),
        "machine_best_roi_name": (machine_record or {}).get("best_roi_name", ""),
        "machine_best_roi_area_ratio": (machine_record or {}).get("best_roi_area_ratio"),
        "machine_comparison_status": (machine_record or {}).get("comparison_status", ""),
        "machine_comparison_reasons": (machine_record or {}).get("comparison_reasons", []),
        "final_drawing_number": final_number,
        "calibration_outcome": outcome,
        "candidate_diff_operations": operations,
        "candidate_char_confusions": char_confusions(operations),
        "human_note": row.get("备注", ""),
        "roi_note_tags": tags,
        "roi_adjustment_suggestions": suggestions,
        "modified_pdf": False,
        "renamed_pdf": False,
    }


def load_existing_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return load_jsonl(path)


def merge_events(existing: list[dict[str, Any]], new_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for event in existing:
        event_id = str(event.get("event_id") or "")
        if event_id:
            merged[event_id] = event
    for event in new_events:
        merged[event["event_id"]] = event
    return sorted(merged.values(), key=lambda item: (str(item.get("review_session_id")), str(item.get("sample_id"))))


def counter_dict(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def build_patterns(events: list[dict[str, Any]], current_session_id: str) -> dict[str, Any]:
    all_events = list(events)
    current_events = [event for event in all_events if event.get("review_session_id") == current_session_id]
    roi_judgment_counts = Counter(event.get("fine_roi_judgment") or "空" for event in current_events)
    drawing_judgment_counts = Counter(event.get("drawing_number_judgment") or "空" for event in current_events)
    outcome_counts = Counter(event.get("calibration_outcome") or "unknown" for event in current_events)
    roi_tag_counts: Counter[str] = Counter()
    suggestion_counts: Counter[str] = Counter()
    confusion_counts: Counter[str] = Counter()

    correction_pairs: list[dict[str, Any]] = []
    unresolved_samples: list[str] = []
    machine_confirmed_samples: list[str] = []
    manual_corrected_samples: list[str] = []
    manual_supplied_missing_samples: list[str] = []

    for event in current_events:
        for tag in event.get("roi_note_tags") or []:
            roi_tag_counts[tag] += 1
        for suggestion in event.get("roi_adjustment_suggestions") or []:
            suggestion_counts[suggestion] += 1
        for confusion in event.get("candidate_char_confusions") or []:
            key = f"{confusion.get('op')}:{confusion.get('machine')}->{confusion.get('manual')}"
            confusion_counts[key] += 1

        outcome = event.get("calibration_outcome")
        sample = event.get("sample_id")
        if outcome == "machine_confirmed":
            machine_confirmed_samples.append(sample)
        elif outcome == "manual_corrected":
            manual_corrected_samples.append(sample)
        elif outcome == "manual_supplied_missing":
            manual_supplied_missing_samples.append(sample)
        elif outcome == "unresolved_requires_manual_identification":
            unresolved_samples.append(sample)

        if outcome in {"manual_corrected", "manual_supplied_missing"}:
            correction_pairs.append(
                {
                    "sample_id": sample,
                    "machine_fine_candidate": event.get("machine_fine_candidate"),
                    "machine_coarse_candidate": event.get("machine_coarse_candidate"),
                    "manual_confirmed_drawing_number": event.get("manual_confirmed_drawing_number"),
                    "final_drawing_number": event.get("final_drawing_number"),
                    "diff_operations": event.get("candidate_diff_operations") or [],
                    "human_note": event.get("human_note"),
                }
            )

    transplantable_rules = build_transplantable_rules(
        current_events=current_events,
        roi_tag_counts=roi_tag_counts,
        suggestion_counts=suggestion_counts,
        confusion_counts=confusion_counts,
        unresolved_samples=unresolved_samples,
    )
    resolved_events = [
        event
        for event in current_events
        if event.get("calibration_outcome")
        in {"machine_confirmed", "manual_corrected", "manual_supplied_missing", "manual_override_without_standard_judgment"}
    ]
    machine_confirmed_count = outcome_counts.get("machine_confirmed", 0)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_session_id": current_session_id,
        "event_count": len(all_events),
        "current_session_event_count": len(current_events),
        "current_session": {
            "roi_judgment_counts": counter_dict(roi_judgment_counts),
            "drawing_number_judgment_counts": counter_dict(drawing_judgment_counts),
            "calibration_outcome_counts": counter_dict(outcome_counts),
            "machine_confirmed_samples": machine_confirmed_samples,
            "manual_corrected_samples": manual_corrected_samples,
            "manual_supplied_missing_samples": manual_supplied_missing_samples,
            "unresolved_samples": unresolved_samples,
            "correction_pairs": correction_pairs,
            "roi_note_tag_counts": counter_dict(roi_tag_counts),
            "roi_adjustment_suggestion_counts": counter_dict(suggestion_counts),
            "candidate_confusion_counts": counter_dict(confusion_counts),
            "resolved_event_count": len(resolved_events),
            "machine_confirmed_rate_on_resolved": round(
                machine_confirmed_count / len(resolved_events), 6
            )
            if resolved_events
            else None,
        },
        "transplantable_rules": transplantable_rules,
        "modified_pdf": False,
        "renamed_pdf": False,
    }


def build_transplantable_rules(
    current_events: list[dict[str, Any]],
    roi_tag_counts: Counter[str],
    suggestion_counts: Counter[str],
    confusion_counts: Counter[str],
    unresolved_samples: list[str],
) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    total = len(current_events)
    if total and roi_tag_counts.get("roi_too_large", 0) / total >= 0.5:
        rules.append(
            {
                "rule_id": "roi-too-large-quality-gate",
                "type": "roi_feedback",
                "description": "当细 ROI 虽能识别图号但被人工反复标记范围太大时，不应只按图号命中自动放行，应继续收窄 ROI 或保留人工复核。",
                "support_count": roi_tag_counts.get("roi_too_large", 0),
            }
        )
    for suggestion, count in suggestion_counts.most_common():
        if count >= 2:
            rules.append(
                {
                    "rule_id": f"roi-adjustment-{len(rules) + 1}",
                    "type": "roi_adjustment",
                    "description": suggestion,
                    "support_count": count,
                }
            )
    for confusion, count in confusion_counts.most_common():
        if count >= 1:
            rules.append(
                {
                    "rule_id": f"ocr-confusion-{len(rules) + 1}",
                    "type": "ocr_candidate_diff",
                    "description": f"候选差异：{confusion}",
                    "support_count": count,
                }
            )
    if unresolved_samples:
        rules.append(
            {
                "rule_id": "manual-fallback-required",
                "type": "fallback",
                "description": "图号模糊或人工无法确认的样本不得自动命名，应保留人工识别或 VLM 兜底。",
                "support_count": len(unresolved_samples),
            }
        )
    return rules


def build_human_summary(patterns: dict[str, Any], archive_dir: Path) -> str:
    current = patterns["current_session"]
    lines = [
        "# 图号人工校正记忆摘要",
        "",
        "## 本轮概况",
        "",
        f"- 记忆事件：{patterns['current_session_event_count']} 条。",
        f"- 归档目录：`{as_posix(archive_dir)}`。",
        f"- PDF 修改：{patterns['modified_pdf']}。",
        f"- PDF 重命名：{patterns['renamed_pdf']}。",
        "",
        "## 人工判断统计",
        "",
        f"- 细 ROI 判断：{json.dumps(current['roi_judgment_counts'], ensure_ascii=False)}。",
        f"- 图号判断：{json.dumps(current['drawing_number_judgment_counts'], ensure_ascii=False)}。",
        f"- 校正结果：{json.dumps(current['calibration_outcome_counts'], ensure_ascii=False)}。",
        "",
        "## 可迁移规律",
        "",
    ]
    rules = patterns.get("transplantable_rules") or []
    if rules:
        lines.extend(f"- {rule['description']}（支持 {rule['support_count']} 条）。" for rule in rules)
    else:
        lines.append("- 暂无稳定规律。")
    lines.extend(
        [
            "",
            "## 仍需人工兜底样本",
            "",
        ]
    )
    unresolved = current.get("unresolved_samples") or []
    lines.append("- " + "、".join(unresolved) + "。" if unresolved else "- 无。")
    lines.extend(
        [
            "",
            "## 使用建议",
            "",
            "- 后续重建命名审核包前，可先读取 `portable_export/drawing_number_calibration_memory_v1.json`。",
            "- 该记忆库只提供校正事实和规律建议，不直接生成或重命名 PDF。",
            "",
        ]
    )
    return "\n".join(lines)


def event_csv_rows(events: list[dict[str, Any]], session_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        if event.get("review_session_id") != session_id:
            continue
        rows.append(
            {
                "sample_id": event.get("sample_id"),
                "fine_roi_judgment": event.get("fine_roi_judgment"),
                "drawing_number_judgment": event.get("drawing_number_judgment"),
                "machine_fine_candidate": event.get("machine_fine_candidate"),
                "machine_coarse_candidate": event.get("machine_coarse_candidate"),
                "manual_confirmed_drawing_number": event.get("manual_confirmed_drawing_number"),
                "final_drawing_number": event.get("final_drawing_number"),
                "calibration_outcome": event.get("calibration_outcome"),
                "roi_note_tags": ";".join(event.get("roi_note_tags") or []),
                "roi_adjustment_suggestions": ";".join(event.get("roi_adjustment_suggestions") or []),
                "human_note": event.get("human_note"),
            }
        )
    return rows


def unique_archive_dir(archive_root: Path, archive_name: str | None) -> Path:
    if archive_name:
        candidate = archive_root / archive_name
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = archive_root / f"{REVIEW_NAME}_{timestamp}_reviewed"
    if candidate.exists():
        raise FileExistsError(f"archive target already exists: {candidate}")
    return candidate


def validate_inputs(
    rows: list[dict[str, str]],
    manifest: list[dict[str, Any]],
    machine_records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    missing_fields = [field for field in FORM_FIELDS if any(field not in row for row in rows)]
    samples = [row.get("样本编号", "") for row in rows]
    duplicate_samples = sorted(sample for sample, count in Counter(samples).items() if count > 1)
    missing_machine_records = [sample for sample in samples if sample not in machine_records]
    if missing_fields:
        raise ValueError(f"review form missing required fields: {missing_fields}")
    if duplicate_samples:
        raise ValueError(f"duplicate samples in review form: {duplicate_samples}")
    if len(rows) != len(manifest):
        raise ValueError(f"review row count {len(rows)} does not match manifest count {len(manifest)}")
    if missing_machine_records:
        raise ValueError(f"missing machine records: {missing_machine_records}")
    return {
        "record_count": len(rows),
        "manifest_count": len(manifest),
        "missing_fields": missing_fields,
        "missing_machine_records": missing_machine_records,
    }


def reset_current_readme(current_dir: Path, archive_dir: Path, memory_root: Path) -> None:
    current_dir.mkdir(parents=True, exist_ok=True)
    readme = (
        "# 当前审核入口\n\n"
        "当前没有待用户审核、填写或标注的文件。\n\n"
        f"上一轮细 ROI 与图号候选复核已归档到 `{as_posix(archive_dir)}`。\n\n"
        f"图号人工校正记忆库已生成在 `{as_posix(memory_root)}`。\n"
    )
    (current_dir / "README.md").write_text(readme, encoding="utf-8")


def build_memory(args: argparse.Namespace) -> dict[str, Any]:
    current_dir = ensure_inside(resolve_path(args.current_dir), ROOT)
    archive_root = ensure_inside(resolve_path(args.archive_root), ROOT)
    memory_root = ensure_inside(resolve_path(args.memory_root), ROOT)
    machine_records_path = resolve_path(args.machine_records)
    review_dir = ensure_inside(current_dir / REVIEW_NAME, current_dir)
    archive_dir = ensure_inside(unique_archive_dir(archive_root, args.archive_name), archive_root)

    if not review_dir.exists():
        raise FileNotFoundError(f"review directory does not exist: {review_dir}")
    form_path = review_dir / "review_form.csv"
    manifest_path = review_dir / "review_manifest.json"
    rows, encoding = read_csv_compatible(form_path)
    manifest = load_json(manifest_path)
    machine_records = record_by_sample(load_jsonl(machine_records_path))
    validation = validate_inputs(rows, manifest, machine_records)
    review_session_id = archive_dir.name

    new_events = [
        build_event(
            row=row,
            machine_record=machine_records.get(row.get("样本编号", "")),
            review_session_id=review_session_id,
            archive_dir=archive_dir,
            source_form_encoding=encoding,
        )
        for row in rows
    ]
    existing_events_path = memory_root / "memory_events.jsonl"
    merged_events = merge_events(load_existing_events(existing_events_path), new_events)
    patterns = build_patterns(merged_events, review_session_id)
    human_summary = build_human_summary(patterns, archive_dir)

    archive_dir.mkdir(parents=True)
    current_readme = current_dir / "README.md"
    if current_readme.exists():
        shutil.copy2(current_readme, archive_dir / "README.md")
    archived_review_dir = archive_dir / REVIEW_NAME
    shutil.move(str(review_dir), str(archived_review_dir))

    portable_dir = memory_root / "portable_export"
    write_jsonl(existing_events_path, merged_events)
    write_json(memory_root / "memory_patterns.json", patterns)
    (memory_root / "memory_patterns.md").write_text(human_summary, encoding="utf-8")
    write_csv(
        memory_root / "current_session_events.csv",
        event_csv_rows(merged_events, review_session_id),
        [
            "sample_id",
            "fine_roi_judgment",
            "drawing_number_judgment",
            "machine_fine_candidate",
            "machine_coarse_candidate",
            "manual_confirmed_drawing_number",
            "final_drawing_number",
            "calibration_outcome",
            "roi_note_tags",
            "roi_adjustment_suggestions",
            "human_note",
        ],
    )
    write_json(
        portable_dir / "drawing_number_calibration_memory_v1.json",
        {
            "schema_version": SCHEMA_VERSION,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "patterns": patterns,
            "events": merged_events,
            "modified_pdf": False,
            "renamed_pdf": False,
        },
    )
    (portable_dir / "drawing_number_calibration_rules.md").write_text(human_summary, encoding="utf-8")

    archive_summary = {
        "review_name": REVIEW_NAME,
        "review_session_id": review_session_id,
        "archive_dir": as_posix(archive_dir),
        "archived_review_dir": as_posix(archived_review_dir),
        "review_form_encoding": encoding,
        "machine_records": as_posix(machine_records_path),
        "memory_root": as_posix(memory_root),
        "memory_events": as_posix(existing_events_path),
        "memory_patterns": as_posix(memory_root / "memory_patterns.json"),
        "portable_export": as_posix(portable_dir / "drawing_number_calibration_memory_v1.json"),
        "validation": validation,
        "current_session_summary": patterns["current_session"],
        "modified_pdf": False,
        "renamed_pdf": False,
    }
    write_json(archive_dir / "filled_review_summary.json", archive_summary)
    write_csv(
        archive_dir / "filled_review_summary.csv",
        event_csv_rows(merged_events, review_session_id),
        [
            "sample_id",
            "fine_roi_judgment",
            "drawing_number_judgment",
            "machine_fine_candidate",
            "machine_coarse_candidate",
            "manual_confirmed_drawing_number",
            "final_drawing_number",
            "calibration_outcome",
            "roi_note_tags",
            "roi_adjustment_suggestions",
            "human_note",
        ],
    )
    (archive_dir / "human_summary.md").write_text(human_summary, encoding="utf-8")
    reset_current_readme(current_dir, archive_dir, memory_root)
    return archive_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive fine ROI review results and build drawing-number calibration memory."
    )
    parser.add_argument("--current-dir", type=Path, default=DEFAULT_CURRENT_DIR)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--memory-root", type=Path, default=DEFAULT_MEMORY_ROOT)
    parser.add_argument("--machine-records", type=Path, default=DEFAULT_MACHINE_RECORDS)
    parser.add_argument("--archive-name", default=None)
    return parser.parse_args()


def main() -> int:
    result = build_memory(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

