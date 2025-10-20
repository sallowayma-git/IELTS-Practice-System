"""扫描并修复判断题题型/选项错误的JSON。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[4] / "output" / "json"


def _iter_json_files(directory: Path) -> Iterable[Path]:
    yield from sorted(directory.glob("*.json"))


def _detect_boolean_spec(instruction: str, content: Dict[str, object]) -> Tuple[str, Sequence[str]] | None:
    upper = instruction.upper()
    patterns: Dict[Tuple[str, ...], Tuple[str, Sequence[str]]] = {
        ("TRUE", "FALSE", "NOT GIVEN"): (
            "true-false-ng",
            ("TRUE", "FALSE", "NOT GIVEN"),
        ),
        ("YES", "NO", "NOT GIVEN"): (
            "yes-no-ng",
            ("YES", "NO", "NOT GIVEN"),
        ),
    }
    for tokens, spec in patterns.items():
        if all(re.search(token, upper) for token in tokens):
            return spec

    options = content.get("options")
    if isinstance(options, list):
        for tokens, spec in patterns.items():
            _, labels = spec
            if _options_match(options, labels):
                return spec
    return None


def _normalize_statement(content: Dict[str, object]) -> str | None:
    statement = content.get("statement")
    if isinstance(statement, str) and statement.strip():
        return statement.strip()

    question_text = content.get("questionText")
    if isinstance(question_text, str) and question_text.strip():
        return question_text.strip()

    return None


def _options_match(options: List[Dict[str, str]], labels: Sequence[str]) -> bool:
    if len(options) != len(labels):
        return False
    for option, label in zip(options, labels):
        if option.get("label", "").strip().upper() != label.upper():
            return False
        if option.get("text", "").strip().upper() != label.upper():
            return False
    return True


def _normalize_question_types(questions: Sequence[Dict[str, object]]) -> List[str]:
    ordered: List[str] = []
    for question in questions:
        qtype = question.get("type")
        if isinstance(qtype, str) and qtype not in ordered:
            ordered.append(qtype)
    return ordered


def repair_file(path: Path) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    questions = data.get("questions")
    if not isinstance(questions, list):
        return False

    changed = False

    for question in questions:
        if not isinstance(question, dict):
            continue
        instruction = question.get("instruction")
        content = question.get("content")
        if not isinstance(instruction, str) or not isinstance(content, dict):
            continue

        detection = _detect_boolean_spec(instruction, content)
        if detection is None:
            continue

        expected_type, _labels = detection
        statement = _normalize_statement(content)
        if statement is None:
            continue

        desired_content = {"statement": statement}
        if content != desired_content:
            content.clear()
            content.update(desired_content)
            changed = True

        if question.get("type") != expected_type:
            question["type"] = expected_type
            changed = True

    if changed:
        metadata = data.get("metadata")
        if isinstance(metadata, dict):
            metadata["questionTypes"] = _normalize_question_types(questions)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
    return changed


def main() -> None:
    any_changed = False
    for json_file in _iter_json_files(ROOT):
        if repair_file(json_file):
            print(f"[FIXED] {json_file.name}")
            any_changed = True
    if not any_changed:
        print("No files required updates.")


if __name__ == "__main__":  # pragma: no cover - CLI入口
    main()

