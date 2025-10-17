"""Serialize IELTS exam data to individual JSON files.

This module provides utilities to split aggregated exam data into
per-exam JSON files that contain the ``id``, ``passage``, ``questions``
and ``metadata`` fields described in the project documentation.

It exposes a command line interface so the module can be used as a
standalone tool::

    python -m scripts.serialize_exams --source aggregated.json

The CLI supports two overwrite strategies:
``skip`` (default) keeps existing files, whereas ``force`` rewrites
all files regardless of whether they exist.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Mapping, MutableMapping, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SerializationResult:
    """Summary returned after serialising exams."""

    total: int
    written: int
    skipped: int
    log_file: Path


class ExamSerializationError(RuntimeError):
    """Raised when the source data cannot be serialised."""


def _normalise_exam_id(raw_id: str) -> str:
    """Normalise exam identifiers to ``e###`` format.

    Parameters
    ----------
    raw_id:
        Identifier read from the source data.

    Returns
    -------
    str
        Exam id in ``e###`` format.
    """

    match = re.search(r"(\d+)", raw_id)
    if not match:
        raise ExamSerializationError(f"无法从ID `{raw_id}` 中解析编号")
    number = int(match.group(1))
    return f"e{number:03d}"


def _extract_exam_id(exam: Mapping[str, Any]) -> str:
    """Extract and normalise the exam identifier from an exam payload."""

    if "id" in exam and isinstance(exam["id"], str):
        return _normalise_exam_id(exam["id"])
    if "number" in exam:
        return _normalise_exam_id(str(exam["number"]))
    raise ExamSerializationError("缺少考试ID或编号，无法生成文件名")


def _ensure_required_fields(exam: Mapping[str, Any]) -> None:
    """Validate the presence of required fields in the exam payload."""

    for field in ("passage", "questions", "metadata"):
        if field not in exam:
            raise ExamSerializationError(f"缺少必要字段 `{field}`")
    if not isinstance(exam["questions"], Sequence):
        raise ExamSerializationError("`questions` 字段必须是数组")


def _iter_exams(source: Any) -> Iterable[MutableMapping[str, Any]]:
    """Yield normalised exam dictionaries from raw source data."""

    if isinstance(source, Sequence) and not isinstance(source, (str, bytes, bytearray)):
        items: Iterable[Any] = source
    elif isinstance(source, Mapping):
        if "exams" in source and isinstance(source["exams"], Sequence):
            items = source["exams"]  # type: ignore[assignment]
        else:
            items = (
                {**({} if not isinstance(value, Mapping) else dict(value)), "id": key}
                for key, value in source.items()
            )
    else:
        raise ExamSerializationError("无法识别的源数据结构，应为数组或对象")

    for item in items:
        if not isinstance(item, MutableMapping):
            raise ExamSerializationError("考试条目必须是对象")
        _ensure_required_fields(item)
        # copy to avoid mutating caller data
        normalised = dict(item)
        normalised["id"] = _extract_exam_id(normalised)
        yield normalised


def _configure_logger(log_file: Path) -> logging.Logger:
    """Configure and return a dedicated logger for serialization."""

    log_file.parent.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("serialize_exams")
    log.setLevel(logging.INFO)
    log.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    log.addHandler(stream_handler)

    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)

    return log


def serialize_exams(
    exams: Iterable[MutableMapping[str, Any]] | Iterable[Mapping[str, Any]],
    output_dir: Path,
    *,
    overwrite: str = "skip",
    log_file: Path | None = None,
) -> SerializationResult:
    """Serialize exam payloads into ``output_dir``.

    Parameters
    ----------
    exams:
        Iterable of exam dictionaries.
    output_dir:
        Directory that will contain the ``e###.json`` files.
    overwrite:
        Either ``"skip"`` (default) to keep existing files or ``"force"``
        to rewrite them.
    log_file:
        Optional path for the operation log. Defaults to
        ``output_dir / "serialization.log"``.
    """

    if overwrite not in {"skip", "force"}:
        raise ValueError("overwrite 仅支持 'skip' 或 'force'")

    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_file or output_dir / "serialization.log"
    log = _configure_logger(log_path)

    raw_exams = list(exams)
    normalised_exams = list(_iter_exams(raw_exams))
    normalised_exams.sort(key=lambda exam: int(re.search(r"(\d+)", exam["id"]).group(1)))  # type: ignore[arg-type]

    total = len(normalised_exams)
    written = 0
    skipped = 0

    for exam in normalised_exams:
        exam_id = exam["id"]
        target_path = output_dir / f"{exam_id}.json"
        record = {
            "id": exam_id,
            "passage": exam["passage"],
            "questions": exam["questions"],
            "metadata": exam["metadata"],
        }

        if target_path.exists() and overwrite == "skip":
            skipped += 1
            log.info("跳过已存在文件 %s", target_path)
            continue

        with target_path.open("w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=2)
        written += 1
        log.info("写入 %s", target_path)

    log.info("完成序列化：共 %d 篇，写入 %d 篇，跳过 %d 篇", total, written, skipped)
    return SerializationResult(total=total, written=written, skipped=skipped, log_file=log_path)


def load_exams_from_file(path: Path) -> List[MutableMapping[str, Any]]:
    """Load aggregated exam data from ``path``."""

    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return list(_iter_exams(raw))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serialize IELTS exams to individual JSON files")
    parser.add_argument("--source", required=True, type=Path, help="汇总JSON文件路径")
    parser.add_argument("--output-dir", default=Path("output/json"), type=Path, help="输出目录，默认为 output/json")
    parser.add_argument(
        "--overwrite",
        choices=("skip", "force"),
        default="skip",
        help="遇到已存在文件时的处理策略：skip=跳过，force=覆盖",
    )
    parser.add_argument("--log-file", type=Path, default=None, help="自定义日志文件路径")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        exams = load_exams_from_file(args.source)
        result = serialize_exams(
            exams,
            args.output_dir,
            overwrite=args.overwrite,
            log_file=args.log_file,
        )
    except (ExamSerializationError, json.JSONDecodeError) as exc:
        logger.error("序列化失败：%s", exc)
        return 1
    logger.info(
        "序列化完成：共 %d 篇，写入 %d 篇，跳过 %d 篇。日志：%s",
        result.total,
        result.written,
        result.skipped,
        result.log_file,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
