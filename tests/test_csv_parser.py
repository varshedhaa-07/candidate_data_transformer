"""Tests for recruiter CSV parsing."""

import pytest

from parsers.recruiter_csv_parser import RecruiterCSVParser


def test_recruiter_csv_parser_populates_candidate(tmp_path) -> None:
    csv_path = tmp_path / "recruiter.csv"
    csv_path.write_text(
        "name,email,phone,current_company,title\n"
        "Jane Doe,jane@example.com,9876543210,Acme,Backend Engineer\n",
        encoding="utf-8",
    )

    candidate = RecruiterCSVParser().parse(csv_path)

    assert candidate.full_name == "Jane Doe"
    assert candidate.emails == ["jane@example.com"]
    assert candidate.phones == ["9876543210"]
    assert candidate.experience[0].company == "Acme"
    assert candidate.experience[0].title == "Backend Engineer"
    assert {record.field_name for record in candidate.provenance} == {
        "full_name",
        "emails",
        "phones",
        "experience.company",
        "experience.title",
    }


def test_recruiter_csv_parser_skips_malformed_rows(tmp_path) -> None:
    csv_path = tmp_path / "recruiter.csv"
    csv_path.write_text(
        "name,email,phone,current_company,title\n"
        "Bad Row,bad@example.com,123,Company,Title,extra\n"
        "Jane Doe,jane@example.com,9876543210,Acme,Backend Engineer\n",
        encoding="utf-8",
    )

    candidate = RecruiterCSVParser().parse(csv_path)

    assert candidate.full_name == "Jane Doe"
    assert candidate.candidate_id.endswith(":3")


def test_recruiter_csv_parser_rejects_missing_headers(tmp_path) -> None:
    csv_path = tmp_path / "recruiter.csv"
    csv_path.write_text("name,email\nJane Doe,jane@example.com\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required fields"):
        RecruiterCSVParser().parse(csv_path)


def test_recruiter_csv_parser_rejects_all_malformed_rows(tmp_path) -> None:
    csv_path = tmp_path / "recruiter.csv"
    csv_path.write_text(
        "name,email,phone,current_company,title\n"
        "Bad Row,bad@example.com,123,Company,Title,extra\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No well-formed"):
        RecruiterCSVParser().parse(csv_path)

