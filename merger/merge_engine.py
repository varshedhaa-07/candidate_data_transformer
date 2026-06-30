"""Candidate merge engine."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from models import Candidate, Education, Experience, ProvenanceRecord, Skill
from normalizers import SkillNormalizer


class MergeEngine:
    """Merges multiple candidate profiles into one canonical profile."""

    SOURCE_NAME = "merge_engine"
    STRUCTURED_SOURCE_PRIORITY = {
        "recruiter_csv": 100,
        "resume_pdf": 50,
    }

    def __init__(self, skill_normalizer: SkillNormalizer | None = None) -> None:
        self._skill_normalizer = skill_normalizer or SkillNormalizer()

    def merge(self, candidates: list[Candidate] | tuple[Candidate, ...]) -> Candidate:
        """Merge candidate profiles according to configured field policies."""
        if not candidates:
            raise ValueError("At least one candidate is required for merge.")

        candidate_list = list(candidates)
        merged = Candidate(candidate_id=self._merged_candidate_id(candidate_list))

        merged.full_name = self._select_name(candidate_list)
        merged.emails = self._merge_unique_values(candidate_list, "emails")
        merged.phones = self._merge_unique_values(candidate_list, "phones")
        merged.links = self._merge_unique_values(candidate_list, "links")
        merged.location = self._select_by_source_priority(candidate_list, "location")
        merged.headline = self._select_by_source_priority(candidate_list, "headline")
        merged.years_experience = self._select_highest_confidence_value(
            candidate_list,
            "years_experience",
        )
        merged.skills = self._merge_skills(candidate_list)
        merged.experience = self._merge_experience(candidate_list)
        merged.education = self._merge_education(candidate_list)
        merged.overall_confidence = self._select_overall_confidence(candidate_list)

        merged.provenance = self._merge_provenance(candidate_list)
        merged.provenance.extend(self._build_merge_provenance(candidate_list, merged))
        return merged

    def _merged_candidate_id(self, candidates: list[Candidate]) -> str:
        return "merged:" + "|".join(candidate.candidate_id for candidate in candidates)

    def _select_name(self, candidates: list[Candidate]) -> str | None:
        return self._select_scalar_candidate(candidates, "full_name")

    def _select_by_source_priority(
        self,
        candidates: list[Candidate],
        field_name: str,
    ) -> Any | None:
        return self._select_scalar_candidate(candidates, field_name)

    def _select_highest_confidence_value(
        self,
        candidates: list[Candidate],
        field_name: str,
    ) -> Any | None:
        options = [
            candidate
            for candidate in candidates
            if self._has_value(getattr(candidate, field_name))
        ]
        if not options:
            return None

        selected = max(
            options,
            key=lambda candidate: (
                self._field_confidence(candidate, field_name, getattr(candidate, field_name)),
                self._source_priority(candidate),
            ),
        )
        return getattr(selected, field_name)

    def _select_overall_confidence(self, candidates: list[Candidate]) -> float | None:
        confidences = [
            candidate.overall_confidence
            for candidate in candidates
            if candidate.overall_confidence is not None
        ]
        if not confidences:
            return None
        return max(confidences)

    def _select_scalar_candidate(
        self,
        candidates: list[Candidate],
        field_name: str,
    ) -> Any | None:
        options = [
            candidate
            for candidate in candidates
            if self._has_value(getattr(candidate, field_name))
        ]
        if not options:
            return None

        selected = max(options, key=self._source_priority)
        return getattr(selected, field_name)

    def _merge_unique_values(
        self,
        candidates: list[Candidate],
        field_name: str,
    ) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()

        for candidate in candidates:
            for value in getattr(candidate, field_name):
                if not value or value in seen:
                    continue
                seen.add(value)
                values.append(value)

        return values

    def _merge_skills(self, candidates: list[Candidate]) -> list[Skill]:
        skill_names = [
            skill.name
            for candidate in candidates
            for skill in candidate.skills
            if skill.name
        ]
        return [Skill(name=name) for name in self._skill_normalizer.normalize(skill_names)]

    def _merge_experience(self, candidates: list[Candidate]) -> list[Experience]:
        selected_current_company = self._select_current_company(candidates)
        experiences = self._merge_duplicate_models(
            [experience for candidate in candidates for experience in candidate.experience],
            self._experience_key,
            self._merge_experience_entry,
        )

        if selected_current_company is None:
            return experiences

        return sorted(
            experiences,
            key=lambda experience: experience.company != selected_current_company,
        )

    def _select_current_company(self, candidates: list[Candidate]) -> str | None:
        options: list[tuple[Candidate, Experience]] = []
        for candidate in candidates:
            current_experience = self._current_experience(candidate)
            if current_experience and current_experience.company:
                options.append((candidate, current_experience))

        if not options:
            return None

        _, selected_experience = max(
            options,
            key=lambda option: (
                self._field_confidence(
                    option[0],
                    "experience.company",
                    option[1].company,
                ),
                self._source_priority(option[0]),
            ),
        )
        return selected_experience.company

    def _current_experience(self, candidate: Candidate) -> Experience | None:
        for experience in candidate.experience:
            if experience.is_current and experience.company:
                return experience

        for experience in candidate.experience:
            if experience.company:
                return experience

        return None

    def _merge_education(self, candidates: list[Candidate]) -> list[Education]:
        return self._merge_duplicate_models(
            [education for candidate in candidates for education in candidate.education],
            self._education_key,
            self._merge_education_entry,
        )

    def _merge_duplicate_models(
        self,
        items: list[Any],
        key_factory: Callable[[Any], tuple[str, ...]],
        merge_entry: Callable[[Any, Any], Any],
    ) -> list[Any]:
        merged_by_key: dict[tuple[str, ...], Any] = {}

        for item in items:
            item_key = key_factory(item)
            if item_key in merged_by_key:
                merged_by_key[item_key] = merge_entry(merged_by_key[item_key], item)
            else:
                merged_by_key[item_key] = replace(item)

        return list(merged_by_key.values())

    def _merge_experience_entry(self, existing: Experience, incoming: Experience) -> Experience:
        return Experience(
            title=existing.title or incoming.title,
            company=existing.company or incoming.company,
            location=existing.location or incoming.location,
            start_date=existing.start_date or incoming.start_date,
            end_date=existing.end_date or incoming.end_date,
            is_current=(
                existing.is_current if existing.is_current is not None else incoming.is_current
            ),
            description=existing.description or incoming.description,
            skills=self._merge_string_lists(existing.skills, incoming.skills),
        )

    def _merge_education_entry(self, existing: Education, incoming: Education) -> Education:
        return Education(
            institution=existing.institution or incoming.institution,
            degree=existing.degree or incoming.degree,
            field_of_study=existing.field_of_study or incoming.field_of_study,
            start_date=existing.start_date or incoming.start_date,
            end_date=existing.end_date or incoming.end_date,
            description=existing.description or incoming.description,
        )

    def _merge_string_lists(self, first: list[str], second: list[str]) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for value in [*first, *second]:
            if value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values

    def _experience_key(self, experience: Experience) -> tuple[str, ...]:
        primary_key = (
            self._normalize_key(experience.company),
            self._normalize_key(experience.title),
            self._normalize_key(experience.start_date),
            self._normalize_key(experience.end_date),
        )
        if any(primary_key):
            return primary_key
        return (self._normalize_key(experience.description),)

    def _education_key(self, education: Education) -> tuple[str, ...]:
        identity_key = (
            self._normalize_key(education.institution),
            self._normalize_key(education.degree),
            self._normalize_key(education.field_of_study),
        )
        if any(identity_key):
            return identity_key

        date_key = (
            self._normalize_key(education.start_date),
            self._normalize_key(education.end_date),
        )
        if any(date_key):
            return date_key

        return (self._normalize_key(education.description),)

    def _merge_provenance(self, candidates: list[Candidate]) -> list[ProvenanceRecord]:
        return [
            replace(record)
            for candidate in candidates
            for record in candidate.provenance
        ]

    def _build_merge_provenance(
        self,
        candidates: list[Candidate],
        merged: Candidate,
    ) -> list[ProvenanceRecord]:
        records: list[ProvenanceRecord] = []

        self._append_selected_record(
            records,
            candidates,
            "full_name",
            merged.full_name,
            "selected_name_prefer_structured_source",
        )
        self._append_union_records(records, "emails", merged.emails)
        self._append_union_records(records, "phones", merged.phones)
        self._append_union_records(records, "links", merged.links)
        self._append_selected_record(
            records,
            candidates,
            "location",
            merged.location,
            "selected_location_highest_priority_source",
        )
        self._append_selected_record(
            records,
            candidates,
            "headline",
            merged.headline,
            "selected_headline_highest_priority_source",
        )
        self._append_selected_record(
            records,
            candidates,
            "years_experience",
            merged.years_experience,
            "selected_years_experience_highest_confidence_source",
        )
        self._append_union_records(records, "skills", [skill.name for skill in merged.skills])
        self._append_model_records(records, "experience", merged.experience)
        self._append_model_records(records, "education", merged.education)

        current_company = self._select_current_company(candidates)
        if current_company:
            records.append(
                self._merge_record(
                    "experience.company",
                    "selected_current_company_highest_confidence_source",
                    current_company,
                )
            )

        return records

    def _append_selected_record(
        self,
        records: list[ProvenanceRecord],
        candidates: list[Candidate],
        field_name: str,
        value: Any,
        reason: str,
    ) -> None:
        if not self._has_value(value):
            return

        records.append(
            self._merge_record(
                field_name,
                f"{reason}:{self._source_for_value(candidates, field_name, value)}",
                value,
            )
        )

    def _append_union_records(
        self,
        records: list[ProvenanceRecord],
        field_name: str,
        values: list[str],
    ) -> None:
        for value in values:
            records.append(self._merge_record(field_name, "union_preserved_value", value))

    def _append_model_records(
        self,
        records: list[ProvenanceRecord],
        field_name: str,
        values: list[Experience] | list[Education],
    ) -> None:
        for value in values:
            records.append(self._merge_record(field_name, "merged_duplicate_records", value))

    def _merge_record(
        self,
        field_name: str,
        reason: str,
        value: Any,
    ) -> ProvenanceRecord:
        return ProvenanceRecord(
            source=self.SOURCE_NAME,
            field_name=field_name,
            source_field=reason,
            value=value,
        )

    def _source_for_value(
        self,
        candidates: list[Candidate],
        field_name: str,
        value: Any,
    ) -> str:
        for candidate in candidates:
            if getattr(candidate, field_name) == value:
                return self._candidate_source(candidate)
        return "unknown_source"

    def _field_confidence(self, candidate: Candidate, field_name: str, value: Any) -> float:
        for record in candidate.provenance:
            if (
                record.field_name == field_name
                and record.value == value
                and record.confidence is not None
            ):
                return record.confidence
        return candidate.overall_confidence or 0.0

    def _source_priority(self, candidate: Candidate) -> int:
        return self.STRUCTURED_SOURCE_PRIORITY.get(self._candidate_source(candidate), 0)

    def _candidate_source(self, candidate: Candidate) -> str:
        if candidate.provenance:
            return candidate.provenance[0].source
        return candidate.candidate_id.split(":", maxsplit=1)[0]

    def _has_value(self, value: Any) -> bool:
        return value is not None and value != "" and value != []

    def _normalize_key(self, value: str | None) -> str:
        if value is None:
            return ""
        return " ".join(value.casefold().split())
