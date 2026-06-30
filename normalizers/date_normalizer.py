"""Date normalization utilities."""

from __future__ import annotations

import re


class DateNormalizer:
    """Normalizes partial dates into YYYY-MM or YYYY format."""

    MONTHS = {
        "jan": "01",
        "january": "01",
        "feb": "02",
        "february": "02",
        "mar": "03",
        "march": "03",
        "apr": "04",
        "april": "04",
        "may": "05",
        "jun": "06",
        "june": "06",
        "jul": "07",
        "july": "07",
        "aug": "08",
        "august": "08",
        "sep": "09",
        "sept": "09",
        "september": "09",
        "oct": "10",
        "october": "10",
        "nov": "11",
        "november": "11",
        "dec": "12",
        "december": "12",
    }

    MONTH_NAME_YEAR_PATTERN = re.compile(r"^([A-Za-z]+)\s+(\d{4})$")
    YEAR_PATTERN = re.compile(r"^\d{4}$")
    NUMERIC_MONTH_YEAR_PATTERN = re.compile(r"^(\d{1,2})/(\d{4})$")

    def normalize(self, value: str | None) -> str | None:
        """Normalize a date value, or return None if invalid."""
        if value is None:
            return None

        cleaned = value.strip()
        if not cleaned:
            return None

        if self.YEAR_PATTERN.match(cleaned):
            return cleaned

        month_name_match = self.MONTH_NAME_YEAR_PATTERN.match(cleaned)
        if month_name_match:
            return self._normalize_month_name_year(month_name_match)

        numeric_month_match = self.NUMERIC_MONTH_YEAR_PATTERN.match(cleaned)
        if numeric_month_match:
            return self._normalize_numeric_month_year(numeric_month_match)

        return None

    def _normalize_month_name_year(self, match: re.Match[str]) -> str | None:
        month_name, year = match.groups()
        month = self.MONTHS.get(month_name.casefold())
        if month is None:
            return year
        return f"{year}-{month}"

    def _normalize_numeric_month_year(self, match: re.Match[str]) -> str | None:
        month_value, year = match.groups()
        month_number = int(month_value)
        if not 1 <= month_number <= 12:
            return None
        return f"{year}-{month_number:02d}"

