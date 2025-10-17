import textwrap
import unittest

from develop.html_to_json.answer_parser import ExtractedAnswer, ParseError, extract_answer_data


class AnswerParserTests(unittest.TestCase):
    def test_extracts_and_normalises_answers(self) -> None:
        html = textwrap.dedent(
            """
            <script>
            const correctAnswers = {
                q1: 'TRUE',
                q2: 'Polynesian',
                q3: ['A', 'c'],
                q20_21: ['A', 'D']
            };
            const answerExplanations = {
                q2: 'Derived from the passage heading.',
                q3: {
                    explanation: 'Option A is described in paragraph B.',
                    hint: 'Focus on the researcher examples.'
                }
            };
            </script>
            """
        )

        extracted = extract_answer_data(html)

        self.assertEqual(
            extracted["q1"],
            ExtractedAnswer(answer="TRUE", explanation=None),
        )
        self.assertEqual(
            extracted["q2"],
            ExtractedAnswer(answer="polynesian", explanation="Derived from the passage heading."),
        )
        self.assertEqual(
            extracted["q3"],
            ExtractedAnswer(
                answer=["A", "C"],
                explanation="Option A is described in paragraph B.\nFocus on the researcher examples.",
            ),
        )
        self.assertEqual(
            extracted["q20_21"],
            ExtractedAnswer(answer=["A", "D"], explanation=None),
        )

    def test_missing_answers_raises(self) -> None:
        with self.assertRaises(ParseError):
            extract_answer_data("<html></html>")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
