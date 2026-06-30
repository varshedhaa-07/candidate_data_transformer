"""Confidence scoring engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    """Confidence score with calculation details."""

    score: float
    source_reliability: float
    agreement: float
    validation: float
    explanation: str


class ConfidenceEngine:
    """Calculates confidence using source reliability, agreement, and validation."""

    SOURCE_RELIABILITY = {
        "csv": 0.95,
        "resume": 0.80,
        "github": 0.90,
        "recruiter notes": 0.60,
    }

    SOURCE_ALIASES = {
        "recruiter_csv": "csv",
        "resume_pdf": "resume",
        "recruiter_notes": "recruiter notes",
    }

    SOURCE_WEIGHT = 0.4
    AGREEMENT_WEIGHT = 0.4
    VALIDATION_WEIGHT = 0.2

    def calculate(
        self,
        *,
        source: str,
        agreement: float,
        validation_success: bool,
    ) -> ConfidenceResult:
        """Calculate confidence between 0 and 1.

        Formula:
            confidence =
                0.4 * source reliability +
                0.4 * agreement +
                0.2 * validation

        Validation is represented as 1.0 when successful and 0.0 when failed.
        Agreement should be passed as a value between 0 and 1.
        """
        source_reliability = self.source_reliability(source)
        return self.calculate_from_components(
            source_reliability=source_reliability,
            agreement=agreement,
            validation_success=validation_success,
        )

    def calculate_from_components(
        self,
        *,
        source_reliability: float,
        agreement: float,
        validation_success: bool,
    ) -> ConfidenceResult:
        """Calculate confidence from already resolved component scores.

        Formula:
            confidence =
                0.4 * source reliability +
                0.4 * agreement +
                0.2 * validation

        This is useful when a merged candidate combines multiple sources and the
        caller has already calculated aggregate source reliability.
        """
        source_reliability = self._clamp(source_reliability)
        agreement_score = self._clamp(agreement)
        validation_score = 1.0 if validation_success else 0.0

        score = (
            self.SOURCE_WEIGHT * source_reliability
            + self.AGREEMENT_WEIGHT * agreement_score
            + self.VALIDATION_WEIGHT * validation_score
        )
        score = self._clamp(score)

        return ConfidenceResult(
            score=score,
            source_reliability=source_reliability,
            agreement=agreement_score,
            validation=validation_score,
            explanation=(
                "confidence = "
                f"0.4 * {source_reliability:.2f} source reliability + "
                f"0.4 * {agreement_score:.2f} agreement + "
                f"0.2 * {validation_score:.2f} validation = "
                f"{score:.2f}"
            ),
        )

    def source_reliability(self, source: str) -> float:
        """Return configured reliability for a source, or 0.0 if unknown."""
        canonical_source = self._canonical_source(source)
        return self.SOURCE_RELIABILITY.get(canonical_source, 0.0)

    def _canonical_source(self, source: str) -> str:
        normalized = " ".join(source.strip().casefold().replace("-", " ").split())
        return self.SOURCE_ALIASES.get(normalized, normalized)

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, value))
