"""Tests for phone normalization."""

import pytest

from normalizers import PhoneNormalizer


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("98765 43210", "+919876543210"),
        ("+91-98765-43210", "+919876543210"),
        ("(09876543210)", "+919876543210"),
        ("0919876543210", "+919876543210"),
    ],
)
def test_phone_normalizer_converts_indian_numbers(input_value, expected) -> None:
    assert PhoneNormalizer().normalize(input_value) == expected


@pytest.mark.parametrize("input_value", ["12345", "+1 555 123 4567", "abcdef", None, ""])
def test_phone_normalizer_returns_none_for_invalid_values(input_value) -> None:
    assert PhoneNormalizer().normalize(input_value) is None

