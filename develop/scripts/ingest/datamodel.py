"""核心数据模型定义。

该模块根据《脚本开发项目配置》和《JSON数据格式说明》的要求，将HTML解析
流程中的输入输出结构固化为数据类与类型提示。所有后续子任务（解析、校验、
序列化等）都需直接复用这里的模型，避免字段漂移或重复约定。
"""
from __future__ import annotations

from dataclasses import dataclass, field
import warnings
from enum import Enum
from typing import List, Optional, Sequence, TypedDict, Union


class DifficultyLevel(int, Enum):
    """难度等级枚举，对应metadata.difficulty字段。"""

    P1 = 1
    P2 = 2
    P3 = 3

    @classmethod
    def from_source_tag(cls, tag: str) -> "DifficultyLevel":
        """将文件名中的P1/P2/P3标签映射为数字难度。"""

        normalized = tag.strip().upper()
        mapping = {"P1": cls.P1, "P2": cls.P2, "P3": cls.P3}
        try:
            return mapping[normalized]
        except KeyError as exc:  # pragma: no cover - 容错信息在上层处理
            raise ValueError(f"未知的难度标签: {tag}") from exc


class QuestionType(str, Enum):
    """题型代码全集，与JSON规范一一对应。"""

    TRUE_FALSE_NG = "true-false-ng"
    YES_NO_NG = "yes-no-ng"
    MULTIPLE_CHOICE_SINGLE = "multiple-choice-single"
    MULTIPLE_CHOICE_MULTIPLE = "multiple-choice-multiple"
    SENTENCE_COMPLETION = "sentence-completion"
    SUMMARY_COMPLETION = "summary-completion"
    NOTES_COMPLETION = "notes-completion"
    TABLE_COMPLETION = "table-completion"
    SHORT_ANSWER = "short-answer"
    PARAGRAPH_MATCHING = "paragraph-matching"
    HEADING_MATCHING = "heading-matching"
    FEATURE_MATCHING = "feature-matching"
    STATEMENT_MATCHING = "statement-matching"
    SENTENCE_ENDING_MATCHING = "sentence-ending-matching"
    CLASSIFICATION = "classification"


class ChoiceOption(TypedDict):
    """单选、多选共用的选项结构。"""

    label: str
    text: str


class DragOption(TypedDict):
    """拖拽匹配题的可选项。"""

    key: str
    text: str


class StatementContent(TypedDict):
    """判断题陈述。"""

    statement: str


class ChoiceQuestionContent(TypedDict):
    """单选、多选题题干。"""

    questionText: str
    options: List[ChoiceOption]


class SummaryCompletionContent(TypedDict, total=False):
    """摘要填空题结构。"""

    sentence: str
    wordLimit: Optional[str]
    options: List[ChoiceOption]
    canReuse: bool


class MatchingQuestionContent(TypedDict, total=False):
    """匹配题题干。"""

    statement: str
    options: List[ChoiceOption]
    canReuse: bool
    paragraphLabel: str
    feature: str
    item: str
    sentenceStart: str


QuestionContent = Union[
    StatementContent,
    ChoiceQuestionContent,
    SummaryCompletionContent,
    MatchingQuestionContent,
]

AnswerValue = Union[str, Sequence[str]]


@dataclass(slots=True)
class Paragraph:
    """文章段落，包含可选标签与正文。"""

    content: str
    label: Optional[str] = None


@dataclass(slots=True)
class Passage:
    """文章主体，包括标题与段落列表。"""

    title: str
    paragraphs: List[Paragraph] = field(default_factory=list)

    def append_paragraph(self, paragraph: Paragraph) -> None:
        self.paragraphs.append(paragraph)


@dataclass(slots=True)
class Question:
    """单道题目的标准结构。"""

    questionNumber: int
    type: QuestionType
    instruction: str
    content: QuestionContent
    answer: AnswerValue
    explanation: Optional[str] = None
    checkboxGroupName: Optional[str] = None
    occupiesQuestions: Optional[int] = None
    canReuse: Optional[bool] = None


@dataclass(slots=True)
class Metadata:
    """文章元数据字段。"""

    difficulty: DifficultyLevel
    totalQuestions: int
    questionTypes: List[QuestionType]


@dataclass(slots=True)
class Exam:
    """完整的阅读文章结构。"""

    id: str
    passage: Passage
    questions: List[Question]
    metadata: Metadata

    def validate_consistency(self) -> None:
        """执行基本一致性检查，确保早期发现结构错误。"""

        if not self.id.startswith("e") or len(self.id) != 4 or not self.id[1:].isdigit():
            raise ValueError(f"非法的文章ID: {self.id}")

        if self.metadata.totalQuestions != len(self.questions):
            raise ValueError(
                "metadata.totalQuestions与questions数量不一致: "
                f"{self.metadata.totalQuestions} != {len(self.questions)}"
            )

        normalized_types = [question.type for question in self.questions]
        if list(dict.fromkeys(normalized_types)) != self.metadata.questionTypes:
            raise ValueError("metadata.questionTypes与题目实际类型集合不匹配")

        numbers = [question.questionNumber for question in self.questions]
        if not numbers:
            raise ValueError("题目列表不能为空")

        expected_start = {
            DifficultyLevel.P1: 1,
            DifficultyLevel.P2: 14,
            DifficultyLevel.P3: 27,
        }[self.metadata.difficulty]

        if numbers[0] != expected_start:
            warnings.warn(
                "题号起始值与常规范围不符: "
                f"难度={self.metadata.difficulty.name}, 实际起始={numbers[0]}, 参考={expected_start}",
                RuntimeWarning,
                stacklevel=2,
            )

        expected = [numbers[0] + idx for idx in range(len(numbers))]
        if numbers != expected:
            raise ValueError(
                "题号不连续或数量错误: "
                f"实际={numbers}, 期望={expected}"
            )

        allowed_end = {
            DifficultyLevel.P1: 14,
            DifficultyLevel.P2: 27,
            DifficultyLevel.P3: 40,
        }[self.metadata.difficulty]
        if numbers[-1] > allowed_end:
            raise ValueError(
                "题号超过该难度允许的最大值: "
                f"实际末尾={numbers[-1]}, 上限={allowed_end}"
            )


__all__ = [
    "AnswerValue",
    "ChoiceOption",
    "ChoiceQuestionContent",
    "DifficultyLevel",
    "DragOption",
    "Exam",
    "MatchingQuestionContent",
    "Metadata",
    "Paragraph",
    "Passage",
    "Question",
    "QuestionContent",
    "QuestionType",
    "StatementContent",
    "SummaryCompletionContent",
]
