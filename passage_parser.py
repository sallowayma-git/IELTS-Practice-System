"""Parse IELTS reading passage HTML into structured data."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable, List, Optional, Union


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    parent: Optional["Node"] = None
    children: List[Union["Node", str]] = field(default_factory=list)

    def get(self, key: str, default=None):
        return self.attrs.get(key, default)

    @property
    def class_list(self) -> List[str]:
        value = self.attrs.get("class", "")
        return [item for item in value.split() if item]


class HTMLTreeBuilder(HTMLParser):
    SELF_CLOSING = {"br", "hr", "img", "input", "meta", "link", "source"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node(tag="document", attrs={})
        self.stack: List[Node] = [self.root]

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]):
        attributes = {name: (value or "") for name, value in attrs}
        node = Node(tag=tag, attrs=attributes, parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in self.SELF_CLOSING:
            self.stack.append(node)

    def handle_endtag(self, tag: str):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str):
        if not data:
            return
        current = self.stack[-1]
        current.children.append(data)

    def handle_startendtag(self, tag: str, attrs: List[tuple[str, Optional[str]]]):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_comment(self, data: str):
        # Comments are ignored for our parsing purposes.
        return


@dataclass
class Paragraph:
    label: Optional[str]
    content: str

    def as_dict(self) -> dict:
        return {"label": self.label, "content": self.content}


def parse_passage(html: str) -> dict:
    builder = HTMLTreeBuilder()
    builder.feed(html)
    root = builder.root

    left_section = _find_first(root, lambda node: node.tag == "section" and node.get("id") == "left" and "pane" in node.class_list)
    if left_section is None:
        raise ValueError("未找到左侧阅读面板（.pane#left）")

    title_node = _find_first(left_section, lambda node: node.tag == "h3")
    if title_node is None:
        raise ValueError("未找到文章标题 <h3>")

    title = _normalize_text(_gather_text(title_node))
    paragraphs = _collect_paragraphs(left_section, title_node)

    return {
        "title": title,
        "paragraphs": [paragraph.as_dict() for paragraph in paragraphs],
    }


def _collect_paragraphs(left_section: Node, title_node: Node) -> List[Paragraph]:
    paragraphs: List[Paragraph] = []
    siblings = left_section.children

    try:
        start_index = siblings.index(title_node)
    except ValueError as error:
        raise ValueError("标题节点不属于左侧面板") from error

    for item in siblings[start_index + 1 :]:
        if isinstance(item, str):
            if item.strip():
                continue
            continue

        if item.tag == "div" and item.get("id") == "divider":
            break
        if item.tag == "section" and item.get("id") == "right":
            break
        if item.tag == "div" and "practice-nav" in item.class_list:
            break
        if item.tag == "div" and "empty-space" in item.class_list:
            continue

        if item.tag == "div" and "paragraph-wrapper" in item.class_list:
            paragraph = _parse_paragraph_wrapper(item)
            if paragraph:
                paragraphs.append(paragraph)
            continue

        if item.tag in {"p", "h4", "h5"}:
            paragraph = _parse_simple_block(item)
            if paragraph:
                paragraphs.append(paragraph)
            continue

        direct_paragraphs = [child for child in item.children if isinstance(child, Node) and child.tag == "p"]
        for para_node in direct_paragraphs:
            paragraph = _parse_simple_block(para_node)
            if paragraph:
                paragraphs.append(paragraph)

    return paragraphs


def _parse_paragraph_wrapper(wrapper: Node) -> Optional[Paragraph]:
    dropzone = _find_first(wrapper, lambda node: node.get("data-paragraph") is not None)
    label = dropzone.get("data-paragraph", "").strip() if dropzone else None

    paragraph_node = _find_first(wrapper, lambda node: node.tag == "p")
    if paragraph_node is None:
        return None

    strong_label, content = _extract_paragraph_text(paragraph_node)
    if not content:
        return None

    label = label or strong_label
    return Paragraph(label=label or None, content=content)


def _parse_simple_block(node: Node) -> Optional[Paragraph]:
    allow_label = node.tag == "p"
    label, content = _extract_paragraph_text(node, allow_label=allow_label)
    if not content:
        return None
    return Paragraph(label=label or None, content=content)


def _extract_paragraph_text(node: Node, *, allow_label: bool = True) -> tuple[Optional[str], str]:
    label: Optional[str] = None
    parts: List[str] = []
    label_consumed = False

    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
            continue

        if allow_label and not label_consumed and child.tag in {"strong", "b"}:
            candidate = _normalize_text(_gather_text(child))
            if _looks_like_label(candidate):
                label = candidate
                label_consumed = True
                continue

        if child.tag == "br":
            parts.append("\n")
        else:
            parts.append(_gather_text(child))

    text = _normalize_text("".join(parts))

    if label and text.startswith(label):
        text = text[len(label) :].lstrip()

    return label, text


def _gather_text(node: Node) -> str:
    fragments: List[str] = []
    for child in node.children:
        if isinstance(child, str):
            fragments.append(child)
        elif child.tag == "br":
            fragments.append("\n")
        else:
            fragments.append(_gather_text(child))
    return "".join(fragments)


def _find_first(node: Node, predicate: Callable[[Node], bool]) -> Optional[Node]:
    for child in node.children:
        if isinstance(child, Node):
            if predicate(child):
                return child
            nested = _find_first(child, predicate)
            if nested is not None:
                return nested
    return None


def _looks_like_label(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]", text))


def _normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n+ *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


__all__ = ["parse_passage", "Paragraph"]
