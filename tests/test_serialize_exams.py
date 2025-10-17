from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.serialize_exams import ExamSerializationError, load_exams_from_file, serialize_exams


@pytest.fixture
def sample_exams() -> list[dict]:
    return [
        {
            "id": "e002",
            "passage": {"title": "Title A", "paragraphs": [{"label": None, "content": "Paragraph A"}]},
            "questions": [
                {
                    "questionNumber": 1,
                    "type": "true-false-ng",
                    "instruction": "Answer",
                    "content": {"statement": "Statement"},
                    "answer": "TRUE",
                }
            ],
            "metadata": {"difficulty": 1, "totalQuestions": 1, "questionTypes": ["true-false-ng"]},
        },
        {
            "number": 5,
            "passage": {"title": "Title B", "paragraphs": [{"label": "A", "content": "Paragraph B"}]},
            "questions": [
                {
                    "questionNumber": 2,
                    "type": "multiple-choice-single",
                    "instruction": "Choose",
                    "content": {
                        "questionText": "Q",
                        "options": [
                            {"label": "A", "text": "Opt A"},
                            {"label": "B", "text": "Opt B"},
                        ],
                    },
                    "answer": "A",
                }
            ],
            "metadata": {"difficulty": 3, "totalQuestions": 1, "questionTypes": ["multiple-choice-single"]},
        },
    ]


def test_serialize_creates_files(tmp_path: Path, sample_exams: list[dict]) -> None:
    output_dir = tmp_path / "json"
    result = serialize_exams(sample_exams, output_dir)

    assert result.total == 2
    assert result.written == 2
    assert result.skipped == 0

    exam_files = sorted(output_dir.glob("*.json"))
    assert [file_path.name for file_path in exam_files] == ["e002.json", "e005.json"]

    with exam_files[0].open(encoding="utf-8") as fh:
        payload = json.load(fh)
    assert set(payload.keys()) == {"id", "passage", "questions", "metadata"}
    assert payload["id"] == "e002"


def test_skip_existing_files(tmp_path: Path, sample_exams: list[dict]) -> None:
    output_dir = tmp_path / "json"
    serialize_exams(sample_exams, output_dir)

    target = output_dir / "e002.json"
    target.write_text("{}", encoding="utf-8")

    result = serialize_exams(sample_exams, output_dir, overwrite="skip")
    assert result.skipped == 2
    assert target.read_text(encoding="utf-8") == "{}"


def test_force_overwrites_existing_files(tmp_path: Path, sample_exams: list[dict]) -> None:
    output_dir = tmp_path / "json"
    serialize_exams(sample_exams, output_dir)

    target = output_dir / "e002.json"
    target.write_text("{}", encoding="utf-8")

    result = serialize_exams(sample_exams, output_dir, overwrite="force")
    assert result.written == 2
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["passage"]["title"] == "Title A"


def test_load_exams_accepts_various_structures(tmp_path: Path, sample_exams: list[dict]) -> None:
    source_path = tmp_path / "source.json"

    with source_path.open("w", encoding="utf-8") as fh:
        json.dump({"exams": sample_exams}, fh, ensure_ascii=False)
    exams = load_exams_from_file(source_path)
    assert [exam["id"] for exam in exams] == ["e002", "e005"]

    with source_path.open("w", encoding="utf-8") as fh:
        json.dump({"e010": sample_exams[0]}, fh, ensure_ascii=False)
    exams = load_exams_from_file(source_path)
    assert exams[0]["id"] == "e010"


def test_missing_required_fields_raise_error(tmp_path: Path) -> None:
    bad_data = [{"id": "e001", "passage": {}, "metadata": {}}]
    source_path = tmp_path / "bad.json"
    source_path.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(ExamSerializationError):
        load_exams_from_file(source_path)
