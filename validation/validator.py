"""Candidate validation report generation."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from models import Candidate, Education, Experience
from normalizers import DateNormalizer, PhoneNormalizer


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Single validation issue."""

    field_name: str
    message: str
    value: Any | None = None


@dataclass(slots=True)
class ValidationReport:
    """Validation result containing non-blocking warnings and errors."""

    warnings: list[ValidationIssue] = field(default_factory=list)
    errors: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return True when no validation errors were found."""
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        """Convert the report into a JSON-serializable dictionary."""
        return asdict(self)

    def to_json(self, *, indent: int | None = None) -> str:
        """Serialize the report into a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class Validator:
    """Validates candidate profile data without stopping execution."""

    EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
    E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")
    SUPPORTED_COUNTRY_CODES = ("91",)
    REQUIRED_FIELDS = ("candidate_id", "full_name")

    def __init__(
        self,
        phone_normalizer: PhoneNormalizer | None = None,
        date_normalizer: DateNormalizer | None = None,
    ) -> None:
        self._phone_normalizer = phone_normalizer or PhoneNormalizer()
        self._date_normalizer = date_normalizer or DateNormalizer()

    def validate(self, candidate: Candidate) -> ValidationReport:
        """Validate a candidate and return a report with warnings and errors."""
        report = ValidationReport()

        self._validate_required_fields(candidate, report)
        self._validate_emails(candidate, report)
        self._validate_phones(candidate, report)
        self._validate_dates(candidate.experience, "experience", report)
        self._validate_dates(candidate.education, "education", report)

        return report

    def _validate_required_fields(
        self,
        candidate: Candidate,
        report: ValidationReport,
    ) -> None:
        for field_name in self.REQUIRED_FIELDS:
            value = getattr(candidate, field_name)
            if not self._has_value(value):
                report.errors.append(
                    ValidationIssue(
                        field_name=field_name,
                        message="Required field is missing.",
                        value=value,
                    )
                )

    def _validate_emails(self, candidate: Candidate, report: ValidationReport) -> None:
        seen: set[str] = set()

        for email in candidate.emails:
            normalized_email = email.strip().casefold() if isinstance(email, str) else ""
            if not normalized_email:
                report.errors.append(
                    ValidationIssue("emails", "Email value is empty.", email)
                )
                continue

            if not self.EMAIL_PATTERN.match(email):
                report.errors.append(
                    ValidationIssue("emails", "Email format is invalid.", email)
                )

            if normalized_email in seen:
                report.warnings.append(
                    ValidationIssue("emails", "Duplicate email found.", email)
                )
            else:
                seen.add(normalized_email)

    def _validate_phones(self, candidate: Candidate, report: ValidationReport) -> None:
        for phone in candidate.phones:
            if not isinstance(phone, str):
                report.errors.append(
                    ValidationIssue("phones", "Phone value must be a string.", phone)
                )
                continue

            if self._has_unsupported_country_code(phone):
                report.errors.append(
                    ValidationIssue(
                        "phones",
                        "Phone country code is not supported.",
                        phone,
                    )
                )
                continue

            normalized_phone = self._phone_normalizer.normalize(phone)
            if normalized_phone is None:
                report.errors.append(
                    ValidationIssue("phones", "Phone number is invalid.", phone)
                )
                continue

            if not self.E164_PATTERN.match(normalized_phone):
                report.errors.append(
                    ValidationIssue("phones", "Phone number is not E.164 compliant.", phone)
                )
                continue

            country_code = self._extract_country_code(normalized_phone)
            if country_code not in self.SUPPORTED_COUNTRY_CODES:
                report.errors.append(
                    ValidationIssue(
                        "phones",
                        "Phone country code is not supported.",
                        phone,
                    )
                )

    def _validate_dates(
        self,
        records: list[Experience] | list[Education],
        field_prefix: str,
        report: ValidationReport,
    ) -> None:
        for index, record in enumerate(records):
            self._validate_date_value(
                getattr(record, "start_date", None),
                f"{field_prefix}[{index}].start_date",
                report,
            )
            self._validate_date_value(
                getattr(record, "end_date", None),
                f"{field_prefix}[{index}].end_date",
                report,
            )

    def _validate_date_value(
        self,
        value: str | None,
        field_name: str,
        report: ValidationReport,
    ) -> None:
        if value is None or value == "":
            return

        if self._date_normalizer.normalize(value) is None:
            report.errors.append(
                ValidationIssue(
                    field_name=field_name,
                    message="Date value is invalid.",
                    value=value,
                )
            )

    def _extract_country_code(self, e164_phone: str) -> str:
        digits = e164_phone.removeprefix("+")
        for country_code in self.SUPPORTED_COUNTRY_CODES:
            if digits.startswith(country_code):
                return country_code
        return ""

    def _has_unsupported_country_code(self, phone: str) -> bool:
        compact_phone = re.sub(r"[\s().-]", "", phone.strip())
        if not self.E164_PATTERN.match(compact_phone):
            return False
        return self._extract_country_code(compact_phone) == ""

    def _has_value(self, value: Any) -> bool:
        return value is not None and value != "" and value != []
