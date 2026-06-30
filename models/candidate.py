"""Canonical candidate profile data model."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Skill:
    """Canonical representation of a candidate skill."""

    name: str
    category: str | None = None
    years_experience: float | None = None
    confidence: float | None = None


@dataclass(slots=True)
class Experience:
    """Canonical representation of a work experience entry."""

    title: str | None = None
    company: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool | None = None
    description: str | None = None
    skills: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Education:
    """Canonical representation of an education entry."""

    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


@dataclass(slots=True)
class ProvenanceRecord:
    """Tracks where a candidate field or value originated."""

    source: str
    field_name: str
    source_field: str | None = None
    value: Any | None = None
    confidence: float | None = None


@dataclass(slots=True)
class Candidate:
    """Canonical candidate profile used across the transformation pipeline."""

    candidate_id: str
    full_name: str | None = None
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    location: str | None = None
    links: list[str] = field(default_factory=list)
    headline: str | None = None
    years_experience: float | None = None
    skills: list[Skill] = field(default_factory=list)
    experience: list[Experience] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)
    provenance: list[ProvenanceRecord] = field(default_factory=list)
    overall_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the candidate model into a JSON-serializable dictionary."""
        return asdict(self)

    def to_json(self, *, indent: int | None = None) -> str:
        """Serialize the candidate model into a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

