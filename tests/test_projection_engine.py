"""Tests for projection engine."""

import json

import pytest

from models import Candidate, Experience, ProvenanceRecord, Skill
from projection import ProjectionEngine


def test_projection_selects_renames_maps_and_normalizes_without_mutation() -> None:
    candidate = Candidate(
        candidate_id="c1",
        full_name="Jane Doe",
        phones=["98765 43210"],
        skills=[Skill("CPP"), Skill("ReactJS")],
        experience=[Experience(start_date="Jan 2022", end_date="2023")],
        overall_confidence=0.91,
        provenance=[ProvenanceRecord("csv", "full_name", "name", "Jane Doe")],
    )

    projected = json.loads(
        ProjectionEngine().project(
            candidate,
            {
                "fields": ["candidate_id", "full_name", "phones", "skills", "experience"],
                "rename": {"full_name": "name"},
                "mapping": {"primary_phone": "phones"},
                "normalization": True,
                "include_confidence": True,
                "include_provenance": True,
                "missing_value_policy": "null",
            },
        )
    )

    assert projected["name"] == "Jane Doe"
    assert projected["phones"] == ["+919876543210"]
    assert projected["skills"] == [{"name": "C++"}, {"name": "React"}]
    assert projected["experience"][0]["start_date"] == "2022-01"
    assert projected["overall_confidence"] == 0.91
    assert projected["provenance"][0]["source"] == "csv"
    assert candidate.phones == ["98765 43210"]
    assert candidate.skills[0].name == "CPP"


def test_projection_omit_missing_values() -> None:
    candidate = Candidate(candidate_id="c1")

    projected = json.loads(
        ProjectionEngine().project(
            candidate,
            {"fields": ["candidate_id", "headline"], "missing_value_policy": "omit"},
        )
    )

    assert projected == {"candidate_id": "c1"}


def test_projection_error_policy_raises_for_missing_values() -> None:
    with pytest.raises(ValueError, match="missing"):
        ProjectionEngine().project(
            Candidate(candidate_id="c1"),
            {"fields": ["headline"], "missing_value_policy": "error"},
        )


def test_projection_rejects_malformed_config() -> None:
    with pytest.raises(ValueError, match="fields"):
        ProjectionEngine().project(Candidate(candidate_id="c1"), {"fields": "full_name"})


def test_projection_supports_json_config_and_null_missing_policy() -> None:
    projected = json.loads(
        ProjectionEngine().project(
            Candidate(candidate_id="c1"),
            '{"fields": ["candidate_id", "headline"], "missing_value_policy": "null"}',
        )
    )

    assert projected == {"candidate_id": "c1", "headline": None}


def test_projection_rejects_malformed_mapping_and_policy() -> None:
    engine = ProjectionEngine()

    with pytest.raises(ValueError, match="mapping"):
        engine.project(Candidate(candidate_id="c1"), {"mapping": []})

    with pytest.raises(ValueError, match="missing_value_policy"):
        engine.project(Candidate(candidate_id="c1"), {"missing_value_policy": "explode"})
