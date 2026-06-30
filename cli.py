"""Command-line entry point for the candidate profile transformation pipeline."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from confidence import ConfidenceEngine, ConfidenceResult
from merger import MergeEngine
from models import Candidate, Skill
from normalizers import DateNormalizer, PhoneNormalizer, SkillNormalizer
from projection import ProjectionEngine
from validation import ValidationReport, Validator


LOGGER = logging.getLogger(__name__)


DEFAULT_PROJECTION_CONFIG = {
    "normalization": False,
    "include_confidence": True,
    "include_provenance": True,
    "missing_value_policy": "null",
}


def main() -> None:
    """Run the candidate profile transformation pipeline."""
    args = _parse_args()
    _configure_logging(args.log_file)

    LOGGER.info("Pipeline started")
    try:
        candidates = _parse_inputs(args)
        _normalize_candidates(candidates)

        merged_candidate = MergeEngine().merge(candidates)
        LOGGER.info("Merge completed for %s candidates", len(candidates))
        _log_merge_decisions(merged_candidate)

        validation_report = Validator().validate(merged_candidate)
        _log_validation(validation_report)

        confidence_result = _calculate_confidence(candidates, validation_report)
        merged_candidate.overall_confidence = confidence_result.score
        LOGGER.info("Confidence calculation: %s", confidence_result.explanation)

        projection_config = _load_projection_config(args.config)
        projected_json = ProjectionEngine().project(
            merged_candidate,
            projection_config,
            indent=2,
        )
        LOGGER.info("Projection completed")

        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_outputs(output_dir, merged_candidate, projected_json, validation_report, confidence_result)

        _print_summary(output_dir, candidates, merged_candidate, validation_report, confidence_result)
        LOGGER.info("Pipeline completed successfully")
    except Exception:
        LOGGER.exception("Pipeline failed")
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform candidate source profiles into projected JSON.",
    )
    parser.add_argument("--csv", help="Path to recruiter CSV input.")
    parser.add_argument("--resume", help="Path to PDF resume input.")
    parser.add_argument("--config", help="Path to projection configuration JSON.")
    parser.add_argument("--output", default="output", help="Output directory.")
    parser.add_argument("--log-file", default="pipeline.log", help="Pipeline log file path.")
    args = parser.parse_args()

    if not args.csv and not args.resume:
        parser.error("At least one input is required: --csv or --resume.")

    return args


def _configure_logging(log_file: str) -> None:
    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def _parse_inputs(args: argparse.Namespace) -> list[Candidate]:
    candidates: list[Candidate] = []

    if args.csv:
        from parsers.recruiter_csv_parser import RecruiterCSVParser

        candidate = RecruiterCSVParser().parse(args.csv)
        candidates.append(candidate)
        LOGGER.info("Source loaded: csv path=%s", args.csv)
        LOGGER.info("Fields extracted from csv: %s", _extracted_fields(candidate))

    if args.resume:
        from parsers.resume_parser import ResumeParser

        candidate = ResumeParser().parse(args.resume)
        candidates.append(candidate)
        LOGGER.info("Source loaded: resume path=%s", args.resume)
        LOGGER.info("Fields extracted from resume: %s", _extracted_fields(candidate))

    return candidates


def _normalize_candidates(candidates: list[Candidate]) -> None:
    phone_normalizer = PhoneNormalizer()
    skill_normalizer = SkillNormalizer()
    date_normalizer = DateNormalizer()

    for candidate in candidates:
        original_phone_count = len(candidate.phones)
        candidate.phones = [
            normalized_phone if (normalized_phone := phone_normalizer.normalize(phone)) else phone
            for phone in candidate.phones
        ]

        candidate.skills = [
            Skill(name=name)
            for name in skill_normalizer.normalize([skill.name for skill in candidate.skills])
        ]

        for experience in candidate.experience:
            experience.start_date = _normalize_date_preserving_invalid(
                date_normalizer,
                experience.start_date,
            )
            experience.end_date = _normalize_date_preserving_invalid(
                date_normalizer,
                experience.end_date,
            )

        for education in candidate.education:
            education.start_date = _normalize_date_preserving_invalid(
                date_normalizer,
                education.start_date,
            )
            education.end_date = _normalize_date_preserving_invalid(
                date_normalizer,
                education.end_date,
            )

        LOGGER.info(
            "Normalization completed for %s: phones %s->%s, skills=%s",
            candidate.candidate_id,
            original_phone_count,
            len(candidate.phones),
            len(candidate.skills),
        )


def _normalize_date_preserving_invalid(
    date_normalizer: DateNormalizer,
    value: str | None,
) -> str | None:
    normalized_value = date_normalizer.normalize(value)
    if normalized_value is None and value:
        return value
    return normalized_value


def _calculate_confidence(
    candidates: list[Candidate],
    validation_report: ValidationReport,
) -> ConfidenceResult:
    engine = ConfidenceEngine()
    source_reliability = _average_source_reliability(engine, candidates)
    agreement = _agreement_score(candidates)
    return engine.calculate_from_components(
        source_reliability=source_reliability,
        agreement=agreement,
        validation_success=validation_report.is_valid,
    )


def _average_source_reliability(
    engine: ConfidenceEngine,
    candidates: list[Candidate],
) -> float:
    scores = [engine.source_reliability(_candidate_source(candidate)) for candidate in candidates]
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _agreement_score(candidates: list[Candidate]) -> float:
    if len(candidates) <= 1:
        return 1.0

    scores = [
        _field_agreement([candidate.full_name for candidate in candidates]),
        _field_agreement([candidate.headline for candidate in candidates]),
        _field_agreement([email for candidate in candidates for email in candidate.emails]),
        _field_agreement([phone for candidate in candidates for phone in candidate.phones]),
        _field_agreement([skill.name for candidate in candidates for skill in candidate.skills]),
    ]
    observed_scores = [score for score in scores if score is not None]
    if not observed_scores:
        return 0.0
    return sum(observed_scores) / len(observed_scores)


def _field_agreement(values: list[str | None]) -> float | None:
    observed = [value.strip().casefold() for value in values if isinstance(value, str) and value.strip()]
    if not observed:
        return None
    return max(observed.count(value) for value in set(observed)) / len(observed)


def _load_projection_config(config_path: str | None) -> dict[str, Any]:
    if config_path is None:
        LOGGER.info("Projection config loaded: default")
        return DEFAULT_PROJECTION_CONFIG

    path = Path(config_path)
    with path.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)
    LOGGER.info("Projection config loaded: %s", path)
    return config


def _write_outputs(
    output_dir: Path,
    merged_candidate: Candidate,
    projected_json: str,
    validation_report: ValidationReport,
    confidence_result: ConfidenceResult,
) -> None:
    _write_text(output_dir / "canonical_candidate.json", merged_candidate.to_json(indent=2))
    _write_text(output_dir / "projected_candidate.json", projected_json)
    _write_text(output_dir / "validation_report.json", validation_report.to_json(indent=2))
    _write_text(output_dir / "confidence_report.json", json.dumps(asdict(confidence_result), indent=2))
    LOGGER.info("JSON outputs written to %s", output_dir)


def _write_text(path: Path, content: str) -> None:
    path.write_text(content + "\n", encoding="utf-8")


def _log_merge_decisions(candidate: Candidate) -> None:
    for record in candidate.provenance:
        if record.source == MergeEngine.SOURCE_NAME:
            LOGGER.info(
                "Merge decision: field=%s reason=%s value=%r",
                record.field_name,
                record.source_field,
                record.value,
            )


def _log_validation(report: ValidationReport) -> None:
    LOGGER.info(
        "Validation completed: errors=%s warnings=%s",
        len(report.errors),
        len(report.warnings),
    )
    for error in report.errors:
        LOGGER.error(
            "Validation error: field=%s message=%s value=%r",
            error.field_name,
            error.message,
            error.value,
        )
    for warning in report.warnings:
        LOGGER.warning(
            "Validation warning: field=%s message=%s value=%r",
            warning.field_name,
            warning.message,
            warning.value,
        )


def _extracted_fields(candidate: Candidate) -> list[str]:
    candidate_data = candidate.to_dict()
    return [
        field_name
        for field_name, value in candidate_data.items()
        if field_name != "provenance" and value not in (None, "", [])
    ]


def _candidate_source(candidate: Candidate) -> str:
    if candidate.provenance:
        return candidate.provenance[0].source
    return candidate.candidate_id.split(":", maxsplit=1)[0]


def _print_summary(
    output_dir: Path,
    candidates: list[Candidate],
    merged_candidate: Candidate,
    validation_report: ValidationReport,
    confidence_result: ConfidenceResult,
) -> None:
    print("Pipeline complete")
    print(f"Sources parsed: {len(candidates)}")
    print(f"Candidate ID: {merged_candidate.candidate_id}")
    print(f"Validation errors: {len(validation_report.errors)}")
    print(f"Validation warnings: {len(validation_report.warnings)}")
    print(f"Confidence: {confidence_result.score:.2f}")
    print(f"Output directory: {output_dir}")
    print("Log file: pipeline.log")


if __name__ == "__main__":
    main()
