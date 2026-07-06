"""Configuration loading and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import copy
import tomllib


SECRET_KEY_PARTS = ("api_key", "apikey", "token", "secret", "password")


@dataclass(frozen=True)
class ConfigCheckResult:
    path: Path
    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def load_toml(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("rb") as file_obj:
        data = tomllib.load(file_obj)
    if not isinstance(data, dict):
        raise ValueError("TOML root must be a table.")
    return data


def check_config(path: str | Path) -> ConfigCheckResult:
    config_path = Path(path)
    try:
        data = load_toml(config_path)
    except FileNotFoundError:
        return ConfigCheckResult(config_path, False, ("Config file does not exist.",), ())
    except tomllib.TOMLDecodeError as exc:
        return ConfigCheckResult(config_path, False, (f"Invalid TOML: {exc}",), ())
    except ValueError as exc:
        return ConfigCheckResult(config_path, False, (str(exc),), ())

    errors, warnings = validate_config(data)
    return ConfigCheckResult(config_path, not errors, tuple(errors), tuple(warnings))


def validate_config(data: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    qwen = _table(data, "qwen", errors)
    paths = _table(data, "paths", errors)
    runtime = _table(data, "runtime", errors)

    if qwen is not None:
        _string(qwen, "base_url", "qwen.base_url", errors)
        _string(qwen, "model", "qwen.model", errors)
        api_key = qwen.get("api_key")
        if api_key is None:
            warnings.append("Qwen credentials are not set; real model runs will require them.")
        elif not isinstance(api_key, str):
            errors.append("qwen.api_key must be a string.")
        elif not api_key:
            warnings.append("Qwen credentials are empty; real model runs will require them.")

        temperature = qwen.get("temperature")
        if temperature is not None and not isinstance(temperature, (int, float)):
            errors.append("qwen.temperature must be numeric when set.")

        enable_thinking = qwen.get("enable_thinking")
        if enable_thinking is not None and not isinstance(enable_thinking, bool):
            errors.append("qwen.enable_thinking must be true or false when set.")

    if paths is not None:
        for key in ("input_dir", "output_dir", "work_dir", "log_dir"):
            _string(paths, key, f"paths.{key}", errors)

    if runtime is not None:
        for key in ("keep_work_files", "dry_run"):
            value = runtime.get(key)
            if value is not None and not isinstance(value, bool):
                errors.append(f"runtime.{key} must be true or false when set.")

    return errors, warnings


def redacted_copy(data: Mapping[str, Any]) -> dict[str, Any]:
    copied = copy.deepcopy(dict(data))
    return _redact_mapping(copied)


def _table(data: Mapping[str, Any], key: str, errors: list[str]) -> Mapping[str, Any] | None:
    value = data.get(key)
    if value is None:
        errors.append(f"Missing [{key}] section.")
        return None
    if not isinstance(value, Mapping):
        errors.append(f"[{key}] must be a table.")
        return None
    return value


def _string(data: Mapping[str, Any], key: str, label: str, errors: list[str]) -> None:
    value = data.get(key)
    if value is None:
        errors.append(f"{label} is required.")
    elif not isinstance(value, str):
        errors.append(f"{label} must be a string.")


def _redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(data.items()):
        lowered = key.lower()
        if any(part in lowered for part in SECRET_KEY_PARTS):
            data[key] = "<redacted>"
        elif isinstance(value, dict):
            data[key] = _redact_mapping(value)
    return data
