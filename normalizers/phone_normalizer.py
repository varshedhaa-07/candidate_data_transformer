"""Phone number normalization utilities."""

from __future__ import annotations

import re


class PhoneNormalizer:
    """Normalizes supported phone numbers into E.164 format."""

    INDIA_COUNTRY_CODE = "91"
    INDIA_NATIONAL_NUMBER_LENGTH = 10
    INDIA_MOBILE_START_DIGITS = {"6", "7", "8", "9"}

    def normalize(self, phone_number: str | None) -> str | None:
        """Normalize a phone number to E.164, or return None if invalid."""
        if phone_number is None:
            return None

        cleaned = self._clean(phone_number)
        if not cleaned:
            return None

        return self._normalize_indian_number(cleaned)

    def _clean(self, phone_number: str) -> str:
        cleaned = phone_number.strip()
        cleaned = re.sub(r"[\s().-]", "", cleaned)
        return cleaned

    def _normalize_indian_number(self, phone_number: str) -> str | None:
        if phone_number.startswith("+"):
            digits = phone_number[1:]
        else:
            digits = phone_number

        if not digits.isdigit():
            return None

        national_number = self._extract_indian_national_number(digits)
        if national_number is None:
            return None

        return f"+{self.INDIA_COUNTRY_CODE}{national_number}"

    def _extract_indian_national_number(self, digits: str) -> str | None:
        if self._is_valid_indian_national_number(digits):
            return digits

        if digits.startswith(self.INDIA_COUNTRY_CODE):
            national_number = digits[len(self.INDIA_COUNTRY_CODE) :]
            if self._is_valid_indian_national_number(national_number):
                return national_number

        if digits.startswith(f"0{self.INDIA_COUNTRY_CODE}"):
            national_number = digits[len(f"0{self.INDIA_COUNTRY_CODE}") :]
            if self._is_valid_indian_national_number(national_number):
                return national_number

        if digits.startswith("0"):
            national_number = digits[1:]
            if self._is_valid_indian_national_number(national_number):
                return national_number

        return None

    def _is_valid_indian_national_number(self, digits: str) -> bool:
        return (
            len(digits) == self.INDIA_NATIONAL_NUMBER_LENGTH
            and digits[0] in self.INDIA_MOBILE_START_DIGITS
            and digits.isdigit()
        )

