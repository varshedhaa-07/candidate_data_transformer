"""Tests for candidate validation."""

from models import Candidate, Education, Experience
from validation import Validator


def test_validator_returns_clean_report_for_valid_candidate() -> None:
    candidate = Candidate(
        candidate_id="c1",
        full_name="Jane Doe",
        emails=["jane@example.com"],
        phones=["+919876543210"],
        experience=[Experience(start_date="Jan 2022", end_date="2023")],
        education=[Education(start_date="2020", end_date="01/2022")],
    )

    report = Validator().validate(candidate)

    assert report.is_valid is True
    assert report.errors == []
    assert report.warnings == []


def test_validator_reports_errors_and_warnings_without_stopping() -> None:
    candidate = Candidate(
        candidate_id="",
        full_name=None,
        emails=["bad-email", "dup@example.com", "DUP@example.com"],
        phones=["+15551234567", "abc"],
        experience=[Experience(start_date="13/2022")],
        education=[Education(end_date="not a date")],
    )

    report = Validator().validate(candidate)

    assert report.is_valid is False
    assert len(report.warnings) == 1
    messages = [issue.message for issue in report.errors]
    assert "Required field is missing." in messages
    assert "Email format is invalid." in messages
    assert "Phone country code is not supported." in messages
    assert "Phone number is invalid." in messages
    assert "Date value is invalid." in messages
    assert "warnings" in report.to_dict()
    assert "errors" in report.to_json()


def test_validator_reports_non_string_phone() -> None:
    candidate = Candidate(
        candidate_id="c1",
        full_name="Jane Doe",
        phones=[1234567890],  # type: ignore[list-item]
    )

    report = Validator().validate(candidate)

    assert report.errors[0].message == "Phone value must be a string."
