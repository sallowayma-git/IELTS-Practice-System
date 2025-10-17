"""Generic question parsing strategies for IELTS ingestion scripts.

This module defines a small strategy engine capable of interpreting different
question layouts (multiple choice, fill-in-the-blank, drag-and-drop, etc.) from
pre-tokenised content blocks.  Each strategy receives an ordered sequence of
``QuestionBlock`` objects describing the textual fragments extracted upstream
from HTML and yields normalized ``Question`` records.

The parser focuses on:
* preserving the explicit question type label;
* extracting question numbers, stems, and option text; and
* handling shared stems or option pools while maintaining numerical order.

The strategies here do **not** perform HTML parsing directly; upstream code must
convert the raw document into ``QuestionBlock`` instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Question:
    """Normalized question payload.

    Attributes
    ----------
    number:
        The question number (1-indexed, sequential within the original
        assessment section).
    stem:
        The textual prompt shown to the candidate.
    options:
        Available option text.  Blank for gap-filling questions.
    qtype:
        A short label representing the question type (e.g. ``"choice"`` or
        ``"fill_blank"``).
    metadata:
        Optional dictionary for carrying auxiliary information (for example,
        shared context identifiers or hints).
    """

    number: int
    stem: str
    options: Tuple[str, ...]
    qtype: str
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class QuestionBlock:
    """Intermediate representation for pre-tokenised question fragments."""

    numbers: Sequence[int]
    stem: Optional[str] = None
    options: Optional[Sequence[str]] = None
    is_shared_options: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class QuestionParseError(ValueError):
    """Raised when a block sequence cannot be converted into ordered questions."""


class BaseStrategy:
    """Contract for strategy implementations."""

    qtype: str

    def parse(self, blocks: Iterable[QuestionBlock]) -> List[Question]:
        raise NotImplementedError

    # Utility helpers -----------------------------------------------------
    @staticmethod
    def _expand_numbers(numbers: Sequence[int]) -> List[int]:
        if not numbers:
            raise QuestionParseError("Question block missing question numbers")
        return list(numbers)

    @staticmethod
    def _ensure_sequence(questions: Sequence[Question]) -> None:
        ordered = sorted(questions, key=lambda q: q.number)
        for idx, question in enumerate(ordered, start=ordered[0].number if ordered else 1):
            if question.number != idx:
                raise QuestionParseError(
                    f"Question numbering is not sequential (expected {idx}, got {question.number})"
                )

    @staticmethod
    def _clone_options(options: Optional[Sequence[str]]) -> Tuple[str, ...]:
        return tuple(options or ())


class ChoiceStrategy(BaseStrategy):
    """Parser for single/multiple choice questions."""

    qtype = "choice"

    def __init__(self, allow_empty_options: bool = False) -> None:
        self._allow_empty_options = allow_empty_options

    def parse(self, blocks: Iterable[QuestionBlock]) -> List[Question]:
        questions: List[Question] = []
        shared_options: Tuple[str, ...] = ()

        for block in blocks:
            if block.is_shared_options:
                shared_options = self._clone_options(block.options)
                continue

            numbers = self._expand_numbers(block.numbers)
            options = self._clone_options(block.options) or shared_options

            if not options and not self._allow_empty_options:
                raise QuestionParseError(
                    f"Choice question {numbers} missing options and no shared pool present"
                )

            for number in numbers:
                questions.append(
                    Question(
                        number=number,
                        stem=block.stem or "",
                        options=options,
                        qtype=self.qtype,
                        metadata=dict(block.metadata),
                    )
                )

        self._ensure_sequence(questions)
        return sorted(questions, key=lambda q: q.number)


class FillBlankStrategy(BaseStrategy):
    """Parser for gap-filling questions without explicit options."""

    qtype = "fill_blank"

    def parse(self, blocks: Iterable[QuestionBlock]) -> List[Question]:
        questions: List[Question] = []

        for block in blocks:
            if block.is_shared_options:
                # Gap-fill questions rarely define shared options; ignore such
                # blocks but allow metadata to flow if provided.
                continue

            numbers = self._expand_numbers(block.numbers)
            for number in numbers:
                questions.append(
                    Question(
                        number=number,
                        stem=block.stem or "",
                        options=(),
                        qtype=self.qtype,
                        metadata=dict(block.metadata),
                    )
                )

        self._ensure_sequence(questions)
        return sorted(questions, key=lambda q: q.number)


class DragDropStrategy(BaseStrategy):
    """Parser for drag-and-drop or matching style questions."""

    qtype = "drag_drop"

    def parse(self, blocks: Iterable[QuestionBlock]) -> List[Question]:
        questions: List[Question] = []
        shared_options: Tuple[str, ...] = ()

        for block in blocks:
            if block.is_shared_options:
                shared_options = self._clone_options(block.options)
                continue

            numbers = self._expand_numbers(block.numbers)
            # Drag-and-drop almost always leverages a shared pool.  If a block
            # defines its own options they supersede the shared pool.
            options = self._clone_options(block.options) or shared_options

            if not options:
                raise QuestionParseError(
                    f"Drag-and-drop question {numbers} missing draggable options"
                )

            for number in numbers:
                questions.append(
                    Question(
                        number=number,
                        stem=block.stem or "",
                        options=options,
                        qtype=self.qtype,
                        metadata=dict(block.metadata),
                    )
                )

        self._ensure_sequence(questions)
        return sorted(questions, key=lambda q: q.number)


class QuestionParser:
    """Facade that dispatches to specialised strategies based on question type."""

    def __init__(self) -> None:
        self._strategies: Dict[str, BaseStrategy] = {
            "choice": ChoiceStrategy(),
            "fill_blank": FillBlankStrategy(),
            "drag_drop": DragDropStrategy(),
        }

    def register(self, name: str, strategy: BaseStrategy) -> None:
        if name in self._strategies:
            raise ValueError(f"Strategy '{name}' already registered")
        self._strategies[name] = strategy

    def parse(self, qtype: str, blocks: Iterable[QuestionBlock]) -> List[Question]:
        try:
            strategy = self._strategies[qtype]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unknown question type '{qtype}'") from exc

        return strategy.parse(blocks)


__all__ = [
    "Question",
    "QuestionBlock",
    "QuestionParseError",
    "QuestionParser",
    "ChoiceStrategy",
    "FillBlankStrategy",
    "DragDropStrategy",
]
