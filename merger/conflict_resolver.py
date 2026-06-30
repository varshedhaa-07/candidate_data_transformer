"""Conflict resolution policies for candidate merge decisions."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ConflictValue:
    """A candidate value and the source that produced it."""

    value: Any
    source: str


@dataclass(frozen=True, slots=True)
class ConflictResolution:
    """Resolved conflict result with a human-readable explanation."""

    selected_value: Any | None
    explanation: str


class ConflictResolver:
    """Resolves conflicting field values using source priority and agreement."""

    SOURCE_PRIORITY = {
        "csv": 400,
        "github": 300,
        "resume": 200,
        "recruiter notes": 100,
    }

    SOURCE_ALIASES = {
        "recruiter_csv": "csv",
        "resume_pdf": "resume",
        "recruiter_notes": "recruiter notes",
    }

    def resolve(
        self,
        values: list[ConflictValue] | tuple[ConflictValue, ...],
    ) -> ConflictResolution:
        """Select one value from conflicting source values."""
        candidates = [value for value in values if self._has_value(value.value)]
        if not candidates:
            return ConflictResolution(
                selected_value=None,
                explanation="No non-empty values were available to resolve.",
            )

        highest_priority = max(self._priority(item.source) for item in candidates)
        priority_matches = [
            item for item in candidates if self._priority(item.source) == highest_priority
        ]

        if len(priority_matches) == 1:
            selected = priority_matches[0]
            return ConflictResolution(
                selected_value=selected.value,
                explanation=(
                    f"Selected value from higher priority source "
                    f"{self._canonical_source(selected.source)}."
                ),
            )

        selected, count = self._select_most_common(priority_matches)
        selected_key = self._value_key(selected)
        source_names = sorted(
            {
                self._canonical_source(item.source)
                for item in priority_matches
                if self._value_key(item.value) == selected_key
            }
        )
        if count == 1:
            return ConflictResolution(
                selected_value=selected,
                explanation=(
                    "Selected first available value after source priority tie; no value "
                    "appeared in multiple same-priority sources."
                ),
            )

        return ConflictResolution(
            selected_value=selected,
            explanation=(
                "Selected value because it appeared in multiple sources with the same "
                f"priority: {', '.join(source_names)}."
            ),
        )

    def _select_most_common(self, values: list[ConflictValue]) -> tuple[Any, int]:
        counts = Counter(self._value_key(item.value) for item in values)
        most_common_key, count = counts.most_common(1)[0]

        for item in values:
            if self._value_key(item.value) == most_common_key:
                return item.value, count

        return None, 0

    def _priority(self, source: str) -> int:
        return self.SOURCE_PRIORITY.get(self._canonical_source(source), 0)

    def _canonical_source(self, source: str) -> str:
        normalized = " ".join(source.strip().casefold().replace("-", " ").split())
        return self.SOURCE_ALIASES.get(normalized, normalized)

    def _value_key(self, value: Any) -> str:
        return str(value).strip().casefold()

    def _has_value(self, value: Any) -> bool:
        return value is not None and value != "" and value != []
