from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_ARBITRATION_RECORDS = (
    ROOT / "local_data" / "title_block_arbitration" / "arbitration_records.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "pdf_correction_dry_run"

RECORD_VERSION = "0.2"
DRAWING_NUMBER_RULE_VERSION = "drawing-number-regex-context-v0.2"
WINDOW_AFTER_LABEL_CHARS = 90
DRAWING_NUMBER_PATTERN = re.compile(
    r"\b[A-Z]{1,8}[A-Z0-9]{0,8}(?:[-_][A-Z0-9]{1,12}){2,8}\b",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(r"^\d{4}[-/.年]\d{1,2}([-/.\u6708]\d{1,2}(\u65e5)?)?$")
IP_OR_PATH_PATTERN = re.compile(r"(\\\\|/|\\|\b\d{1,3}(?:\.\d{1,3}){3}\b)")
ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
TITLE_FLOW_PATTERN = re.compile(r"(标记处数|更改文件号|更改文.号|签字|日期|设计|审核)")
PART_LIST_PATTERN = re.compile(r"(序号|数量|材料|备注|见本图|组件|焊接件|矩形管|油缸)")
PATH_CONTEXT_PATTERN = re.compile(
    r"(\\\\|\\|\b\d{1,3}(?:\.\d{1,3}){3}\b|\.ipt|\.idw|\.dwg|\.idu|三维模型|Attachment|Forklift)",
    re.IGNORECASE,
)
CHINESE_NAME_BEFORE_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,12}\s*$")
PROJECT_PREFIX_PATTERN = re.compile(r"^[A-Z]{2,6}\d{2,5}")


def as_posix(path: Path | str | None) -> str | None:
    if path is None:
        return None
    path_obj = Path(path)
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


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


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def source_exists(path_value: str | None) -> bool:
    if not path_value:
        return False
    return resolve_path(Path(path_value)).exists()


def ensure_text_file(output_dir: Path, record_id: str, text: str) -> str | None:
    if not text:
        return None
    safe_name = safe_record_name(record_id)
    text_path = output_dir / "ocr" / f"{safe_name}.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(text, encoding="utf-8")
    return as_posix(text_path)


def safe_record_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "__", value).strip("._")
    return safe or "record"


def normalize_ocr_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def clean_candidate(value: str) -> str:
    value = value.strip().upper()
    value = value.replace("_", "-")
    value = re.sub(r"^[^A-Z0-9]+|[^A-Z0-9]+$", "", value)
    return value


def looks_like_noise(value: str) -> bool:
    if not value:
        return True
    if len(value) < 6:
        return True
    if DATE_PATTERN.match(value):
        return True
    if IP_OR_PATH_PATTERN.search(value):
        return True
    if value.count("-") < 2:
        return True
    if not re.search(r"[A-Z]", value):
        return True
    if not re.search(r"\d", value):
        return True
    return False


def candidate_context(text: str, start: int, end: int) -> str:
    left = max(0, start - 24)
    right = min(len(text), end + 24)
    return " ".join(text[left:right].split())


def nearby_text(text: str, start: int, end: int, before: int = 48, after: int = 48) -> str:
    left = max(0, start - before)
    right = min(len(text), end + after)
    return text[left:right]


def score_candidate(
    value: str,
    source: str,
    text: str,
    start: int,
    end: int,
) -> tuple[float, list[str], list[str]]:
    reasons: list[str] = [source]
    penalties: list[str] = []
    score = 0.62 if source == "global_pattern" else 0.82

    before = text[max(0, start - 48):start]
    after = text[end:min(len(text), end + 72)]
    context = nearby_text(text, start, end, before=64, after=80)
    segment_count = value.count("-") + 1

    if source == "near_label":
        score += 0.08
        reasons.append("near_drawing_number_label")
    if CHINESE_NAME_BEFORE_PATTERN.search(before):
        score += 0.16
        reasons.append("after_chinese_drawing_name")
    if TITLE_FLOW_PATTERN.search(after):
        score += 0.16
        reasons.append("before_title_block_flow_fields")
    if PROJECT_PREFIX_PATTERN.search(value):
        score += 0.04
        reasons.append("project_prefix")
    if segment_count >= 4:
        score += 0.04
        reasons.append("multi_segment_number")

    if PATH_CONTEXT_PATTERN.search(context):
        score -= 0.35
        penalties.append("cad_or_path_context")
    if source == "global_pattern" and PART_LIST_PATTERN.search(context):
        score -= 0.12
        penalties.append("part_list_context")
    if re.search(r"[0-9][A-Z]|[A-Z][0-9]", value) is None:
        score -= 0.08
        penalties.append("weak_alnum_mix")
    if len(value) < 9:
        score -= 0.08
        penalties.append("short_candidate")

    score = max(0.0, min(0.99, round(score, 4)))
    return score, reasons, penalties


def drawing_number_candidates(ocr_text: str) -> list[dict[str, Any]]:
    text = normalize_ocr_text(ocr_text)
    if not text:
        return []

    candidates: dict[str, dict[str, Any]] = {}

    def add_candidate(raw: str, source: str, start: int, end: int) -> None:
        value = clean_candidate(raw)
        if looks_like_noise(value):
            return
        existing = candidates.get(value)
        context = candidate_context(text, start, end)
        score, reasons, penalties = score_candidate(value, source, text, start, end)
        if score < 0.35:
            return
        item = {
            "value": value,
            "score": score,
            "source": source,
            "context": context,
            "reasons": reasons,
            "penalties": penalties,
        }
        if existing is None or score > float(existing["score"]):
            candidates[value] = item

    label_pattern = re.compile(r"(图号/规格|图样代号|图号|代号)", re.IGNORECASE)
    for label_match in label_pattern.finditer(text):
        window_start = label_match.end()
        window_end = min(len(text), window_start + WINDOW_AFTER_LABEL_CHARS)
        window = text[window_start:window_end]
        for match in DRAWING_NUMBER_PATTERN.finditer(window):
            add_candidate(
                match.group(0),
                "near_label",
                window_start + match.start(),
                window_start + match.end(),
            )

    for match in DRAWING_NUMBER_PATTERN.finditer(text):
        add_candidate(match.group(0), "global_pattern", match.start(), match.end())

    ordered = sorted(candidates.values(), key=lambda item: (-float(item["score"]), item["value"]))
    return ordered


def sanitize_filename(value: str | None) -> tuple[str | None, list[str]]:
    if not value:
        return None, ["drawing_number_missing"]
    stripped = value.strip()
    sanitized = ILLEGAL_FILENAME_CHARS.sub("_", stripped)
    sanitized = re.sub(r"\s+", "_", sanitized).strip(" ._")
    risks: list[str] = []
    if not sanitized:
        risks.append("filename_empty_after_sanitization")
        return None, risks
    if sanitized != stripped:
        risks.append("filename_changed_by_sanitization")
    if len(sanitized) > 120:
        sanitized = sanitized[:120].rstrip(" ._")
        risks.append("filename_truncated")
    return sanitized, risks


def corrected_pdf_candidate_path(output_dir: Path, record: dict[str, Any]) -> str:
    sample = record["sample_id"]
    return as_posix(output_dir / "corrected_pdfs" / f"{safe_record_name(sample)}.pdf") or ""


def renamed_pdf_candidate_path(output_dir: Path, filename_safe_value: str | None) -> str | None:
    if not filename_safe_value:
        return None
    return as_posix(output_dir / "renamed_pdfs" / f"{filename_safe_value}.pdf")


def build_rotation_plan(
    record: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    page = record.get("page") or {}
    arbitration = record.get("arbitration") or {}
    rotation = record.get("rotation") or {}
    blockers: list[str] = []

    if arbitration.get("decision_status") != "auto_accept":
        blockers.append("arbitration_not_auto_accept")
    single_page_pdf_path = page.get("single_page_pdf_path")
    if not single_page_pdf_path:
        blockers.append("missing_single_page_pdf_path")
    elif not source_exists(single_page_pdf_path):
        blockers.append("single_page_pdf_path_not_found")
    correction_degrees = rotation.get("correction_degrees")
    if correction_degrees is None:
        blockers.append("missing_correction_degrees")

    candidate_path = corrected_pdf_candidate_path(output_dir, record)
    would_overwrite = source_exists(candidate_path)
    if would_overwrite:
        blockers.append("corrected_pdf_candidate_would_overwrite")

    return {
        "can_rotate_pdf": len(blockers) == 0,
        "would_rotate_degrees": correction_degrees,
        "corrected_pdf_candidate_path": candidate_path,
        "dry_run_only": True,
        "would_overwrite": would_overwrite,
        "blockers": blockers,
    }


def build_title_block_crop(record: dict[str, Any]) -> dict[str, Any]:
    page = record.get("page") or {}
    ocr = record.get("ocr") or {}
    crop_path = ocr.get("title_block_crop_path")
    normalized_crop_path = ocr.get("normalized_crop_path")
    blockers: list[str] = []
    if not crop_path:
        blockers.append("missing_title_block_crop")
    elif not source_exists(crop_path):
        blockers.append("title_block_crop_not_found")

    return {
        "can_crop": bool(crop_path) and not blockers,
        "source_image_path": page.get("rendered_image_path"),
        "crop_path": crop_path,
        "normalized_crop_path": normalized_crop_path,
        "crop_source": "arbitration_record_ocr_crop" if crop_path else None,
        "blockers": blockers,
    }


def build_ocr_record(record: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    evidence = record.get("evidence") or {}
    evidence_ocr = evidence.get("ocr") or {}
    ocr = record.get("ocr") or {}
    text = ocr.get("ocr_text") or ""
    text_path = ensure_text_file(output_dir, record.get("record_id", ""), text)
    blockers: list[str] = []
    if not text:
        blockers.append("missing_ocr_text")
    if evidence_ocr.get("field_cluster_level") not in {"strong"}:
        blockers.append("ocr_field_cluster_not_strong")

    return {
        "ocr_engine": evidence_ocr.get("engine"),
        "ocr_status": evidence_ocr.get("status"),
        "ocr_text_path": text_path,
        "ocr_text_excerpt": " ".join(text.split())[:160],
        "field_cluster_hits": ocr.get("field_cluster_hits") or {},
        "ocr_confidence": ocr.get("ocr_confidence"),
        "blockers": blockers,
    }


def build_drawing_number(record: dict[str, Any]) -> dict[str, Any]:
    ocr = record.get("ocr") or {}
    candidates = drawing_number_candidates(ocr.get("ocr_text") or "")
    blockers: list[str] = []
    selected = None
    selection_status = "missing"
    confidence = None

    if not candidates:
        blockers.append("drawing_number_missing")
    elif len(candidates) == 1:
        selected = candidates[0]["value"]
        confidence = candidates[0]["score"]
        if confidence >= 0.9:
            selection_status = "single_high_confidence_candidate"
        else:
            selection_status = "single_candidate"
    else:
        top_score = float(candidates[0]["score"])
        second_score = float(candidates[1]["score"])
        if top_score >= 0.9 and top_score - second_score >= 0.18:
            selected = candidates[0]["value"]
            confidence = top_score
            selection_status = "single_high_confidence_candidate"
        else:
            selection_status = "ambiguous"
            blockers.append("drawing_number_ambiguous")

    if confidence is not None and confidence < 0.9:
        blockers.append("drawing_number_low_confidence")

    return {
        "candidates": candidates,
        "selected_candidate": selected,
        "selection_status": selection_status,
        "confidence": confidence,
        "extraction_rule_version": DRAWING_NUMBER_RULE_VERSION,
        "blockers": blockers,
    }


def build_rename_plan(
    record: dict[str, Any],
    drawing_number: dict[str, Any],
    rotation_plan: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    selected = drawing_number.get("selected_candidate")
    filename_safe_value, sanitization_risks = sanitize_filename(selected)
    target = renamed_pdf_candidate_path(output_dir, filename_safe_value)
    blockers: list[str] = list(drawing_number.get("blockers") or [])
    blockers.extend(
        risk for risk in sanitization_risks if risk not in blockers
    )
    if not rotation_plan.get("can_rotate_pdf"):
        blockers.append("upstream_rotation_blocked")
    would_overwrite = source_exists(target) if target else False
    if would_overwrite:
        blockers.append("renamed_pdf_candidate_would_overwrite")
    blockers = sorted(set(blockers))

    return {
        "can_rename": len(blockers) == 0,
        "filename_safe_value": filename_safe_value,
        "renamed_pdf_candidate_path": target,
        "would_overwrite": would_overwrite,
        "duplicate_name_group": None,
        "illegal_character_removed": "filename_changed_by_sanitization" in sanitization_risks,
        "blockers": blockers,
    }


def build_review_routing(
    rotation_plan: dict[str, Any],
    title_block_crop: dict[str, Any],
    ocr: dict[str, Any],
    drawing_number: dict[str, Any],
    rename_plan: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    reasons.extend(rotation_plan.get("blockers") or [])
    reasons.extend(title_block_crop.get("blockers") or [])
    reasons.extend(ocr.get("blockers") or [])
    reasons.extend(drawing_number.get("blockers") or [])
    reasons.extend(rename_plan.get("blockers") or [])
    reasons = sorted(set(reasons))

    if rename_plan.get("can_rename"):
        route = "auto_dry_run_ready"
    elif "arbitration_not_auto_accept" in reasons or "drawing_number_ambiguous" in reasons:
        route = "needs_human_review"
    else:
        route = "blocked"

    return {
        "route": route,
        "route_reasons": reasons,
        "human_visible_fields": [
            "sample_id",
            "rendered_image_path",
            "title_block_position",
            "correction_degrees",
            "title_block_crop_path",
            "ocr_text_excerpt",
            "drawing_number_candidates",
            "route_reasons",
        ],
    }


def build_dry_run_record(record: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    page = record.get("page") or {}
    arbitration = record.get("arbitration") or {}
    rotation = record.get("rotation") or {}
    rotation_plan = build_rotation_plan(record, output_dir)
    title_block_crop = build_title_block_crop(record)
    ocr_record = build_ocr_record(record, output_dir)
    drawing_number = build_drawing_number(record)
    rename_plan = build_rename_plan(record, drawing_number, rotation_plan, output_dir)
    review_routing = build_review_routing(
        rotation_plan,
        title_block_crop,
        ocr_record,
        drawing_number,
        rename_plan,
    )

    return {
        "record_version": RECORD_VERSION,
        "record_id": record.get("record_id"),
        "sample_id": record.get("sample_id"),
        "input": {
            "source_pdf_path": page.get("source_pdf_path"),
            "page_index": page.get("page_index"),
            "single_page_pdf_path": page.get("single_page_pdf_path"),
            "rendered_image_path": page.get("rendered_image_path"),
            "arbitration_record_path": (record.get("artifacts") or {}).get(
                "arbitration_record_path"
            ),
        },
        "arbitration": {
            "decision_status": arbitration.get("decision_status"),
            "title_block_position": arbitration.get("title_block_position"),
            "detected_rotation_degrees": rotation.get("detected_rotation_degrees"),
            "correction_degrees": rotation.get("correction_degrees"),
            "confidence_level": arbitration.get("confidence_level"),
            "decision_reasons": arbitration.get("decision_reasons") or [],
        },
        "rotation_plan": rotation_plan,
        "title_block_crop": title_block_crop,
        "ocr": ocr_record,
        "drawing_number": drawing_number,
        "rename_plan": rename_plan,
        "review_routing": review_routing,
        "artifacts": {
            "source_arbitration_record_id": record.get("record_id"),
            "source_arbitration_record_path": (record.get("artifacts") or {}).get(
                "arbitration_record_path"
            ),
            "dry_run_record_path": as_posix(output_dir / "dry_run_records.jsonl"),
        },
    }


def apply_duplicate_name_risks(records: list[dict[str, Any]]) -> None:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        filename = (record.get("rename_plan") or {}).get("filename_safe_value")
        if filename:
            groups[filename].append(record)

    for filename, group in groups.items():
        if len(group) <= 1:
            continue
        group_id = f"duplicate:{filename}"
        for record in group:
            rename_plan = record["rename_plan"]
            rename_plan["duplicate_name_group"] = group_id
            if "duplicate_filename_candidate" not in rename_plan["blockers"]:
                rename_plan["blockers"].append("duplicate_filename_candidate")
            rename_plan["can_rename"] = False
            routing = record["review_routing"]
            if "duplicate_filename_candidate" not in routing["route_reasons"]:
                routing["route_reasons"].append("duplicate_filename_candidate")
                routing["route_reasons"] = sorted(set(routing["route_reasons"]))
            if routing["route"] == "auto_dry_run_ready":
                routing["route"] = "needs_human_review"


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    route_counts: Counter[str] = Counter()
    rotation_blockers: Counter[str] = Counter()
    crop_blockers: Counter[str] = Counter()
    ocr_blockers: Counter[str] = Counter()
    drawing_blockers: Counter[str] = Counter()
    rename_blockers: Counter[str] = Counter()
    candidate_counts: Counter[str] = Counter()

    for record in records:
        route_counts[record["review_routing"]["route"]] += 1
        candidate_counts[record["drawing_number"]["selection_status"]] += 1
        for blocker in record["rotation_plan"].get("blockers") or []:
            rotation_blockers[blocker] += 1
        for blocker in record["title_block_crop"].get("blockers") or []:
            crop_blockers[blocker] += 1
        for blocker in record["ocr"].get("blockers") or []:
            ocr_blockers[blocker] += 1
        for blocker in record["drawing_number"].get("blockers") or []:
            drawing_blockers[blocker] += 1
        for blocker in record["rename_plan"].get("blockers") or []:
            rename_blockers[blocker] += 1

    return {
        "record_count": len(records),
        "route_counts": dict(sorted(route_counts.items())),
        "drawing_number_selection_counts": dict(sorted(candidate_counts.items())),
        "rotation_blocker_counts": dict(sorted(rotation_blockers.items())),
        "title_block_crop_blocker_counts": dict(sorted(crop_blockers.items())),
        "ocr_blocker_counts": dict(sorted(ocr_blockers.items())),
        "drawing_number_blocker_counts": dict(sorted(drawing_blockers.items())),
        "rename_blocker_counts": dict(sorted(rename_blockers.items())),
        "dry_run_only": True,
        "modified_pdf": False,
        "renamed_pdf": False,
    }


def summary_csv_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        rows.append(
            {
                "record_id": record["record_id"],
                "sample_id": record["sample_id"],
                "route": record["review_routing"]["route"],
                "decision_status": record["arbitration"]["decision_status"],
                "title_block_position": record["arbitration"]["title_block_position"],
                "correction_degrees": record["arbitration"]["correction_degrees"],
                "can_rotate_pdf": record["rotation_plan"]["can_rotate_pdf"],
                "can_crop": record["title_block_crop"]["can_crop"],
                "ocr_status": record["ocr"]["ocr_status"],
                "drawing_number_status": record["drawing_number"]["selection_status"],
                "selected_drawing_number": record["drawing_number"]["selected_candidate"],
                "can_rename": record["rename_plan"]["can_rename"],
                "filename_safe_value": record["rename_plan"]["filename_safe_value"],
                "route_reasons": ";".join(record["review_routing"]["route_reasons"]),
            }
        )
    return rows


def issue_rows(records: list[dict[str, Any]], issue_source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        if issue_source == "rotation":
            issues = record["rotation_plan"].get("blockers") or []
        elif issue_source == "rename":
            issues = record["rename_plan"].get("blockers") or []
        else:
            issues = record["review_routing"].get("route_reasons") or []
        for issue in issues:
            rows.append(
                {
                    "record_id": record["record_id"],
                    "sample_id": record["sample_id"],
                    "route": record["review_routing"]["route"],
                    "issue": issue,
                    "selected_drawing_number": record["drawing_number"]["selected_candidate"],
                    "filename_safe_value": record["rename_plan"]["filename_safe_value"],
                }
            )
    return rows


def drawing_number_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        candidates = record["drawing_number"].get("candidates") or []
        if not candidates:
            rows.append(
                {
                    "record_id": record["record_id"],
                    "sample_id": record["sample_id"],
                    "candidate": "",
                    "score": "",
                    "source": "",
                    "selection_status": record["drawing_number"]["selection_status"],
                    "selected": "",
                    "context": "",
                    "reasons": "",
                    "penalties": "",
                }
            )
            continue
        for candidate in candidates:
            rows.append(
                {
                    "record_id": record["record_id"],
                    "sample_id": record["sample_id"],
                    "candidate": candidate["value"],
                    "score": candidate["score"],
                    "source": candidate["source"],
                    "selection_status": record["drawing_number"]["selection_status"],
                    "selected": candidate["value"]
                    == record["drawing_number"].get("selected_candidate"),
                    "context": candidate["context"],
                    "reasons": ";".join(candidate.get("reasons") or []),
                    "penalties": ";".join(candidate.get("penalties") or []),
                }
            )
    return rows


def build(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_records = load_jsonl(args.arbitration_records)
    dry_run_records = [
        build_dry_run_record(record, output_dir) for record in source_records
    ]
    apply_duplicate_name_risks(dry_run_records)
    summary = summarize(dry_run_records)

    records_path = output_dir / "dry_run_records.jsonl"
    summary_json_path = output_dir / "dry_run_summary.json"
    summary_csv_path = output_dir / "dry_run_summary.csv"
    rotation_plan_path = output_dir / "rotation_plan.csv"
    drawing_candidates_path = output_dir / "drawing_number_candidates.csv"
    naming_risks_path = output_dir / "naming_risks.csv"
    needs_review_path = output_dir / "needs_review.csv"

    write_jsonl(records_path, dry_run_records)
    write_json(summary_json_path, summary)
    write_csv(
        summary_csv_path,
        summary_csv_rows(dry_run_records),
        [
            "record_id",
            "sample_id",
            "route",
            "decision_status",
            "title_block_position",
            "correction_degrees",
            "can_rotate_pdf",
            "can_crop",
            "ocr_status",
            "drawing_number_status",
            "selected_drawing_number",
            "can_rename",
            "filename_safe_value",
            "route_reasons",
        ],
    )
    write_csv(
        rotation_plan_path,
        issue_rows(dry_run_records, "rotation"),
        ["record_id", "sample_id", "route", "issue", "selected_drawing_number", "filename_safe_value"],
    )
    write_csv(
        drawing_candidates_path,
        drawing_number_rows(dry_run_records),
        [
            "record_id",
            "sample_id",
            "candidate",
            "score",
            "source",
            "selection_status",
            "selected",
            "context",
            "reasons",
            "penalties",
        ],
    )
    write_csv(
        naming_risks_path,
        issue_rows(dry_run_records, "rename"),
        ["record_id", "sample_id", "route", "issue", "selected_drawing_number", "filename_safe_value"],
    )
    write_csv(
        needs_review_path,
        [
            row
            for row in summary_csv_rows(dry_run_records)
            if row["route"] != "auto_dry_run_ready"
        ],
        [
            "record_id",
            "sample_id",
            "route",
            "decision_status",
            "title_block_position",
            "correction_degrees",
            "can_rotate_pdf",
            "can_crop",
            "ocr_status",
            "drawing_number_status",
            "selected_drawing_number",
            "can_rename",
            "filename_safe_value",
            "route_reasons",
        ],
    )

    return {
        "output_dir": as_posix(output_dir),
        "dry_run_records": as_posix(records_path),
        "dry_run_summary": as_posix(summary_json_path),
        "dry_run_summary_csv": as_posix(summary_csv_path),
        "rotation_plan": as_posix(rotation_plan_path),
        "drawing_number_candidates": as_posix(drawing_candidates_path),
        "naming_risks": as_posix(naming_risks_path),
        "needs_review": as_posix(needs_review_path),
        "summary": summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build read-only PDF correction and drawing-number dry-run records."
    )
    parser.add_argument(
        "--arbitration-records",
        type=Path,
        default=DEFAULT_ARBITRATION_RECORDS,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    result = build(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

