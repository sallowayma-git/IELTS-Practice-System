"""Configuration loader for the IELTS HTML ingest toolkit."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional


class ConfigError(RuntimeError):
    """Raised when configuration files are missing or invalid."""


@dataclass(frozen=True)
class OutputConfig:
    """Resolved output locations."""

    root: Path
    json_dir: Path
    chunks_dir: Path
    manifest_path: Path


@dataclass(frozen=True)
class IngestConfig:
    """Top-level configuration container."""

    input_root: Path
    output: OutputConfig
    concurrency: int


_DEFAULT_FILENAME = "settings.default.json"
_LOCAL_OVERRIDE_FILENAME = "settings.local.json"


def load_config(config_dir: Optional[Path] = None) -> IngestConfig:
    """Load ingest configuration.

    Args:
        config_dir: Directory containing the configuration files. Defaults to
            the directory of this module.

    Returns:
        IngestConfig with resolved paths and concurrency.

    Raises:
        ConfigError: if required files are missing or values are invalid.
    """

    base_dir = config_dir or Path(__file__).resolve().parent
    default_path = base_dir / _DEFAULT_FILENAME
    default_data = _read_json(default_path)

    local_path = base_dir / _LOCAL_OVERRIDE_FILENAME
    if local_path.exists():
        local_data = _read_json(local_path)
        merged = _deep_merge_dicts(default_data, local_data)
    else:
        merged = default_data

    try:
        return _parse_config(merged, base_dir)
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(str(exc)) from exc


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except FileNotFoundError as exc:
        raise ConfigError(f"配置文件不存在: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"配置文件格式错误: {path}: {exc}") from exc


def _deep_merge_dicts(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries."""

    result: Dict[str, Any] = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], MutableMapping)
            and isinstance(value, Mapping)
        ):
            result[key] = _deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def _parse_config(raw: Mapping[str, Any], base_dir: Path) -> IngestConfig:
    paths = raw["paths"]
    input_root = _resolve_path(base_dir, paths["input_root"])

    output_root = _resolve_path(base_dir, paths["output_root"])
    json_dir = _resolve_path(output_root, paths.get("json_subdir", "json"))
    chunks_dir = _resolve_path(output_root, paths.get("chunks_subdir", "chunks"))
    manifest_path = _resolve_path(output_root, paths.get("manifest_filename", "manifest.json"))

    concurrency_section = raw.get("concurrency", {})
    concurrency_value = concurrency_section.get("max_workers", 1)
    concurrency = _validate_concurrency(concurrency_value)

    output = OutputConfig(
        root=output_root,
        json_dir=json_dir,
        chunks_dir=chunks_dir,
        manifest_path=manifest_path,
    )

    return IngestConfig(
        input_root=input_root,
        output=output,
        concurrency=concurrency,
    )


def _resolve_path(base_dir: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"路径字段格式错误: {value!r}")

    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = (base_dir / candidate).resolve()
    return candidate


def _validate_concurrency(raw_value: Any) -> int:
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise ValueError(f"并发度必须是正整数，收到: {raw_value!r}")
    if raw_value <= 0:
        raise ValueError(f"并发度必须大于0，收到: {raw_value}")
    return raw_value


__all__ = [
    "ConfigError",
    "OutputConfig",
    "IngestConfig",
    "load_config",
]
