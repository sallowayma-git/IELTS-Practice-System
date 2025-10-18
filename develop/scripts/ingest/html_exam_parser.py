"""HTML→JSON解析器初版。"""

from __future__ import annotations

import ast
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

from .datamodel import (
    ChoiceOption,
    DifficultyLevel,
    Exam,
    MatchingQuestionContent,
    Metadata,
    Paragraph,
    Passage,
    Question,
    QuestionType,
    SummaryCompletionContent,
)


@dataclass
class Node:
    """极简DOM节点，仅保留结构和文本顺序。"""

    tag: Optional[str]
    attrs: Dict[str, str]
    contents: List[Union["Node", str]]

    def add_child(self, child: "Node") -> None:
        self.contents.append(child)

    def add_text(self, data: str) -> None:
        if data:
            self.contents.append(data)

    def get_text(self, strip: bool = True) -> str:
        parts: List[str] = []
        for item in self.contents:
            if isinstance(item, Node):
                if item.tag == "br":
                    parts.append("\n")
                else:
                    parts.append(item.get_text(strip=False))
            else:
                parts.append(item)
        text = unescape("".join(parts))
        if strip:
            text = " ".join(text.split())
        return text

    def find_first(self, tag: Optional[str] = None, **attrs: str) -> Optional["Node"]:
        for node in self.iter(tag, **attrs):
            return node
        return None

    def iter(self, tag: Optional[str] = None, **attrs: str) -> Iterator["Node"]:
        for item in self.contents:
            if isinstance(item, Node):
                if self._match(item, tag, attrs):
                    yield item
                yield from item.iter(tag, **attrs)

    def iter_children(self, tag: Optional[str] = None, **attrs: str) -> Iterator["Node"]:
        for item in self.contents:
            if isinstance(item, Node) and self._match(item, tag, attrs):
                yield item

    def _match(self, node: "Node", tag: Optional[str], attrs: Dict[str, str]) -> bool:
        if tag is not None and node.tag != tag:
            return False
        for key, value in attrs.items():
            actual = node.attrs.get(key)
            if key == "class" and actual is not None:
                classes = set(actual.split())
                if value not in classes:
                    return False
            else:
                if actual != value:
                    return False
        return True


class MiniHTMLParser(HTMLParser):
    """构建轻量DOM的解析器。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.root = Node(tag="root", attrs={}, contents=[])
        self._stack: List[Node] = [self.root]

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag == "br":
            self._stack[-1].add_text("\n")
            return
        node = Node(tag=tag, attrs={k: v or "" for k, v in attrs}, contents=[])
        self._stack[-1].add_child(node)
        if tag not in {"input", "img", "br", "meta", "link"}:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag == "br":
            self._stack[-1].add_text("\n")
            return
        node = Node(tag=tag, attrs={k: v or "" for k, v in attrs}, contents=[])
        self._stack[-1].add_child(node)

    def handle_endtag(self, tag: str) -> None:
        while len(self._stack) > 1:
            node = self._stack.pop()
            if node.tag == tag:
                break

    def handle_data(self, data: str) -> None:
        if not data:
            return
        if any(parent.tag in {"script", "style"} for parent in self._stack[1:]):
            return
        self._stack[-1].add_text(data)


def parse_html(content: str) -> Node:
    parser = MiniHTMLParser()
    parser.feed(content)
    parser.close()
    return parser.root


def parse_exam(html_path: Path) -> Exam:
    raw = html_path.read_text(encoding="utf-8")
    root = parse_html(raw)

    exam_id, difficulty = _infer_identity(html_path.name)
    passage = _parse_passage(root)
    questions = _parse_questions(root, raw)
    metadata = Metadata(
        difficulty=difficulty,
        totalQuestions=len(questions),
        questionTypes=_collect_question_types(questions),
    )

    exam = Exam(id=exam_id, passage=passage, questions=questions, metadata=metadata)
    exam.validate_consistency()
    return exam


def _infer_identity(filename: str) -> Tuple[str, DifficultyLevel]:
    match = re.search(r"(?P<num>\d+)\.\s*(?P<difficulty>P[123])", filename)
    if not match:
        raise ValueError(f"无法从文件名推断编号和难度: {filename}")
    number = int(match.group("num"))
    difficulty = DifficultyLevel.from_source_tag(match.group("difficulty"))
    exam_id = f"e{number:03d}"
    return exam_id, difficulty


def _parse_passage(root: Node) -> Passage:
    left_section = _find_passage_container(root)
    if left_section is None:
        raise ValueError("未找到文章内容区域 (#left)")

    title_node = (
        left_section.find_first("h3")
        or left_section.find_first("h2")
        or left_section.find_first("h1")
    )
    if title_node is None:
        raise ValueError("文章缺少标题")
    title = title_node.get_text()

    paragraphs: List[Paragraph] = []
    collect = False
    for item in left_section.contents:
        if item is title_node:
            collect = True
            continue
        if not collect:
            continue
        if isinstance(item, Node):
            if _is_empty_space_marker(item):
                break
            paragraphs.extend(_collect_paragraphs(item))
        else:
            text = _normalize_inline_text(item)
            if text:
                paragraphs.append(Paragraph(content=text, label=None))
    return Passage(title=title, paragraphs=paragraphs)


def _is_empty_space_marker(node: Node) -> bool:
    return node.tag == "div" and "empty-space" in node.attrs.get("class", "").split()


def _is_paragraph_label_container(node: Node) -> bool:
    classes = set(node.attrs.get("class", "").split())
    if not classes:
        return False
    if node.tag == "div" and "paragraph-dropzone" in classes:
        return True
    if node.tag in {"span", "div"} and "paragraph-label" in classes:
        return True
    if node.tag == "div" and "dropped-items" in classes:
        return True
    return False


def _collect_paragraphs(node: Node) -> List[Paragraph]:
    paragraphs: List[Paragraph] = []

    def _walk(current: Node) -> None:
        if _is_paragraph_label_container(current):
            return
        if current.tag == "p":
            label, text = _resolve_paragraph_label(current)
            if text:
                paragraphs.append(Paragraph(content=text, label=label))
            return
        for child in current.contents:
            if isinstance(child, Node):
                if _is_empty_space_marker(child):
                    continue
                _walk(child)
            else:
                text = _normalize_inline_text(child)
                if text:
                    paragraphs.append(Paragraph(content=text, label=None))

    _walk(node)
    return paragraphs


def _resolve_paragraph_label(node: Node) -> Tuple[Optional[str], str]:
    label = node.attrs.get("data-label") or None
    text = node.get_text()
    if label:
        cleaned = _strip_leading_label(text, label)
        return label, cleaned or text

    label = _extract_label_from_leading_child(node)
    if label is not None:
        cleaned = _strip_leading_label(text, label)
        return label, cleaned or text

    return None, text


def _extract_label_from_leading_child(node: Node) -> Optional[str]:
    if not node.contents:
        return None
    first = node.contents[0]
    if isinstance(first, Node):
        raw = first.get_text().strip()
    else:
        raw = str(first).strip()
    if not raw:
        return None
    match = re.search(r"([A-Z]|[IVXLCDM]{1,6})$", raw)
    if not match:
        return None
    candidate = match.group(1)
    if re.fullmatch(r"[A-Z]", candidate) or re.fullmatch(r"[IVXLCDM]{1,6}", candidate):
        return candidate
    return None


def _normalize_inline_text(data: str) -> str:
    text = unescape(data)
    text = " ".join(text.split())
    return text


def _parse_questions(root: Node, raw_html: str) -> List[Question]:
    right_section = _find_question_container(root)
    if right_section is None:
        raise ValueError("未找到题目区域 (#right)")

    correct_answers = _extract_answer_key(raw_html)
    questions: List[Question] = []
    heading_targets = _collect_heading_targets(root)

    for group in right_section.iter_children("div", **{"class": "group"}):
        group_questions = _parse_group(group, correct_answers, heading_targets)
        questions.extend(group_questions)

    return sorted(questions, key=lambda q: q.questionNumber)


def _extract_answer_key(raw_html: str) -> Dict[str, str]:
    match = re.search(r"const\s+correctAnswers\s*=\s*\{(?P<body>.*?)\}\s*;", raw_html, re.S)
    if not match:
        return {}
    body = match.group("body")
    python_literal = "{" + body + "}"
    cleaned = re.sub(r"//.*", "", python_literal)
    cleaned = re.sub(r"(?P<key>\b\w+\b)\s*:", r"'\g<key>':", cleaned)
    try:
        return ast.literal_eval(cleaned)
    except SyntaxError as exc:  # pragma: no cover - 解析失败由上层处理
        raise ValueError("无法解析correctAnswers字典") from exc


def _parse_group(
    group: Node, answers: Dict[str, str], heading_targets: Dict[int, str]
) -> List[Question]:
    if group.find_first("table", **{"class": "matching-table"}):
        return _parse_matching_table_group(group, answers)
    if group.find_first("div", **{"class": "headings-pool"}):
        return _parse_heading_group(group, answers, heading_targets)
    if group.find_first("div", **{"class": "match-question-item"}):
        return _parse_matching_group(group, answers)
    if group.find_first("div", **{"class": "summary-completion"}):
        return _parse_summary_group(group, answers)
    return _parse_choice_group(group, answers)


def _gather_instruction(group: Node) -> str:
    instructions: List[str] = []
    for item in group.contents:
        if isinstance(item, Node):
            classes = item.attrs.get("class", "")
            if "question-item" in classes.split():
                break
            if item.tag == "div" and "options-pool" in classes.split():
                break
            text = item.get_text()
            if text:
                instructions.append(text)
            if item.tag == "ul":
                for li in item.iter_children("li"):
                    li_text = li.get_text()
                    if li_text:
                        instructions.append(li_text)
    return "\n".join(dict.fromkeys(instructions))


def _find_passage_container(root: Node) -> Optional[Node]:
    candidates = [
        ("section", {"id": "left"}),
        ("div", {"id": "passage-pane"}),
        ("section", {"class": "passage-pane"}),
        ("div", {"class": "passage-pane"}),
    ]
    for tag, attrs in candidates:
        node = root.find_first(tag, **attrs)
        if node is not None:
            return node
    return None


def _find_question_container(root: Node) -> Optional[Node]:
    candidates = [
        ("section", {"id": "right"}),
        ("div", {"id": "questions-pane"}),
        ("section", {"class": "questions-pane"}),
        ("div", {"class": "questions-pane"}),
    ]
    for tag, attrs in candidates:
        node = root.find_first(tag, **attrs)
        if node is not None:
            return node
    return None


def _collect_heading_targets(root: Node) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    left_section = _find_passage_container(root)
    if left_section is None:
        return mapping

    for wrapper in left_section.iter("div", **{"class": "paragraph-wrapper"}):
        anchor_id = wrapper.attrs.get("id", "")
        match = re.search(r"q(\d+)", anchor_id)
        if not match:
            continue
        number = int(match.group(1))
        dropzone = wrapper.find_first("div", **{"class": "paragraph-dropzone"})
        label: Optional[str] = None
        if dropzone:
            label = dropzone.attrs.get("data-paragraph") or None
            if label is None:
                label_span = dropzone.find_first("span")
                if label_span:
                    label_match = re.search(r"Paragraph\s+([A-Z]+)", label_span.get_text())
                    if label_match:
                        label = label_match.group(1)
        if label is None:
            strong = wrapper.find_first("strong")
            if strong:
                label = strong.get_text().strip()
        if label:
            mapping[number] = label.strip()
    return mapping


def _extract_question_range(group: Node) -> Optional[Tuple[int, int]]:
    header = group.find_first("h4")
    if header is None:
        return None
    text = header.get_text()
    match = re.search(r"Questions?\s+(\d+)(?:\s*[–-]\s*(\d+))?", text)
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else start
    return start, end


def _strip_leading_label(text: str, label: str) -> str:
    if not label:
        return text
    pattern = re.compile(rf"^{re.escape(label)}[\s\.\-\):：]+", re.I)
    return pattern.sub("", text, count=1).strip()


def _clone_options(options: List[ChoiceOption]) -> List[ChoiceOption]:
    return [ChoiceOption(label=opt["label"], text=opt["text"]) for opt in options]


def _extract_drag_options(pool: Optional[Node], label_attr: str) -> List[ChoiceOption]:
    options: List[ChoiceOption] = []
    if pool is None:
        return options
    for item in pool.iter("div", **{"class": "drag-item"}):
        label = (
            item.attrs.get(label_attr)
            or item.attrs.get("data-option")
            or item.attrs.get("data-heading")
            or ""
        )
        text = item.get_text().strip()
        cleaned_text = _strip_leading_label(text, label)
        options.append(
            ChoiceOption(
                label=label or cleaned_text,
                text=cleaned_text or text,
            )
        )
    return options


def _parse_heading_group(
    group: Node, answers: Dict[str, str], heading_targets: Dict[int, str]
) -> List[Question]:
    instruction = _gather_instruction(group)
    options_pool = group.find_first("div", **{"class": "headings-pool"})
    options = _extract_drag_options(options_pool, "data-heading")
    question_range = _extract_question_range(group)
    if question_range:
        start, end = question_range
        numbers = [num for num in sorted(heading_targets) if start <= num <= end]
    else:
        numbers = sorted(heading_targets)

    questions: List[Question] = []
    for number in numbers:
        paragraph_label = heading_targets.get(number)
        if not paragraph_label:
            continue
        content: MatchingQuestionContent = {
            "paragraphLabel": paragraph_label,
            "options": _clone_options(options),
        }
        questions.append(
            Question(
                questionNumber=number,
                type=QuestionType.HEADING_MATCHING,
                instruction=instruction,
                content=content,
                answer=answers.get(f"q{number}") or "",
            )
        )
    return questions


def _determine_matching_table_type(instruction: str) -> Tuple[QuestionType, str]:
    normalized = instruction.lower()
    if "heading" in normalized:
        return QuestionType.HEADING_MATCHING, "paragraphLabel"
    if "paragraph" in normalized:
        return QuestionType.PARAGRAPH_MATCHING, "statement"
    if "classify" in normalized or "classification" in normalized:
        return QuestionType.CLASSIFICATION, "statement"
    if "feature" in normalized or "person" in normalized:
        return QuestionType.FEATURE_MATCHING, "statement"
    return QuestionType.CLASSIFICATION, "statement"


def _parse_matching_table_group(group: Node, answers: Dict[str, str]) -> List[Question]:
    instruction = _gather_instruction(group)
    table = group.find_first("table", **{"class": "matching-table"})
    if table is None:
        return []

    thead = table.find_first("thead")
    options: List[ChoiceOption] = []
    if thead:
        header_row = thead.find_first("tr")
        if header_row:
            header_cells = list(header_row.iter_children("th"))
            for cell in header_cells[1:]:
                label = cell.get_text().strip()
                if label:
                    options.append(ChoiceOption(label=label, text=label))

    tbody = table.find_first("tbody")
    if tbody is None:
        return []

    question_type, statement_key = _determine_matching_table_type(instruction)
    reuse = "more than once" in instruction.lower()
    questions: List[Question] = []

    for row in tbody.iter_children("tr"):
        cells = list(row.iter_children("td"))
        if not cells:
            continue
        number_node = cells[0].find_first("strong")
        if number_node is None:
            continue
        number_match = re.search(r"\d+", number_node.get_text())
        if not number_match:
            continue
        number = int(number_match.group())
        statement_text = cells[0].get_text()
        statement = re.sub(r"^\d+\s*", "", statement_text).strip()

        if not options:
            # 尝试从本行的输入元素推断选项
            row_options: List[ChoiceOption] = []
            for cell in cells[1:]:
                input_node = cell.find_first("input")
                if input_node and "value" in input_node.attrs:
                    value = input_node.attrs.get("value", "")
                    row_options.append(ChoiceOption(label=value, text=value))
            if row_options:
                options = row_options

        content: MatchingQuestionContent = {
            statement_key: statement,
            "options": _clone_options(options),
        }
        if reuse:
            content["canReuse"] = True

        questions.append(
            Question(
                questionNumber=number,
                type=question_type,
                instruction=instruction,
                content=content,
                answer=answers.get(f"q{number}") or "",
                canReuse=reuse or None,
            )
        )

    return questions


def _parse_matching_group(group: Node, answers: Dict[str, str]) -> List[Question]:
    instruction = _gather_instruction(group)
    reuse = "may use any letter" in instruction.lower()

    options_block = group.find_first("div", **{"class": "options-pool"})
    options = _extract_drag_options(options_block, "data-option")

    questions: List[Question] = []
    for item in group.iter_children("div", **{"class": "match-question-item"}):
        number_node = item.find_first("strong")
        if number_node is None:
            continue
        number = int(number_node.get_text())
        statement_node = item.find_first("p")
        statement = statement_node.get_text() if statement_node else ""
        statement = re.sub(r"^\d+\s*", "", statement).strip()
        answer_key = answers.get(f"q{number}")
        content: MatchingQuestionContent = {
            "statement": statement,
            "options": _clone_options(options),
        }
        if reuse:
            content["canReuse"] = True
        questions.append(
            Question(
                questionNumber=number,
                type=QuestionType.FEATURE_MATCHING,
                instruction=instruction,
                content=content,
                answer=answer_key or "",
                canReuse=reuse or None,
            )
        )
    return questions


def _parse_choice_group(group: Node, answers: Dict[str, str]) -> List[Question]:
    instruction = _gather_instruction(group)
    questions: List[Question] = []

    for item in _iter_choice_items(group):
        number = _extract_question_number(item)
        if number is None:
            continue
        question_text = _extract_question_prompt(item)
        options = _extract_choice_options(item)
        if not options:
            fallback = _fallback_boolean_options(instruction)
            if fallback:
                options = fallback
        question_type = _infer_choice_type(options, instruction)

        questions.append(
            Question(
                questionNumber=number,
                type=question_type,
                instruction=instruction,
                content={"questionText": question_text, "options": options},
                answer=answers.get(f"q{number}") or "",
            )
        )
    return questions


def _iter_choice_items(group: Node) -> Iterator[Node]:
    known_classes = {
        "question-item",
        "tfng-item",
        "yn-item",
        "mcq-item",
        "choice-item",
    }
    for item in group.contents:
        if not isinstance(item, Node):
            continue
        if item.tag != "div":
            continue
        classes = set(item.attrs.get("class", "").split())
        if known_classes & classes:
            yield item
            continue
        if item.find_first("strong") and item.find_first("input"):
            yield item


def _extract_question_number(node: Node) -> Optional[int]:
    number_node = node.find_first("strong")
    if number_node is None:
        return None
    match = re.search(r"\d+", number_node.get_text())
    if not match:
        return None
    return int(match.group())


def _extract_question_prompt(node: Node) -> str:
    prompt_node = node.find_first("p")
    if prompt_node:
        prompt_text = prompt_node.get_text()
        return re.sub(r"^\d+\s*", "", prompt_text).strip()
    text = node.get_text()
    return re.sub(r"^\d+\s*", "", text).strip()


def _parse_summary_group(group: Node, answers: Dict[str, str]) -> List[Question]:
    instruction = _gather_instruction(group)
    word_limit = _extract_word_limit(instruction)
    summary_block = group.find_first("div", **{"class": "summary-completion"})
    if summary_block is None:
        return []

    paragraphs = list(summary_block.iter_children("p"))
    options_block = group.find_first("div", **{"class": "options-pool"})
    options = _extract_drag_options(options_block, "data-option")
    reuse = "more than once" in instruction.lower()
    questions: List[Question] = []

    for paragraph in paragraphs:
        text, placeholders = _render_paragraph_with_placeholders(paragraph)
        ordered = sorted(
            ((text.index(token), number, token) for number, token in placeholders.items()),
            key=lambda item: item[0],
        )
        last_cut = 0
        for idx, (position, number, token) in enumerate(ordered):
            next_start = ordered[idx + 1][0] if idx + 1 < len(ordered) else len(text)
            segment = text[last_cut:next_start]
            last_cut = position + len(token)
            segment = _clean_summary_segment(segment, token)
            content: SummaryCompletionContent = {"sentence": segment.strip()}
            if word_limit:
                content["wordLimit"] = word_limit
            if options:
                content["options"] = _clone_options(options)
            if reuse:
                content["canReuse"] = True
            questions.append(
                Question(
                    questionNumber=number,
                    type=QuestionType.SUMMARY_COMPLETION,
                    instruction=instruction,
                    content=content,
                    answer=answers.get(f"q{number}") or "",
                )
            )

    return questions


def _extract_choice_options(item: Node) -> List[ChoiceOption]:
    options: List[ChoiceOption] = []
    for label_node in item.iter("label"):
        text = label_node.get_text().strip()
        if not text:
            continue
        input_node = label_node.find_first("input")
        value = input_node.attrs.get("value") if input_node else None
        label_key = value or ""
        body = text
        if not label_key:
            match = re.match(r"^([A-Z])(?:[\.)]|\s)+(.+)$", text)
            if match:
                label_key = match.group(1)
                body = match.group(2).strip()
        else:
            body = _strip_leading_label(text, label_key)
        if not label_key:
            label_key = body
        options.append(ChoiceOption(label=label_key, text=body))
    return options


def _infer_choice_type(options: List[ChoiceOption], instruction: str) -> QuestionType:
    normalized = {option["text"].strip().upper() for option in options}
    if normalized == {"TRUE", "FALSE", "NOT GIVEN"}:
        return QuestionType.TRUE_FALSE_NG
    if normalized == {"YES", "NO", "NOT GIVEN"}:
        return QuestionType.YES_NO_NG
    if re.search(r"choose\s+(two|three|four)\s+letters", instruction, re.I):
        return QuestionType.MULTIPLE_CHOICE_MULTIPLE
    return QuestionType.MULTIPLE_CHOICE_SINGLE


def _fallback_boolean_options(instruction: str) -> List[ChoiceOption]:
    upper = instruction.upper()

    def _build_options(labels: Sequence[str]) -> List[ChoiceOption]:
        return [ChoiceOption(label=label, text=label) for label in labels]

    if all(token in upper for token in ("TRUE", "FALSE", "NOT GIVEN")):
        return _build_options(["True", "False", "Not Given"])
    if all(token in upper for token in ("YES", "NO", "NOT GIVEN")):
        return _build_options(["Yes", "No", "Not Given"])
    return []


def _render_paragraph_with_placeholders(paragraph: Node) -> Tuple[str, Dict[int, str]]:
    buffer: List[str] = []
    placeholders: Dict[int, str] = {}

    for item in paragraph.contents:
        if isinstance(item, Node):
            if item.tag == "strong":
                number = int(item.get_text())
                placeholder = f"[[BLANK-{number}]]"
                placeholders[number] = placeholder
                buffer.append(placeholder)
            elif item.tag == "input":
                continue
            else:
                buffer.append(item.get_text(strip=False))
        else:
            buffer.append(item)

    paragraph_text = unescape("".join(buffer))
    paragraph_text = re.sub(r"\s+", " ", paragraph_text).strip()
    return paragraph_text, placeholders


def _clean_summary_segment(segment: str, token: str) -> str:
    marker = "<<CURRENT_BLANK>>"
    segment = segment.replace(token, marker)
    segment = re.sub(r"\[\[BLANK-\d+\]\]", "", segment)
    segment = segment.replace(marker, "_____")
    segment = segment.strip()
    if segment.endswith("_____"):
        segment = segment[:-5].rstrip()
    if segment.endswith(","):
        segment = segment[:-1].rstrip()
    segment = segment.lstrip()
    if segment.startswith("."):
        segment = segment.lstrip(". ")
    if segment and segment[0].islower():
        upper = re.search(r"[A-Z]", segment)
        if upper:
            segment = segment[upper.start():]
    return segment


def _extract_word_limit(instruction: str) -> Optional[str]:
    pattern = re.compile(
        r"Choose\s+(?P<limit>[A-Z\s/]+?)\s+(?:from the passage|for each answer)",
        re.IGNORECASE,
    )
    for line in instruction.splitlines():
        match = pattern.search(line)
        if match:
            return match.group("limit").strip()
    return None


def _collect_question_types(questions: Iterable[Question]) -> List[QuestionType]:
    seen: Dict[QuestionType, None] = {}
    for question in questions:
        if question.type not in seen:
            seen[question.type] = None
    return list(seen.keys())


def _serialize_answer(answer: AnswerValue) -> Any:
    if isinstance(answer, str):
        return answer
    return list(answer)


def exam_to_payload(exam: Exam) -> Dict[str, Any]:
    return {
        "id": exam.id,
        "passage": {
            "title": exam.passage.title,
            "paragraphs": [
                {"label": paragraph.label, "content": paragraph.content}
                for paragraph in exam.passage.paragraphs
            ],
        },
        "questions": [
            {
                "questionNumber": question.questionNumber,
                "type": question.type.value,
                "instruction": question.instruction,
                "content": deepcopy(question.content),
                "answer": _serialize_answer(question.answer),
                **(
                    {"explanation": question.explanation}
                    if question.explanation is not None
                    else {}
                ),
                **(
                    {"checkboxGroupName": question.checkboxGroupName}
                    if question.checkboxGroupName is not None
                    else {}
                ),
                **(
                    {"occupiesQuestions": question.occupiesQuestions}
                    if question.occupiesQuestions is not None
                    else {}
                ),
                **(
                    {"canReuse": question.canReuse}
                    if question.canReuse is not None
                    else {}
                ),
            }
            for question in exam.questions
        ],
        "metadata": {
            "difficulty": exam.metadata.difficulty.value,
            "totalQuestions": exam.metadata.totalQuestions,
            "questionTypes": [t.value for t in exam.metadata.questionTypes],
        },
    }


def export_exam_to_json(exam: Exam, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{exam.id}.json"
    payload = exam_to_payload(exam)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def convert_html_to_json(html_path: Path, output_dir: Path) -> Path:
    exam = parse_exam(html_path)
    return export_exam_to_json(exam, output_dir)

