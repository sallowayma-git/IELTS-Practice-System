"""HTML与JSON结果对比审计工具。"""

from __future__ import annotations

import argparse
import json
import sys
from difflib import unified_diff
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

if __package__ in {None, ""}:  # 允许直接python执行
    package_root = Path(__file__).resolve().parents[2]
    sys.path.append(str(package_root))
    from scripts.ingest.datamodel import (  # noqa: E402
        DifficultyLevel,
        Exam,
        Metadata,
        Paragraph,
        Passage,
        Question,
        QuestionType,
    )
    from scripts.ingest.html_exam_parser import (  # noqa: E402
        exam_to_payload,
        parse_exam,
    )
else:  # pragma: no cover - 包内调用
    from .datamodel import DifficultyLevel, Exam, Metadata, Paragraph, Passage, Question, QuestionType
    from .html_exam_parser import exam_to_payload, parse_exam


class AuditError(RuntimeError):
    """表示审计过程中发现的不一致。"""


def load_exam_from_json(json_path: Path) -> Exam:
    data = json.loads(json_path.read_text(encoding="utf-8"))

    passage_data = data.get("passage", {})
    paragraphs = [
        Paragraph(content=item["content"], label=item.get("label"))
        for item in passage_data.get("paragraphs", [])
    ]
    passage = Passage(title=passage_data.get("title", ""), paragraphs=paragraphs)

    questions: List[Question] = []
    for question_data in data.get("questions", []):
        question_type = QuestionType(question_data["type"])
        content = _clone_content(question_data["content"])
        answer = _normalize_answer(question_data["answer"])
        question = Question(
            questionNumber=int(question_data["questionNumber"]),
            type=question_type,
            instruction=question_data["instruction"],
            content=content,
            answer=answer,
            explanation=question_data.get("explanation"),
            checkboxGroupName=question_data.get("checkboxGroupName"),
            occupiesQuestions=question_data.get("occupiesQuestions"),
            canReuse=question_data.get("canReuse"),
        )
        questions.append(question)

    metadata_data = data.get("metadata", {})
    metadata = Metadata(
        difficulty=DifficultyLevel(metadata_data["difficulty"]),
        totalQuestions=int(metadata_data["totalQuestions"]),
        questionTypes=[QuestionType(item) for item in metadata_data.get("questionTypes", [])],
    )

    exam = Exam(id=data["id"], passage=passage, questions=questions, metadata=metadata)
    exam.validate_consistency()
    _validate_answers_present(exam)
    return exam


def audit_exam_pair(html_path: Path, json_path: Path) -> None:
    html_exam = parse_exam(html_path)
    json_exam = load_exam_from_json(json_path)

    if html_exam.id != json_exam.id:
        raise AuditError(f"ID不一致: HTML={html_exam.id}, JSON={json_exam.id}")

    _validate_answers_present(html_exam)

    html_payload = exam_to_payload(html_exam)
    json_payload = exam_to_payload(json_exam)

    if html_payload != json_payload:
        diff = _render_diff(html_payload, json_payload)
        raise AuditError(f"数据不匹配:\n{diff}")


def _clone_content(content: Dict[str, Any]) -> Dict[str, Any]:
    cloned: Dict[str, Any] = {}
    for key, value in content.items():
        if isinstance(value, list):
            cloned[key] = [item.copy() if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict):
            cloned[key] = value.copy()
        else:
            cloned[key] = value
    return cloned


def _normalize_answer(answer: Any) -> Any:
    if isinstance(answer, list):
        return [str(item) for item in answer]
    return str(answer)


def _validate_answers_present(exam: Exam) -> None:
    for question in exam.questions:
        value = question.answer
        if isinstance(value, str):
            if not value.strip():
                raise AuditError(f"题目{question.questionNumber}的答案为空")
        else:
            sequence: Sequence[Any] = value
            if not sequence:
                raise AuditError(f"题目{question.questionNumber}的答案数组为空")
            for item in sequence:
                if not str(item).strip():
                    raise AuditError(f"题目{question.questionNumber}存在空答案项")


def _render_diff(expected: Dict[str, Any], actual: Dict[str, Any]) -> str:
    expected_text = json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True)
    actual_text = json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True)
    diff_lines = list(
        unified_diff(
            expected_text.splitlines(),
            actual_text.splitlines(),
            fromfile="html-derived",
            tofile="json-file",
            lineterm="",
        )
    )
    if not diff_lines:
        return "(无差异详情，可能是不可序列化对象差异)"
    preview = diff_lines[:200]
    if len(diff_lines) > 200:
        preview.append("... (diff截断)")
    return "\n".join(preview)


def _iter_html_files(path: Path) -> Iterable[Path]:
    if path.is_dir():
        yield from sorted(path.rglob("*.html"))
    else:
        yield path


def main() -> None:
    parser = argparse.ArgumentParser(description="审计HTML与JSON的一致性")
    parser.add_argument("html", type=Path, help="HTML文件或目录")
    parser.add_argument("--json", type=Path, help="单个JSON文件路径")
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=Path("output/json"),
        help="默认JSON搜索目录（未显式指定--json时使用）",
    )
    args = parser.parse_args()

    html_targets = list(_iter_html_files(args.html))
    if not html_targets:
        raise SystemExit("未找到任何HTML文件")

    failures: List[str] = []

    for html_path in html_targets:
        try:
            html_exam = parse_exam(html_path)
            if args.json is not None and html_path.is_file() and len(html_targets) == 1:
                json_path = args.json
            else:
                json_path = args.json_dir / f"{html_exam.id}.json"
            if not json_path.exists():
                raise AuditError(f"JSON文件不存在: {json_path}")
            audit_exam_pair(html_path, json_path)
            print(f"[OK] {html_exam.id} - {html_path}")
        except Exception as exc:  # noqa: BLE001 - 明确捕获所有异常用于报告
            failures.append(f"[FAIL] {html_path}: {exc}")

    if failures:
        for line in failures:
            print(line)
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover
    main()

