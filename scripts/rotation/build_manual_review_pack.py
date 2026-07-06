from __future__ import annotations

import csv
import html
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH_PATH = ROOT / "local_data" / "ground_truth" / "rotation_ground_truth.json"
EVALUATION_DETAILS_PATH = ROOT / "outputs" / "rotation-detection" / "evaluation" / "evaluation_details.csv"
PNG_DIR = ROOT / "local_data" / "experiment_samples" / "all" / "png"
OUTPUT_DIR = ROOT / "outputs" / "rotation-detection" / "manual_review"
HTML_OUTPUT = OUTPUT_DIR / "review_index.html"
FORM_CSV_OUTPUT = OUTPUT_DIR / "review_form.csv"
JSON_OUTPUT = OUTPUT_DIR / "review_sheet.json"


POSITION_LABELS = {
    "bottom": "下方或右下方",
    "left": "左侧",
    "top": "上方或左上方",
    "right": "右侧或右上方",
}

POSITION_OPTIONS = "bottom/left/top/right"
ROTATION_OPTIONS = "0/90/180/270"


@dataclass
class ReviewRecord:
    sample: str
    image_path: str
    candidate_position: str
    candidate_rotation_degrees: int
    opencv_position: str
    opencv_rotation_degrees: int
    opencv_confidence: float
    needs_review: bool
    source_level: str
    source_basis: str
    verified_by_human: bool
    priority: int
    human_status: str
    human_corrected_position: str
    human_corrected_rotation_degrees: str
    human_note: str


def load_ground_truth() -> list[dict]:
    if not GROUND_TRUTH_PATH.exists():
        raise SystemExit(f"Ground truth file does not exist: {GROUND_TRUTH_PATH}")
    return json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))


def load_evaluation_details() -> dict[str, dict]:
    if not EVALUATION_DETAILS_PATH.exists():
        raise SystemExit(f"Evaluation details file does not exist: {EVALUATION_DETAILS_PATH}")
    with EVALUATION_DETAILS_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["sample"]: row for row in csv.DictReader(handle)}


def image_for_sample(sample: str) -> Path:
    matches = sorted(PNG_DIR.glob(f"*{sample}.png"))
    if not matches:
        raise SystemExit(f"No PNG image found for {sample} in {PNG_DIR}")
    return matches[0]


def priority_for(row: dict, verified_by_human: bool) -> int:
    if row["needs_review"].lower() == "true":
        return 0
    if not verified_by_human:
        return 1
    return 2


def build_records() -> list[ReviewRecord]:
    details_by_sample = load_evaluation_details()
    records: list[ReviewRecord] = []

    for truth in load_ground_truth():
        sample = truth["sample"]
        detail = details_by_sample.get(sample)
        if detail is None:
            raise SystemExit(f"No evaluation detail found for {sample}")

        image_path = image_for_sample(sample)
        verified_by_human = bool(truth["verified_by_human"])
        records.append(
            ReviewRecord(
                sample=sample,
                image_path=str(image_path.relative_to(ROOT)),
                candidate_position=truth["title_block_position"],
                candidate_rotation_degrees=int(truth["rotation_degrees"]),
                opencv_position=detail["predicted_position"],
                opencv_rotation_degrees=int(detail["predicted_rotation_degrees"]),
                opencv_confidence=float(detail["confidence"]),
                needs_review=detail["needs_review"].lower() == "true",
                source_level=truth["source_level"],
                source_basis=truth["source_basis"],
                verified_by_human=verified_by_human,
                priority=priority_for(detail, verified_by_human),
                human_status="",
                human_corrected_position="",
                human_corrected_rotation_degrees="",
                human_note="",
            )
        )

    return sorted(records, key=lambda item: (item.priority, item.opencv_confidence, item.sample))


def write_form_csv(records: list[ReviewRecord]) -> None:
    rows = []
    for index, record in enumerate(records, start=1):
        rows.append(
            {
                "序号": index,
                "样本编号": record.sample,
                "候选标题栏位置": POSITION_LABELS.get(record.candidate_position, record.candidate_position),
                "候选旋转角度": record.candidate_rotation_degrees,
                "人工判断": "",
                "正确标题栏位置": "",
                "正确旋转角度": "",
                "备注": "",
            }
        )

    with FORM_CSV_OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(records: list[ReviewRecord]) -> None:
    JSON_OUTPUT.write_text(
        json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def badge(text: str, kind: str) -> str:
    return f'<span class="badge {kind}">{html.escape(text)}</span>'


def record_card(record: ReviewRecord) -> str:
    image_src = Path(record.image_path).as_posix()
    relative_image_src = f"../../../{image_src}"
    source_kind = "manual" if record.verified_by_human else "consensus"
    review_badge = badge("需要复核", "warn") if record.needs_review else badge("无需复核", "ok")
    source_badge = badge("已人工看过" if record.verified_by_human else "待人工确认", source_kind)
    position_label = POSITION_LABELS.get(record.candidate_position, record.candidate_position)
    return f"""
    <article class="card">
      <a class="image-link" href="{html.escape(relative_image_src)}" target="_blank">
        <img src="{html.escape(relative_image_src)}" alt="{html.escape(record.sample)}">
      </a>
      <div class="meta">
        <div class="topline">
          <h2>{html.escape(record.sample)}</h2>
          <div>{review_badge}{source_badge}</div>
        </div>
        <dl>
          <dt>候选标题栏位置</dt><dd>{html.escape(position_label)}</dd>
          <dt>候选旋转角度</dt><dd>{record.candidate_rotation_degrees} 度</dd>
          <dt>样本编号</dt><dd>{html.escape(record.sample)}</dd>
        </dl>
        <p class="hint">对照 review_form.csv 填写：候选正确就填“正确”；候选错误就填“错误”，并补正确位置和角度。位置可填 {POSITION_OPTIONS}，角度可填 {ROTATION_OPTIONS}。</p>
      </div>
    </article>
    """


def write_html(records: list[ReviewRecord]) -> None:
    total = len(records)
    needs_review = sum(1 for record in records if record.needs_review)
    human_verified = sum(1 for record in records if record.verified_by_human)
    consensus = total - human_verified
    cards = "\n".join(record_card(record) for record in records)
    HTML_OUTPUT.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>机械图纸旋转人工复核</title>
  <style>
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", Arial, sans-serif;
      color: #1f2933;
      background: #f6f7f9;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: #ffffff;
      border-bottom: 1px solid #d9dee7;
      padding: 16px 24px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 22px;
      font-weight: 700;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      font-size: 14px;
      color: #52606d;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 20px;
    }}
    .card {{
      display: grid;
      grid-template-columns: minmax(260px, 460px) 1fr;
      gap: 20px;
      background: #ffffff;
      border: 1px solid #d9dee7;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }}
    img {{
      display: block;
      width: 100%;
      max-height: 620px;
      object-fit: contain;
      background: #eef1f5;
      border: 1px solid #d9dee7;
    }}
    .topline {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 18px;
    }}
    dl {{
      display: grid;
      grid-template-columns: 150px 1fr;
      gap: 8px 14px;
      margin: 0;
      font-size: 14px;
    }}
    dt {{
      color: #52606d;
    }}
    dd {{
      margin: 0;
      font-weight: 600;
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
    .manual {{ background: #e8f0ff; color: #1d4ed8; }}
    .consensus {{ background: #edf2f7; color: #3e4c59; }}
    .hint {{
      margin-top: 18px;
      padding: 12px;
      background: #f6f7f9;
      border-left: 4px solid #627d98;
      color: #3e4c59;
      line-height: 1.6;
    }}
    @media (max-width: 820px) {{
      .card {{ grid-template-columns: 1fr; }}
      dl {{ grid-template-columns: 120px 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>机械图纸旋转人工复核</h1>
    <div class="summary">
      <span>总数：{total}</span>
      <span>需要复核：{needs_review}</span>
      <span>人工重点复核：{human_verified}</span>
      <span>共识接受待确认：{consensus}</span>
      <span>填写表：review_form.csv</span>
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


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = build_records()
    if not records:
        raise SystemExit("No review records generated.")
    write_form_csv(records)
    write_json(records)
    write_html(records)
    print(f"Review records: {len(records)}")
    print(f"HTML: {HTML_OUTPUT.relative_to(ROOT)}")
    print(f"Form CSV: {FORM_CSV_OUTPUT.relative_to(ROOT)}")
    print(f"JSON: {JSON_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
