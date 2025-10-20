import json
import sys
import tempfile
import unittest
from pathlib import Path

# 允许直接运行测试文件
sys.path.append(str(Path(__file__).resolve().parents[3]))

from scripts.ingest.audit_conversion import AuditError, audit_exam_pair
from scripts.ingest.datamodel import QuestionType
from scripts.ingest.html_exam_parser import Node, _parse_choice_group


class BooleanQuestionParsingTest(unittest.TestCase):
    def _build_boolean_group(self) -> Node:
        instruction = Node(
            tag="p",
            attrs={},
            contents=[
                "Do the following statements agree with the information in the passage? TRUE/FALSE/NOT GIVEN.",
            ],
        )
        prompt = Node(
            tag="p",
            attrs={},
            contents=[
                Node(tag="strong", attrs={}, contents=["1"]),
                " Statement text.",
            ],
        )
        labels = [
            self._build_option("TRUE"),
            self._build_option("FALSE"),
            self._build_option("NOT GIVEN"),
        ]
        question_item = Node(
            tag="div",
            attrs={"class": "question-item tfng-item"},
            contents=[prompt, *labels],
        )
        return Node(tag="div", attrs={"class": "group"}, contents=[instruction, question_item])

    @staticmethod
    def _build_option(value: str) -> Node:
        input_node = Node(tag="input", attrs={"type": "radio", "name": "q1", "value": value}, contents=[])
        return Node(tag="label", attrs={}, contents=[input_node, f" {value}"])

    def test_boolean_questions_emit_statement_content(self) -> None:
        group = self._build_boolean_group()
        answers = {"q1": "TRUE"}

        questions = _parse_choice_group(group, answers)

        self.assertEqual(len(questions), 1)
        question = questions[0]
        self.assertEqual(question.type, QuestionType.TRUE_FALSE_NG)
        self.assertEqual(question.content, {"statement": "Statement text."})
        self.assertEqual(question.answer, "TRUE")


class BooleanAuditWorkflowTest(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp_path = Path(self.tmpdir.name)
        self.html_path = self.tmp_path / "1. P1 - Sample.html"
        self.json_path = self.tmp_path / "e001.json"

        self.html_path.write_text(self._build_sample_html(), encoding="utf-8")

    @staticmethod
    def _build_sample_html() -> str:
        return """<!DOCTYPE html>
<html>
  <body>
    <section id=\"left\">
      <h3>Sample Title</h3>
      <div class=\"paragraph-wrapper\">
        <p>Paragraph content.</p>
      </div>
    </section>
    <section id=\"right\">
      <div class=\"group\">
        <p>Do the following statements agree with the information? TRUE/FALSE/NOT GIVEN.</p>
        <div class=\"question-item tfng-item\">
          <p><strong>1</strong> Sample statement.</p>
          <label><input type=\"radio\" name=\"q1\" value=\"TRUE\"> TRUE</label>
          <label><input type=\"radio\" name=\"q1\" value=\"FALSE\"> FALSE</label>
          <label><input type=\"radio\" name=\"q1\" value=\"NOT GIVEN\"> NOT GIVEN</label>
        </div>
      </div>
    </section>
    <script>
      const correctAnswers = { q1: 'TRUE' };
    </script>
  </body>
</html>
"""

    def _write_json(self, content: dict) -> None:
        self.json_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_common_payload(self, question_content: dict) -> dict:
        return {
            "id": "e001",
            "passage": {
                "title": "Sample Title",
                "paragraphs": [
                    {"label": None, "content": "Paragraph content."},
                ],
            },
            "questions": [
                {
                    "questionNumber": 1,
                    "type": "true-false-ng",
                    "instruction": "Do the following statements agree with the information? TRUE/FALSE/NOT GIVEN.",
                    "content": question_content,
                    "answer": "TRUE",
                }
            ],
            "metadata": {
                "difficulty": 1,
                "totalQuestions": 1,
                "questionTypes": ["true-false-ng"],
            },
        }

    def test_audit_detects_boolean_payload_with_options(self) -> None:
        bad_content = {
            "questionText": "Sample statement.",
            "options": [
                {"label": "TRUE", "text": "TRUE"},
                {"label": "FALSE", "text": "FALSE"},
                {"label": "NOT GIVEN", "text": "NOT GIVEN"},
            ],
        }
        self._write_json(self._build_common_payload(bad_content))

        with self.assertRaises(AuditError):
            audit_exam_pair(self.html_path, self.json_path)

    def test_audit_accepts_boolean_statement_payload(self) -> None:
        good_content = {"statement": "Sample statement."}
        self._write_json(self._build_common_payload(good_content))

        # 不应抛出异常
        audit_exam_pair(self.html_path, self.json_path)


class BooleanDatasetAuditTest(unittest.TestCase):
    def test_boolean_questions_in_json_assets(self) -> None:
        json_root = Path(__file__).resolve().parents[4] / "output" / "json"
        self.assertTrue(json_root.is_dir(), f"未找到JSON目录: {json_root}")

        boolean_types = {
            "true-false-ng": {"TRUE", "FALSE", "NOT GIVEN"},
            "yes-no-ng": {"YES", "NO", "NOT GIVEN"},
        }

        for json_path in sorted(json_root.glob("*.json")):
            with json_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)

            questions = payload.get("questions", [])
            self.assertIsInstance(questions, list, f"questions字段不是数组: {json_path}")

            for question in questions:
                if not isinstance(question, dict):
                    continue

                qtype = question.get("type")
                if qtype not in boolean_types:
                    continue

                content = question.get("content")
                self.assertIsInstance(content, dict, f"布尔题content不是对象: {json_path}")
                self.assertEqual(
                    {"statement"},
                    set(content.keys()),
                    f"布尔题content包含多余字段: {json_path}",
                )

                statement = content.get("statement")
                self.assertIsInstance(statement, str, f"布尔题statement不是字符串: {json_path}")
                self.assertTrue(statement.strip(), f"布尔题statement为空: {json_path}")

                answer = question.get("answer")
                self.assertIsInstance(answer, str, f"布尔题answer不是字符串: {json_path}")
                normalized_answer = answer.strip().upper()
                self.assertIn(
                    normalized_answer,
                    boolean_types[qtype],
                    f"布尔题答案非法: {json_path} -> {answer}",
                )

if __name__ == "__main__":  # pragma: no cover
    unittest.main()
