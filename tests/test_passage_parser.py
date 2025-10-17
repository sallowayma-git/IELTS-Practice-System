from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from passage_parser import parse_passage

PASSAGE_ROOT = BASE_DIR / "睡着过项目组(9.4)[134篇]" / "3. 所有文章(9.4)[134篇]"


def load_html(relative_path: str) -> str:
    html_path = PASSAGE_ROOT / relative_path
    return html_path.read_text(encoding="utf-8")


def test_parse_passage_with_paragraph_wrappers():
    html = load_html(
        "1. P1 - A Brief History of Tea 茶叶简史【高】/1. P1 - A Brief History of Tea 茶叶简史【高】.html"
    )
    passage = parse_passage(html)

    assert passage["title"] == "A Brief History of Tea"
    assert len(passage["paragraphs"]) == 8
    first_paragraph = passage["paragraphs"][0]
    assert first_paragraph["label"] == "A"
    assert first_paragraph["content"].startswith("The story of tea began in ancient China")
    assert passage["paragraphs"][-1]["label"] == "H"


def test_parse_passage_with_plain_paragraphs():
    html = load_html(
        "28. P1 - Triumph of the City 城市的胜利/28. P1 - Triumph of the City 城市的胜利.html"
    )
    passage = parse_passage(html)

    assert passage["title"] == "Book review: Triumph of the City"
    assert len(passage["paragraphs"]) == 8
    assert all(p["label"] is None for p in passage["paragraphs"])
    assert passage["paragraphs"][0]["content"].startswith("Triumph of the City, by Edward Glaeser")


def test_parse_passage_with_intro_subtitle_and_labels():
    html = load_html(
        "56. P2 - The return of monkey life 猴群回归【高】/56. P2 - The return of monkey life 猴群回归【高】.html"
    )
    passage = parse_passage(html)

    assert passage["title"] == "The Return of Monkey Life"
    assert passage["paragraphs"][0]["label"] is None
    assert passage["paragraphs"][1]["label"] == "A"
    assert passage["paragraphs"][1]["content"].startswith("Hacienda La Pacifica")
    assert passage["paragraphs"][2]["label"] == "B"
    assert passage["paragraphs"][2]["content"].startswith("Ken Glander")
