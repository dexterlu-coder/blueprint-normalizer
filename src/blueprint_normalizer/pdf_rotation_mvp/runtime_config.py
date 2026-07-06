"""Runtime configuration adapter for the PDF rotation MVP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from blueprint_normalizer.config import check_config, load_toml, redacted_copy
from blueprint_normalizer.paths import APP_CONFIG_FILENAME, config_candidates


PATH_KEYS = ("input_dir", "output_dir", "work_dir", "log_dir")


@dataclass(frozen=True)
class PathSetting:
    configured: str
    resolved: Path | None

    @property
    def exists(self) -> bool:
        return self.resolved.exists() if self.resolved is not None else False

    def as_report(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "resolved": str(self.resolved) if self.resolved is not None else "",
            "exists": self.exists,
        }


@dataclass(frozen=True)
class QwenRuntimeConfig:
    model: str
    base_url_present: bool
    api_key_present: bool
    temperature: int | float | None
    enable_thinking: bool | None
    top_p: str | int | float | None

    def as_report(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "base_url_present": self.base_url_present,
            "api_key_present": self.api_key_present,
        }


@dataclass(frozen=True)
class RuntimeOptions:
    keep_work_files: bool | str
    dry_run: bool | str

    def as_report(self) -> dict[str, Any]:
        return {
            "keep_work_files": self.keep_work_files,
            "dry_run": self.dry_run,
        }


@dataclass(frozen=True)
class MvpRunConfig:
    config_path: Path
    config_source: str
    discovery_candidates: tuple[Path, ...]
    config_ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    redacted_config: dict[str, Any]
    paths: dict[str, PathSetting]
    qwen: QwenRuntimeConfig
    runtime: RuntimeOptions

    def config_report(self) -> dict[str, Any]:
        return {
            "path": str(self.config_path),
            "source": self.config_source,
            "discovery_candidates": [str(path) for path in self.discovery_candidates],
            "status": "ok" if self.config_ok else "failed",
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "redacted": self.redacted_config,
        }

    def paths_report(self) -> dict[str, Any]:
        return {key: setting.as_report() for key, setting in self.paths.items()}


def load_mvp_run_config(config: str | Path | None = None) -> MvpRunConfig:
    config_path, config_source, discovery_candidates = select_config(config)
    check = check_config(config_path)
    data: dict[str, Any] = {}
    if config_path.exists() and check.ok:
        data = load_toml(config_path)

    paths_table = data.get("paths", {}) if isinstance(data.get("paths"), dict) else {}
    qwen_table = data.get("qwen", {}) if isinstance(data.get("qwen"), dict) else {}
    runtime_table = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    base_dir = config_path.parent.resolve()

    paths = {
        key: PathSetting(
            configured=paths_table.get(key, "") if isinstance(paths_table.get(key, ""), str) else "",
            resolved=resolve_config_path(paths_table.get(key), base_dir),
        )
        for key in PATH_KEYS
    }

    return MvpRunConfig(
        config_path=config_path,
        config_source=config_source,
        discovery_candidates=tuple(discovery_candidates),
        config_ok=check.ok,
        errors=check.errors,
        warnings=check.warnings,
        redacted_config=redacted_copy(data) if data else {},
        paths=paths,
        qwen=QwenRuntimeConfig(
            model=qwen_table.get("model") if isinstance(qwen_table.get("model"), str) else "",
            base_url_present=isinstance(qwen_table.get("base_url"), str) and bool(qwen_table.get("base_url")),
            api_key_present=isinstance(qwen_table.get("api_key"), str) and bool(qwen_table.get("api_key")),
            temperature=qwen_table.get("temperature") if isinstance(qwen_table.get("temperature"), (int, float)) else None,
            enable_thinking=qwen_table.get("enable_thinking") if isinstance(qwen_table.get("enable_thinking"), bool) else None,
            top_p=qwen_table.get("top_p") if isinstance(qwen_table.get("top_p"), (str, int, float)) else None,
        ),
        runtime=RuntimeOptions(
            keep_work_files=runtime_table.get("keep_work_files") if isinstance(runtime_table.get("keep_work_files"), bool) else "",
            dry_run=runtime_table.get("dry_run") if isinstance(runtime_table.get("dry_run"), bool) else "",
        ),
    )


def select_config(config: str | Path | None) -> tuple[Path, str, list[Path]]:
    candidates = config_candidates(config)
    if config is not None:
        return candidates[0], "explicit", candidates

    for candidate in candidates:
        if candidate.exists():
            return candidate, "discovered", candidates
    return candidates[0] if candidates else Path(APP_CONFIG_FILENAME).resolve(), "missing", candidates


def resolve_config_path(value: Any, base_dir: Path) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()

