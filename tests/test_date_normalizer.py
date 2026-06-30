"""Tests for date normalization."""

from normalizers import DateNormalizer


def test_normalizes_short_month_name() -> None:
    assert DateNormalizer().normalize("Jan 2022") == "2022-01"


def test_normalizes_full_month_name() -> None:
    assert DateNormalizer().normalize("January 2022") == "2022-01"


def test_normalizes_year_only() -> None:
    assert DateNormalizer().normalize("2022") == "2022"


def test_normalizes_numeric_month_year() -> None:
    assert DateNormalizer().normalize("01/2022") == "2022-01"


def test_unknown_month_returns_year() -> None:
    assert DateNormalizer().normalize("Unknown 2022") == "2022"


def test_invalid_numeric_month_returns_none() -> None:
    assert DateNormalizer().normalize("13/2022") is None


def test_invalid_value_returns_none() -> None:
    assert DateNormalizer().normalize("not a date") is None


def test_empty_value_returns_none() -> None:
    assert DateNormalizer().normalize(" ") is None


def test_none_returns_none() -> None:
    assert DateNormalizer().normalize(None) is None

