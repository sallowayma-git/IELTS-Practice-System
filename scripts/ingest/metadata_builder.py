"""Metadata builder utilities for IELTS reading ingestion."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence


_DIFFICULTY_MAPPING: Dict[str, int] = {
    "P1": 1,
    "P2": 2,
    "P3": 3,
    "P4": 4,
}


class MetadataBuilderError(ValueError):
    """Raised when metadata construction fails."""


def map_difficulty_tag(difficulty_tag: str) -> int:
    """Map the textual difficulty tag to its numeric level.

    Args:
        difficulty_tag: Difficulty tag extracted from the source (e.g. "P1").

    Returns:
        The numeric difficulty level.

    Raises:
        MetadataBuilderError: If the tag is unknown or empty.
    """

    tag = (difficulty_tag or "").strip().upper()
    if not tag:
        raise MetadataBuilderError("缺少难度标记，无法生成 metadata.difficulty。")

    if tag not in _DIFFICULTY_MAPPING:
        known = ", ".join(sorted(_DIFFICULTY_MAPPING)) or "<none>"
        raise MetadataBuilderError(f"未知的难度标记 '{difficulty_tag}'，已知标记: {known}。")

    return _DIFFICULTY_MAPPING[tag]


def _ensure_question_numbers_contiguous(questions: Sequence[Mapping[str, Any]]) -> None:
    """Validate that question numbers are present and contiguous."""

    if not questions:
        raise MetadataBuilderError("题目列表为空，无法生成 metadata。")

    try:
        numbers = [int(question["questionNumber"]) for question in questions]
    except KeyError as exc:  # pragma: no cover - defensive, ingestion code should always set the key.
        raise MetadataBuilderError("题目缺少 questionNumber 字段。") from exc
    except (TypeError, ValueError) as exc:
        raise MetadataBuilderError("题目 questionNumber 需为整数。") from exc

    expected = list(range(numbers[0], numbers[0] + len(numbers)))
    if numbers != expected:
        raise MetadataBuilderError(
            "题号不连续: 实际为 {numbers}，应为 {expected}。".format(numbers=numbers, expected=expected)
        )


def _collect_question_types(questions: Iterable[Mapping[str, Any]]) -> List[str]:
    """Collect question types while keeping their first-seen order."""

    seen = set()
    ordered_types: List[str] = []
    for question in questions:
        question_type = question.get("type")
        if not question_type:
            raise MetadataBuilderError("存在题目缺少题型 (type) 字段。")

        if question_type not in seen:
            seen.add(question_type)
            ordered_types.append(question_type)

    return ordered_types


def build_metadata(difficulty_tag: str, questions: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Build the metadata object for a passage.

    Args:
        difficulty_tag: Difficulty tag extracted from the source directory or file name.
        questions: Parsed question objects.

    Returns:
        A dictionary ready to be assigned to ``metadata`` in the JSON structure.
    """

    difficulty = map_difficulty_tag(difficulty_tag)
    _ensure_question_numbers_contiguous(questions)

    return {
        "difficulty": difficulty,
        "totalQuestions": len(questions),
        "questionTypes": _collect_question_types(questions),
    }


__all__ = [
    "MetadataBuilderError",
    "build_metadata",
    "map_difficulty_tag",
]
