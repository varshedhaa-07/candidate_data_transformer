"""Tests for PDF resume parsing."""

import pytest

from parsers.resume_parser import ResumeParser


RESUME_TEXT = """
Jane Doe
Senior Backend Engineer
jane@example.com | +91 987 654 3210
Skills
Python, CPP, ReactJS
Experience
Acme Corp - Backend Engineer
Built APIs and services.
Education
B.Tech Computer Science
"""


def test_resume_parser_extracts_candidate_fields(monkeypatch, tmp_path) -> None:
    resume_path = tmp_path / "resume.pdf"
    parser = ResumeParser()
    monkeypatch.setattr(parser, "_extract_text", lambda path: RESUME_TEXT)

    candidate = parser.parse(resume_path)

    assert candidate.full_name == "Jane Doe"
    assert candidate.headline == "Senior Backend Engineer"
    assert candidate.emails == ["jane@example.com"]
    assert candidate.phones == ["+91 987 654 3210"]
    assert [skill.name for skill in candidate.skills] == ["Python", "CPP", "ReactJS"]
    assert candidate.experience[0].description.startswith("Acme Corp")
    assert candidate.education[0].description == "B.Tech Computer Science"
    assert {record.source for record in candidate.provenance} == {"resume_pdf"}


def test_resume_parser_leaves_missing_fields_empty(monkeypatch, tmp_path) -> None:
    resume_path = tmp_path / "resume.pdf"
    parser = ResumeParser()
    monkeypatch.setattr(parser, "_extract_text", lambda path: "Unstructured text only")

    candidate = parser.parse(resume_path)

    assert candidate.full_name is None
    assert candidate.emails == []
    assert candidate.phones == []
    assert candidate.skills == []
    assert candidate.education == []
    assert candidate.experience == []


def test_resume_parser_rejects_non_pdf() -> None:
    with pytest.raises(ValueError, match="only supports PDF"):
        ResumeParser().parse("resume.txt")
