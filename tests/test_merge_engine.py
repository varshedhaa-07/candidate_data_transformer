"""Tests for candidate merge behavior."""

from merger import ConflictResolver, ConflictValue, MergeEngine
from models import Candidate, Education, Experience, ProvenanceRecord, Skill


def test_merge_engine_unions_and_normalizes_fields() -> None:
    csv_candidate = Candidate(
        candidate_id="recruiter_csv:file:2",
        full_name="Jane Doe",
        emails=["jane@example.com"],
        phones=["+919876543210"],
        headline="CSV Headline",
        skills=[Skill("CPP")],
        experience=[
            Experience(company="Acme", title="Engineer", is_current=True, skills=["Python"])
        ],
        education=[Education(institution="ABC University", degree="B.Tech")],
        provenance=[
            ProvenanceRecord("recruiter_csv", "full_name", "name", "Jane Doe"),
            ProvenanceRecord("recruiter_csv", "headline", "title", "CSV Headline"),
            ProvenanceRecord(
                "recruiter_csv",
                "experience.company",
                "current_company",
                "Acme",
                0.95,
            ),
        ],
    )
    resume_candidate = Candidate(
        candidate_id="resume_pdf:resume",
        full_name="J. Doe",
        emails=["jane@example.com", "jane@work.com"],
        phones=["+919999999999"],
        headline="Resume Headline",
        skills=[Skill("C Plus Plus"), Skill("ReactJS")],
        experience=[Experience(company="Acme", title="Engineer", description="Built APIs")],
        education=[Education(institution="ABC University", degree="B.Tech", end_date="2022")],
        provenance=[
            ProvenanceRecord("resume_pdf", "full_name", "resume_text", "J. Doe"),
            ProvenanceRecord("resume_pdf", "headline", "resume_text", "Resume Headline"),
            ProvenanceRecord("resume_pdf", "experience.company", "resume_text", "Acme", 0.80),
        ],
    )

    merged = MergeEngine().merge([resume_candidate, csv_candidate])

    assert merged.full_name == "Jane Doe"
    assert merged.headline == "CSV Headline"
    assert merged.emails == ["jane@example.com", "jane@work.com"]
    assert merged.phones == ["+919999999999", "+919876543210"]
    assert [skill.name for skill in merged.skills] == ["C++", "React"]
    assert len(merged.experience) == 1
    assert merged.experience[0].description == "Built APIs"
    assert len(merged.education) == 1
    assert any(record.source == "merge_engine" for record in merged.provenance)


def test_merge_engine_rejects_empty_input() -> None:
    try:
        MergeEngine().merge([])
    except ValueError as exc:
        assert "At least one candidate" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_conflict_resolver_uses_priority_and_same_priority_agreement() -> None:
    resolver = ConflictResolver()

    priority_result = resolver.resolve(
        [ConflictValue("Resume Name", "Resume"), ConflictValue("CSV Name", "CSV")]
    )
    agreement_result = resolver.resolve(
        [
            ConflictValue("Jane Doe", "GitHub"),
            ConflictValue("Jane Doe", "github"),
            ConflictValue("Jane A Doe", "GitHub"),
        ]
    )

    assert priority_result.selected_value == "CSV Name"
    assert agreement_result.selected_value == "Jane Doe"


def test_conflict_resolver_handles_empty_and_same_priority_disagreement() -> None:
    resolver = ConflictResolver()

    empty_result = resolver.resolve([ConflictValue("", "CSV"), ConflictValue(None, "Resume")])
    tie_result = resolver.resolve(
        [ConflictValue("Jane", "GitHub"), ConflictValue("Janet", "github")]
    )

    assert empty_result.selected_value is None
    assert "No non-empty" in empty_result.explanation
    assert tie_result.selected_value == "Jane"
    assert "priority tie" in tie_result.explanation


def test_merge_engine_handles_single_sparse_candidate() -> None:
    candidate = Candidate(candidate_id="resume_pdf:resume", provenance=[])

    merged = MergeEngine().merge([candidate])

    assert merged.candidate_id == "merged:resume_pdf:resume"
    assert merged.emails == []
    assert merged.phones == []
    assert merged.skills == []
    assert merged.overall_confidence is None
