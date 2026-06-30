"""Candidate projection engine."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from models import Candidate
from normalizers import DateNormalizer, PhoneNormalizer, SkillNormalizer


class ProjectionEngine:
    """Projects canonical candidates into configurable JSON payloads."""

    MISSING_VALUE_POLICIES = {"null", "omit", "error"}
    DEFAULT_FIELDS = (
        "candidate_id",
        "full_name",
        "emails",
        "phones",
        "location",
        "links",
        "headline",
        "years_experience",
        "skills",
        "experience",
        "education",
    )

    DEFAULT_NORMALIZED_FIELDS = (
        "phones",
        "skills",
        "experience.start_date",
        "experience.end_date",
        "education.start_date",
        "education.end_date",
    )

    def __init__(
        self,
        phone_normalizer: PhoneNormalizer | None = None,
        skill_normalizer: SkillNormalizer | None = None,
        date_normalizer: DateNormalizer | None = None,
    ) -> None:
        self._phone_normalizer = phone_normalizer or PhoneNormalizer()
        self._skill_normalizer = skill_normalizer or SkillNormalizer()
        self._date_normalizer = date_normalizer or DateNormalizer()

    def project(
        self,
        candidate: Candidate,
        configuration: str | dict[str, Any],
        *,
        indent: int | None = None,
    ) -> str:
        """Project a candidate into JSON without modifying the candidate object.

        Supported configuration keys:
            fields: list of canonical field names to include.
            rename: mapping of canonical field name to output field name.
            mapping: mapping of output field name to canonical field name.
            normalization: bool, list of fields, or mapping of field to enabled bool.
            include_confidence: include overall_confidence when true.
            include_provenance: include provenance when true.
            missing_value_policy: one of null, omit, or error.
        """
        config = self._load_configuration(configuration)
        policy = self._missing_value_policy(config)
        candidate_data = deepcopy(candidate.to_dict())

        if self._should_normalize(config):
            self._normalize(candidate_data, self._normalized_fields(config))

        projected = self._build_projection(candidate_data, config, policy)
        return json.dumps(projected, indent=indent)

    def _load_configuration(self, configuration: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(configuration, str):
            loaded = json.loads(configuration)
        else:
            loaded = deepcopy(configuration)

        if not isinstance(loaded, dict):
            raise ValueError("Projection configuration must be a JSON object.")

        return loaded

    def _missing_value_policy(self, config: dict[str, Any]) -> str:
        policy = config.get("missing_value_policy", "null")
        if policy not in self.MISSING_VALUE_POLICIES:
            raise ValueError(
                "missing_value_policy must be one of: "
                + ", ".join(sorted(self.MISSING_VALUE_POLICIES))
            )
        return policy

    def _build_projection(
        self,
        candidate_data: dict[str, Any],
        config: dict[str, Any],
        missing_value_policy: str,
    ) -> dict[str, Any]:
        projected: dict[str, Any] = {}
        rename = self._field_mapping(config, "rename")
        mapping = self._field_mapping(config, "mapping")

        fields = self._selected_fields(config)
        for field_name in fields:
            output_name = rename.get(field_name, field_name)
            self._add_projected_value(
                projected,
                output_name,
                self._get_path(candidate_data, field_name),
                missing_value_policy,
            )

        for output_name, source_field in mapping.items():
            self._add_projected_value(
                projected,
                output_name,
                self._get_path(candidate_data, source_field),
                missing_value_policy,
            )

        if config.get("include_confidence", False):
            self._add_projected_value(
                projected,
                "overall_confidence",
                self._get_path(candidate_data, "overall_confidence"),
                missing_value_policy,
            )

        if config.get("include_provenance", False):
            self._add_projected_value(
                projected,
                "provenance",
                self._get_path(candidate_data, "provenance"),
                missing_value_policy,
            )

        return projected

    def _selected_fields(self, config: dict[str, Any]) -> list[str]:
        fields = config.get("fields", self.DEFAULT_FIELDS)
        if not isinstance(fields, (list, tuple)):
            raise ValueError("fields must be a list of canonical field names.")
        if not all(isinstance(field, str) for field in fields):
            raise ValueError("fields must contain only strings.")
        return [field for field in fields if field not in {"overall_confidence", "provenance"}]

    def _field_mapping(self, config: dict[str, Any], key: str) -> dict[str, str]:
        mapping = config.get(key, {})
        if not isinstance(mapping, dict):
            raise ValueError(f"{key} must be an object.")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
            raise ValueError(f"{key} must map strings to strings.")
        return mapping

    def _add_projected_value(
        self,
        projected: dict[str, Any],
        output_name: str,
        value: Any,
        missing_value_policy: str,
    ) -> None:
        if self._is_missing(value):
            if missing_value_policy == "error":
                raise ValueError(f"Projection field is missing: {output_name}")
            if missing_value_policy == "omit":
                return
            projected[output_name] = None
            return

        projected[output_name] = value

    def _is_missing(self, value: Any) -> bool:
        return value is _MissingValue or value is None

    def _get_path(self, data: dict[str, Any], path: str) -> Any:
        current: Any = data
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return _MissingValue
            current = current[part]
        return current

    def _should_normalize(self, config: dict[str, Any]) -> bool:
        return bool(config.get("normalization", False))

    def _normalized_fields(self, config: dict[str, Any]) -> tuple[str, ...]:
        normalization = config.get("normalization", False)
        if normalization is True:
            return self.DEFAULT_NORMALIZED_FIELDS
        if isinstance(normalization, list):
            return tuple(normalization)
        if isinstance(normalization, dict):
            return tuple(field for field, enabled in normalization.items() if enabled)
        return ()

    def _normalize(self, data: dict[str, Any], fields: tuple[str, ...]) -> None:
        for field_name in fields:
            if field_name == "phones":
                data["phones"] = self._normalize_phones(data.get("phones", []))
            elif field_name == "skills":
                data["skills"] = self._normalize_skills(data.get("skills", []))
            elif field_name == "experience.start_date":
                self._normalize_record_dates(data.get("experience", []), "start_date")
            elif field_name == "experience.end_date":
                self._normalize_record_dates(data.get("experience", []), "end_date")
            elif field_name == "education.start_date":
                self._normalize_record_dates(data.get("education", []), "start_date")
            elif field_name == "education.end_date":
                self._normalize_record_dates(data.get("education", []), "end_date")

    def _normalize_phones(self, phones: list[str]) -> list[str]:
        normalized: list[str] = []
        for phone in phones:
            normalized_phone = self._phone_normalizer.normalize(phone)
            if normalized_phone is not None:
                normalized.append(normalized_phone)
        return normalized

    def _normalize_skills(self, skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
        skill_names = [
            skill.get("name")
            for skill in skills
            if isinstance(skill, dict) and skill.get("name")
        ]
        canonical_names = self._skill_normalizer.normalize(skill_names)
        return [{"name": name} for name in canonical_names]

    def _normalize_record_dates(self, records: list[dict[str, Any]], field_name: str) -> None:
        for record in records:
            if not isinstance(record, dict):
                continue
            value = record.get(field_name)
            if value is None:
                continue
            record[field_name] = self._date_normalizer.normalize(value)


class _MissingValue:
    """Sentinel for values missing from projection input."""
