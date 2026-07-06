from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from pathlib import Path
from typing import Any

from scripts.common.obb_utils import ROOT, resolve_path


DEFAULT_CALL_PREP_DIR = ROOT / "local_data" / "mcp_vlm_teacher_call_prep"
DEFAULT_PROVIDER_DIR = ROOT / "local_data" / "mcp_vlm_teacher_provider"
DEFAULT_MANIFEST = DEFAULT_CALL_PREP_DIR / "teacher_call_manifest.json"
DEFAULT_REQUESTS = DEFAULT_PROVIDER_DIR / "teacher_requests.jsonl"
DEFAULT_RESPONSE_TEMPLATE = DEFAULT_PROVIDER_DIR / "teacher_response_template.jsonl"
DEFAULT_PROMPT = DEFAULT_CALL_PREP_DIR / "teacher_prompt.md"
DEFAULT_SCHEMA = DEFAULT_CALL_PREP_DIR / "teacher_response_schema.json"
DEFAULT_OUTPUT_DIR = ROOT / "local_data" / "review_inbox" / "current"


def as_posix(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def rel_path(target: Path, base: Path) -> str:
    return Path(os.path.relpath(target, base)).as_posix()


def read_json(path: Path) -> Any:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def current_inbox_is_idle(current_dir: Path) -> bool:
    if not current_dir.exists():
        return True
    entries = [entry for entry in current_dir.iterdir() if entry.name != ".gitkeep"]
    if not entries:
        return True
    if len(entries) != 1 or entries[0].name != "README.md":
        return False
    text = entries[0].read_text(encoding="utf-8", errors="ignore")
    return "当前没有待用户审核、填写或标注的文件" in text


def ensure_safe_output(current_dir: Path, force: bool) -> None:
    current_dir.mkdir(parents=True, exist_ok=True)
    if not current_inbox_is_idle(current_dir) and not force:
        raise RuntimeError(
            f"Current review inbox is not idle: {as_posix(current_dir)}. "
            "Archive it first or rerun with --force."
        )
    if force:
        resolved_current = current_dir.resolve()
        if resolved_current == ROOT.resolve() or ROOT.resolve() not in resolved_current.parents:
            raise RuntimeError(f"Refusing to clean unexpected path: {resolved_current}")
        for entry in current_dir.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()


def copy_file(src: Path, dest: Path) -> str:
    resolved = resolve_path(src)
    if not resolved.exists():
        return ""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resolved, dest)
    return as_posix(dest)


def copy_assets(tasks: list[dict[str, Any]], output_dir: Path) -> dict[str, dict[str, str]]:
    copied: dict[str, dict[str, str]] = {}
    assets_root = output_dir / "assets"
    for task in tasks:
        task_id = task["task_id"]
        task_dir = assets_root / task_id
        copied[task_id] = {}
        for key in ["source_image", "overlay_image", "candidate_crop"]:
            src_value = task.get(key, "")
            if not src_value:
                copied[task_id][key] = ""
                continue
            src = resolve_path(Path(src_value))
            dest = task_dir / src.name
            copied[task_id][key] = copy_file(src, dest)
    return copied


def write_tasks_csv(path: Path, tasks: list[dict[str, Any]], assets: dict[str, dict[str, str]]) -> None:
    fieldnames = [
        "序号",
        "任务ID",
        "样本",
        "任务类型",
        "问题",
        "候选编号",
        "图片",
        "overlay",
        "候选裁剪",
        "建议用途",
        "备注",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for index, task in enumerate(tasks, start=1):
            task_assets = assets[task["task_id"]]
            writer.writerow(
                {
                    "序号": index,
                    "任务ID": task["task_id"],
                    "样本": task.get("sample", ""),
                    "任务类型": task.get("task_type", ""),
                    "问题": task.get("question", ""),
                    "候选编号": task.get("candidate_index", ""),
                    "图片": task_assets.get("source_image", ""),
                    "overlay": task_assets.get("overlay_image", ""),
                    "候选裁剪": task_assets.get("candidate_crop", ""),
                    "建议用途": task.get("reason", ""),
                    "备注": "",
                }
            )


def write_readme(path: Path) -> None:
    path.write_text(
        """# MCP/VLM teacher 手动响应任务

本目录是当前固定审核入口。本轮只有 8 条 teacher 小实验任务。

请使用 `teacher_requests.jsonl` 中每条任务的问题和图片资产，让人工、MCP 或 VLM 逐条给出 JSON 响应，然后填写到 `teacher_response_template.jsonl` 的 `parsed_response` 字段，并把对应行的 `parse_status` 改为 `ok`。

填写时重点判断：

- 候选是否是真实标题栏。
- 是否贴住图纸外框线且没有空隙。
- 是否具备标题栏字段簇组合，而不是普通表格或明细表。
- 普通表格误检与图纸方向无关。
- 小角度 OBB 偏差是否仍覆盖标题栏主体。

填完后运行：

```text
python scripts/vlm/build_mcp_vlm_teacher_provider_requests.py --validate-responses local_data/review_inbox/current/teacher_response_template.jsonl
```

辅助文件：

- `teacher_tasks.csv`：低噪声任务清单。
- `teacher_requests.jsonl`：完整请求。
- `teacher_response_template.jsonl`：待填写响应模板。
- `teacher_response_schema.json`：响应结构要求。
- `teacher_prompt.md`：teacher prompt。
- `assets/`：本轮任务图片副本。
""",
        encoding="utf-8",
    )


def build(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = resolve_path(args.output_dir)
    ensure_safe_output(output_dir, args.force)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = read_json(args.manifest)
    tasks = manifest.get("tasks", [])
    assets = copy_assets(tasks, output_dir)

    copied_files = {
        "teacher_requests": copy_file(args.requests, output_dir / "teacher_requests.jsonl"),
        "teacher_response_template": copy_file(
            args.response_template,
            output_dir / "teacher_response_template.jsonl",
        ),
        "teacher_prompt": copy_file(args.prompt, output_dir / "teacher_prompt.md"),
        "teacher_response_schema": copy_file(args.schema, output_dir / "teacher_response_schema.json"),
    }

    tasks_csv = output_dir / "teacher_tasks.csv"
    write_tasks_csv(tasks_csv, tasks, assets)
    write_readme(output_dir / "README.md")

    missing_assets = []
    for task in tasks:
        task_id = task["task_id"]
        for key in ["source_image", "overlay_image", "candidate_crop"]:
            if task.get(key) and not assets[task_id].get(key):
                missing_assets.append({"task_id": task_id, "asset": key, "source": task[key]})

    summary = {
        "task_count": len(tasks),
        "missing_asset_count": len(missing_assets),
        "missing_assets": missing_assets,
        "output_dir": as_posix(output_dir),
        "outputs": {
            **copied_files,
            "teacher_tasks": as_posix(tasks_csv),
            "readme": as_posix(output_dir / "README.md"),
            "assets": as_posix(output_dir / "assets"),
        },
    }
    write_json(output_dir / "teacher_review_inbox_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish MCP/VLM teacher tasks to review inbox.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--response-template", type=Path, default=DEFAULT_RESPONSE_TEMPLATE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


