"""Data validation utilities for IELTS ingest pipeline."""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class ValidationIssue:
    """Represents a single validation failure."""

    message: str
    context: str
    question_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "message": self.message,
            "context": self.context,
        }
        if self.question_number is not None:
            data["questionNumber"] = self.question_number
        return data


@dataclass
class ValidationReport:
    """Result of running validation for a single payload."""

    file_path: Path
    issues: List[ValidationIssue]

    @property
    def is_successful(self) -> bool:
        return not self.issues

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": str(self.file_path),
            "timestamp": _dt.datetime.utcnow().isoformat() + "Z",
            "issues": [issue.to_dict() for issue in self.issues],
        }


_SINGLE_ANSWER_TYPES = {
    "true-false-ng",
    "yes-no-ng",
    "multiple-choice-single",
    "sentence-completion",
    "summary-completion",
    "notes-completion",
    "table-completion",
    "short-answer",
    "paragraph-matching",
    "heading-matching",
    "feature-matching",
    "statement-matching",
    "sentence-ending-matching",
    "classification",
}

_MULTI_ANSWER_TYPES = {
    "multiple-choice-multiple",
}

_BOOLEAN_ANSWER_VALUES = {
    "true-false-ng": {"TRUE", "FALSE", "NOT GIVEN"},
    "yes-no-ng": {"YES", "NO", "NOT GIVEN"},
}


def validate_payload(file_path: Path, payload: Any) -> ValidationReport:
    """Validate a parsed JSON payload.

    Parameters
    ----------
    file_path:
        The source path of the payload, used for reporting.
    payload:
        Parsed JSON content.
    """

    issues: List[ValidationIssue] = []

    for question_list, context in _discover_question_lists(payload):
        issues.extend(_validate_question_list(question_list, context))

    return ValidationReport(file_path=file_path, issues=issues)


def write_report(report: ValidationReport, success_log: Path, errors_dir: Path) -> None:
    """Persist the validation report to disk.

    Successful validations append a line to ``success.log``. Failed validations
    are written to ``errors/<file>.json`` for downstream review.
    """

    errors_dir.mkdir(parents=True, exist_ok=True)
    success_log.parent.mkdir(parents=True, exist_ok=True)

    if report.is_successful:
        with success_log.open("a", encoding="utf-8") as fh:
            timestamp = _dt.datetime.utcnow().isoformat() + "Z"
            fh.write(f"{timestamp}\t{report.file_path}\n")
    else:
        try:
            relative_path = report.file_path.resolve().relative_to(Path.cwd())
        except ValueError:
            relative_path = Path(report.file_path.name)
        safe_name = str(relative_path.with_suffix('')).replace('/', '__').replace('\\', '__')
        output_path = errors_dir / f"{safe_name}.json"
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, ensure_ascii=False, indent=2)


def _discover_question_lists(payload: Any) -> Iterable[Tuple[List[Dict[str, Any]], str]]:
    """Yield every list of question objects found within the payload."""

    def _walk(node: Any, trail: str) -> Iterable[Tuple[List[Dict[str, Any]], str]]:
        if isinstance(node, list):
            if node and all(isinstance(item, dict) and "questionNumber" in item for item in node):
                yield node, trail or "$"
            else:
                for idx, child in enumerate(node):
                    yield from _walk(child, f"{trail}[{idx}]")
        elif isinstance(node, dict):
            for key, child in node.items():
                next_trail = f"{trail}.{key}" if trail else key
                yield from _walk(child, next_trail)

    yield from _walk(payload, "")


def _validate_question_list(questions: Sequence[Dict[str, Any]], context: str) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    expected_number: Optional[int] = None

    for idx, question in enumerate(questions):
        q_context = f"{context}[{idx}]"
        q_number = question.get("questionNumber")

        # Field type checks
        if not isinstance(q_number, int):
            issues.append(
                ValidationIssue(
                    message="questionNumber必须为整数",
                    context=q_context,
                )
            )
            q_number = None
        if not isinstance(question.get("type"), str):
            issues.append(
                ValidationIssue(
                    message="type字段必须为字符串",
                    context=q_context,
                    question_number=q_number,
                )
            )
        if "instruction" in question and not isinstance(question.get("instruction"), str):
            issues.append(
                ValidationIssue(
                    message="instruction字段必须为字符串",
                    context=q_context,
                    question_number=q_number,
                )
            )
        if not isinstance(question.get("content"), dict):
            issues.append(
                ValidationIssue(
                    message="content字段必须为对象",
                    context=q_context,
                    question_number=q_number,
                )
            )

        issues.extend(_validate_answer(question, q_context))

        # Sequential question numbers
        if isinstance(q_number, int):
            if expected_number is None:
                expected_number = q_number
            elif q_number != expected_number:
                issues.append(
                    ValidationIssue(
                        message=f"题号应为{expected_number}，实际为{q_number}",
                        context=q_context,
                        question_number=q_number,
                    )
                )
            step = _step_size(question)
            expected_number = (expected_number if expected_number is not None else q_number) + step

    return issues


def _validate_answer(question: Dict[str, Any], context: str) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    q_type = question.get("type")
    answer = question.get("answer")
    q_number = question.get("questionNumber") if isinstance(question.get("questionNumber"), int) else None

    if q_type in _MULTI_ANSWER_TYPES:
        if not isinstance(answer, list) or not answer:
            issues.append(
                ValidationIssue(
                    message="多选题答案必须为非空数组",
                    context=context,
                    question_number=q_number,
                )
            )
        else:
            if not all(isinstance(item, str) for item in answer):
                issues.append(
                    ValidationIssue(
                        message="多选题答案数组的元素必须为字符串",
                        context=context,
                        question_number=q_number,
                    )
                )
            group_size = question.get("occupiesQuestions")
            if isinstance(group_size, int) and group_size > 0 and len(answer) != group_size:
                issues.append(
                    ValidationIssue(
                        message=f"多选题答案数量应为{group_size}",
                        context=context,
                        question_number=q_number,
                    )
                )
            if "checkboxGroupName" in question and not isinstance(question.get("checkboxGroupName"), str):
                issues.append(
                    ValidationIssue(
                        message="checkboxGroupName必须为字符串",
                        context=context,
                        question_number=q_number,
                    )
                )
    elif q_type in _SINGLE_ANSWER_TYPES:
        if not isinstance(answer, str) or not answer.strip():
            issues.append(
                ValidationIssue(
                    message="答案必须为非空字符串",
                    context=context,
                    question_number=q_number,
                )
            )
        else:
            normalized = answer.strip()
            if q_type in _BOOLEAN_ANSWER_VALUES:
                allowed = _BOOLEAN_ANSWER_VALUES[q_type]
                if normalized.upper() not in allowed:
                    issues.append(
                        ValidationIssue(
                            message=f"判断题答案必须为{', '.join(sorted(allowed))}",
                            context=context,
                            question_number=q_number,
                        )
                    )
            if q_type == "multiple-choice-single" and normalized.upper() != normalized:
                issues.append(
                    ValidationIssue(
                        message="单选题答案必须使用大写选项字母",
                        context=context,
                        question_number=q_number,
                    )
                )
    else:
        if answer is None:
            issues.append(
                ValidationIssue(
                    message="未知题型必须提供answer字段",
                    context=context,
                    question_number=q_number,
                )
            )

    return issues


def _step_size(question: Dict[str, Any]) -> int:
    size = question.get("occupiesQuestions")
    if isinstance(size, int) and size > 0:
        return size
    return 1


__all__ = [
    "ValidationIssue",
    "ValidationReport",
    "validate_payload",
    "write_report",
]
