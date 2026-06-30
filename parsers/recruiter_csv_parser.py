"""Recruiter CSV parser implementation."""

from __future__ import annotations

import csv
from pathlib import Path

from models import Candidate, Experience, ProvenanceRecord
from parsers.source_parser import SourceParser


class RecruiterCSVParser(SourceParser):
    """Parses recruiter-supplied CSV files into canonical candidates."""

    REQUIRED_FIELDS = {
        "name",
        "email",
        "phone",
        "current_company",
        "title",
    }

    SOURCE_NAME = "recruiter_csv"

    def parse(self, file_path: str | Path) -> Candidate:
        """Parse the first well-formed CSV row into a candidate profile."""
        path = Path(file_path)

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(
                    csv_file,
                    restkey="_extra_columns",
                    restval=None,
                )
                self._validate_headers(reader.fieldnames)

                for row_number, row in enumerate(reader, start=2):
                    if self._is_malformed(row):
                        continue

                    return self._candidate_from_row(row, path, row_number)
        except csv.Error as exc:
            raise ValueError(f"Unable to read recruiter CSV: {path}") from exc

        raise ValueError(f"No well-formed candidate rows found in recruiter CSV: {path}")

    def _validate_headers(self, fieldnames: list[str] | None) -> None:
        if fieldnames is None:
            raise ValueError("Recruiter CSV is missing a header row.")

        missing_fields = self.REQUIRED_FIELDS.difference(fieldnames)
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(f"Recruiter CSV is missing required fields: {missing}")

    def _is_malformed(self, row: dict[str, str | list[str] | None]) -> bool:
        has_extra_columns = bool(row.get("_extra_columns"))
        has_missing_required_values = any(row[field] is None for field in self.REQUIRED_FIELDS)
        return has_extra_columns or has_missing_required_values

    def _candidate_from_row(
        self,
        row: dict[str, str | list[str] | None],
        path: Path,
        row_number: int,
    ) -> Candidate:
        name = self._require_text(row, "name")
        email = self._require_text(row, "email")
        phone = self._require_text(row, "phone")
        current_company = self._require_text(row, "current_company")
        title = self._require_text(row, "title")

        return Candidate(
            candidate_id=f"{self.SOURCE_NAME}:{path.name}:{row_number}",
            full_name=name,
            emails=[email],
            phones=[phone],
            experience=[
                Experience(
                    title=title,
                    company=current_company,
                )
            ],
            provenance=[
                self._provenance("full_name", "name", name),
                self._provenance("emails", "email", email),
                self._provenance("phones", "phone", phone),
                self._provenance("experience.company", "current_company", current_company),
                self._provenance("experience.title", "title", title),
            ],
        )

    def _require_text(self, row: dict[str, str | list[str] | None], field_name: str) -> str:
        value = row[field_name]
        if not isinstance(value, str):
            raise ValueError(f"Recruiter CSV field is malformed: {field_name}")
        return value

    def _provenance(
        self,
        field_name: str,
        source_field: str,
        value: str,
    ) -> ProvenanceRecord:
        return ProvenanceRecord(
            source=self.SOURCE_NAME,
            field_name=field_name,
            source_field=source_field,
            value=value,
        )

