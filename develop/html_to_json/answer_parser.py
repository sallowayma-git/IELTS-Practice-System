"""Utilities for extracting and normalising answer data from IELTS HTML files.

The conversion workflow described in ``develop/JSON数据格式说明.md`` expects that
answers are converted into a strict schema before they are written into JSON.
The HTML assets in this repository expose the raw answer key inside
``correctAnswers`` objects embedded in ``<script>`` tags.  This module turns that
blob of JavaScript into structured Python data that mirrors the JSON
specification:

* ``answer`` – string for single-answer questions, list for multi-answer
  questions, nested objects if the source data already uses objects.
* ``explanation`` – optional textual explanation or hints when the HTML provides
  such metadata.

Only standard library modules are used so that the script can run in the
restricted project environment.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, Iterable, List, Optional, Tuple, Union

JsonLike = Union[str, List["JsonLike"], Dict[str, "JsonLike"]]

_COMMENT_PATTERN = re.compile(r"//.*?$|/\*.*?\*/", re.DOTALL | re.MULTILINE)
_OBJECT_HEADER_PATTERN = re.compile(
    r"(?:const|let|var)\s+(?P<name>[a-zA-Z0-9_$]+)\s*=\s*\{"
)
_CORRECT_ANSWER_KEYS = ("correctanswers", "answers", "answerkey", "solutions")
_EXPLANATION_HINT_KEYWORDS = (
    "explanation",
    "explanations",
    "analysis",
    "analyses",
    "解析",
    "hint",
    "hints",
    "tips",
    "solutions",
)


class ParseError(RuntimeError):
    """Raised when a JavaScript snippet cannot be parsed into Python data."""


@dataclass
class ExtractedAnswer:
    """Container for a single question's processed data."""

    answer: JsonLike
    explanation: Optional[str] = None


class _ObjectReader:
    """Very small parser for the limited JS objects embedded in the HTML."""

    def __init__(self, text: str) -> None:
        # Remove comments that could confuse the parser while preserving the
        # relative positioning of tokens.
        self._text = _COMMENT_PATTERN.sub("", text)
        self._length = len(self._text)
        self._index = 0

    def parse(self) -> Dict[str, JsonLike]:
        self._consume_whitespace()
        if not self._peek_char() == "{":
            raise ParseError("Expected object to start with '{'")
        return self._parse_object()

    # ------------------------------------------------------------------
    # Core parsing helpers
    def _consume_whitespace(self) -> None:
        while self._index < self._length and self._text[self._index].isspace():
            self._index += 1

    def _peek_char(self) -> Optional[str]:
        if self._index >= self._length:
            return None
        return self._text[self._index]

    def _consume_char(self) -> str:
        char = self._peek_char()
        if char is None:
            raise ParseError("Unexpected end of input")
        self._index += 1
        return char

    def _parse_object(self) -> Dict[str, JsonLike]:
        obj: Dict[str, JsonLike] = {}
        self._consume_char()  # skip '{'
        while True:
            self._consume_whitespace()
            char = self._peek_char()
            if char is None:
                raise ParseError("Unterminated object literal")
            if char == "}":
                self._consume_char()
                break
            key = self._parse_key()
            self._consume_whitespace()
            if self._consume_char() != ":":
                raise ParseError("Expected ':' after object key")
            value = self._parse_value()
            obj[key] = value
            self._consume_whitespace()
            char = self._peek_char()
            if char == ",":
                self._consume_char()
                continue
            if char == "}":
                self._consume_char()
                break
            if char is None:
                raise ParseError("Unterminated object literal")
            raise ParseError(f"Unexpected character '{char}' in object literal")
        return obj

    def _parse_array(self) -> List[JsonLike]:
        array: List[JsonLike] = []
        self._consume_char()  # skip '['
        while True:
            self._consume_whitespace()
            char = self._peek_char()
            if char is None:
                raise ParseError("Unterminated array literal")
            if char == "]":
                self._consume_char()
                break
            value = self._parse_value()
            array.append(value)
            self._consume_whitespace()
            char = self._peek_char()
            if char == ",":
                self._consume_char()
                continue
            if char == "]":
                self._consume_char()
                break
            raise ParseError(f"Unexpected character '{char}' in array literal")
        return array

    def _parse_value(self) -> JsonLike:
        self._consume_whitespace()
        char = self._peek_char()
        if char is None:
            raise ParseError("Unexpected end of value")
        if char in "'\"":
            return self._parse_string()
        if char == "[":
            return self._parse_array()
        if char == "{":
            return self._parse_object()
        # parse bare tokens (numbers, identifiers)
        token = self._parse_identifier()
        # In the current dataset all bare tokens represent numbers or words.
        # Leave them as strings to keep downstream formatting predictable.
        return token

    def _parse_key(self) -> str:
        self._consume_whitespace()
        char = self._peek_char()
        if char in "'\"":
            return self._parse_string()
        return self._parse_identifier()

    def _parse_identifier(self) -> str:
        start = self._index
        while self._index < self._length:
            char = self._text[self._index]
            if char.isalnum() or char in ("_", "-"):
                self._index += 1
                continue
            break
        if start == self._index:
            raise ParseError("Expected identifier")
        return self._text[start:self._index]

    def _parse_string(self) -> str:
        quote = self._consume_char()
        value_chars: List[str] = []
        while True:
            char = self._consume_char()
            if char == quote:
                break
            if char == "\\":
                next_char = self._consume_char()
                escapes = {
                    "\\": "\\",
                    quote: quote,
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                }
                value_chars.append(escapes.get(next_char, next_char))
                continue
            value_chars.append(char)
        return "".join(value_chars)


def _skip_js_string(text: str, start_index: int) -> int:
    quote = text[start_index]
    index = start_index + 1
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return index + 1
        index += 1
    raise ParseError("Unterminated string literal in script block")


def _skip_js_comment(text: str, start_index: int) -> int:
    if text.startswith("//", start_index):
        end = text.find("\n", start_index + 2)
        return len(text) if end == -1 else end + 1
    if text.startswith("/*", start_index):
        end = text.find("*/", start_index + 2)
        if end == -1:
            raise ParseError("Unterminated comment in script block")
        return end + 2
    return start_index + 1


def _extract_braced_block(text: str, brace_start: int) -> str:
    depth = 0
    index = brace_start
    length = len(text)
    while index < length:
        char = text[index]
        if char == "{":
            depth += 1
            index += 1
            continue
        if char == "}":
            depth -= 1
            index += 1
            if depth == 0:
                return text[brace_start:index]
            continue
        if char in ('"', "'"):
            index = _skip_js_string(text, index)
            continue
        if char == "/":
            index = _skip_js_comment(text, index)
            continue
        index += 1
    raise ParseError("Failed to locate matching '}' for object literal")


def _find_js_object(html: str, candidate_names: Iterable[str]) -> Optional[str]:
    lowercase_names = {name.lower() for name in candidate_names}
    for match in _OBJECT_HEADER_PATTERN.finditer(html):
        name = match.group("name")
        if name.lower() not in lowercase_names:
            continue
        start = match.end() - 1  # position of '{'
        return _extract_braced_block(html, start)
    return None


def _find_explanation_objects(html: str) -> List[Tuple[str, str]]:
    matches: List[Tuple[str, str]] = []
    for match in _OBJECT_HEADER_PATTERN.finditer(html):
        name = match.group("name")
        lowered = name.lower()
        if not any(keyword in lowered for keyword in _EXPLANATION_HINT_KEYWORDS):
            continue
        start = match.end() - 1
        body = _extract_braced_block(html, start)
        matches.append((name, body))
    return matches


def _normalize_single_answer(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return stripped

    uppercase_tokens = {"TRUE", "FALSE", "NOT GIVEN", "YES", "NO"}
    upper_candidate = stripped.upper()
    if upper_candidate in uppercase_tokens:
        return upper_candidate

    if re.fullmatch(r"[A-Z]", stripped, re.IGNORECASE):
        return stripped.upper()

    if re.fullmatch(r"[ivxlcdm]+", stripped, re.IGNORECASE):
        return stripped.lower()

    # Default: free-text answers should be lower-case as per the spec.
    return stripped.lower()


def _normalize_answer(value: JsonLike) -> JsonLike:
    if isinstance(value, str):
        return _normalize_single_answer(value)
    if isinstance(value, list):
        return [_normalize_answer(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_answer(val) for key, val in value.items()}
    return value


def _flatten_explanation_value(value: JsonLike) -> Optional[str]:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, list):
        parts = [part.strip() for part in value if isinstance(part, str) and part.strip()]
        return "\n".join(parts) if parts else None
    if isinstance(value, dict):
        parts: List[str] = []
        for key in ("explanation", "analysis", "hint", "tips", "reason"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                parts.append(raw.strip())
        if not parts:
            # Fallback: join any string leaves.
            for raw in value.values():
                if isinstance(raw, str) and raw.strip():
                    parts.append(raw.strip())
        return "\n".join(parts) if parts else None
    return None


def extract_answer_data(html: str) -> Dict[str, ExtractedAnswer]:
    """Parse ``correctAnswers`` and optional explanation objects from HTML."""

    answers_blob = _find_js_object(html, _CORRECT_ANSWER_KEYS)
    if not answers_blob:
        raise ParseError("No correctAnswers object found in HTML")

    answers = _ObjectReader(answers_blob).parse()
    normalized_answers = {key: _normalize_answer(val) for key, val in answers.items()}

    explanations: Dict[str, str] = {}
    for name, body in _find_explanation_objects(html):
        try:
            parsed = _ObjectReader(body).parse()
        except ParseError:
            continue
        for key, value in parsed.items():
            text = _flatten_explanation_value(value)
            if text:
                explanations[key] = text

    result: Dict[str, ExtractedAnswer] = {}
    for key, answer in normalized_answers.items():
        explanation = explanations.get(key)
        result[key] = ExtractedAnswer(answer=answer, explanation=explanation)
    return result


__all__ = ["ExtractedAnswer", "ParseError", "extract_answer_data"]
