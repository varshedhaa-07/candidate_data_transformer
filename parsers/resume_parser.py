"""PDF resume parser implementation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import pdfplumber

from models import Candidate, Education, Experience, ProvenanceRecord, Skill
from parsers.source_parser import SourceParser


class ResumeParser(SourceParser):
    """Parses PDF resumes into canonical candidates using conservative heuristics."""

    SOURCE_NAME = "resume_pdf"

    EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
    PHONE_PATTERN = re.compile(
        r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}(?!\w)"
    )
    NAME_PATTERN = re.compile(r"^[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,3}$")
    SECTION_HEADER_PATTERN = re.compile(
        r"^(skills?|technical skills|education|experience|work experience|employment|"
        r"professional experience|summary|profile|headline|objective)\s*:?\s*$",
        re.IGNORECASE,
    )

    SKILL_SECTION_HEADERS = ("skill", "skills", "technical skills")
    EDUCATION_SECTION_HEADERS = ("education",)
    EXPERIENCE_SECTION_HEADERS = (
        "experience",
        "work experience",
        "employment",
        "professional experience",
    )
    HEADLINE_SECTION_HEADERS = ("summary", "profile", "headline", "objective")

    def parse(self, file_path: str | Path) -> Candidate:
        """Parse a PDF resume into a candidate profile."""
        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"ResumeParser only supports PDF files: {path}")

        text = self._extract_text(path)
        lines = self._non_empty_lines(text)
        sections = self._extract_sections(lines)

        full_name = self._extract_name(lines)
        emails = self._unique_matches(self.EMAIL_PATTERN, text)
        phones = self._unique_matches(self.PHONE_PATTERN, text)
        headline = self._extract_headline(lines, sections)
        skills = self._extract_skills(sections)
        education = self._extract_education(sections)
        experience = self._extract_experience(sections)

        candidate = Candidate(
            candidate_id=f"{self.SOURCE_NAME}:{path.stem}",
            full_name=full_name,
            emails=emails,
            phones=phones,
            headline=headline,
            skills=skills,
            education=education,
            experience=experience,
        )
        candidate.provenance = self._build_provenance(candidate)
        return candidate

    def _extract_text(self, path: Path) -> str:
        with pdfplumber.open(path) as pdf:
            page_text = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(page_text)

    def _non_empty_lines(self, text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _extract_name(self, lines: list[str]) -> str | None:
        for line in lines[:8]:
            if self.EMAIL_PATTERN.search(line) or self.PHONE_PATTERN.search(line):
                continue
            if self.SECTION_HEADER_PATTERN.match(line):
                continue
            if self.NAME_PATTERN.match(line):
                return line
        return None

    def _extract_headline(
        self,
        lines: list[str],
        sections: dict[str, list[str]],
    ) -> str | None:
        for header in self.HEADLINE_SECTION_HEADERS:
            content = sections.get(header)
            if content:
                return content[0]

        for line in lines[:10]:
            if line == self._extract_name(lines):
                continue
            if self.EMAIL_PATTERN.search(line) or self.PHONE_PATTERN.search(line):
                continue
            if self.SECTION_HEADER_PATTERN.match(line):
                continue
            return line
        return None

    def _extract_sections(self, lines: list[str]) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {}
        current_header: str | None = None

        for line in lines:
            if self.SECTION_HEADER_PATTERN.match(line):
                normalized = line.casefold().rstrip(":").strip()
                current_header = normalized
                sections.setdefault(current_header, [])
                continue
            if current_header is not None:
                sections[current_header].append(line)

        return sections

    def _extract_skills(self, sections: dict[str, list[str]]) -> list[Skill]:
        skill_lines = self._first_section(sections, self.SKILL_SECTION_HEADERS)
        if not skill_lines:
            return []

        skill_names: list[str] = []
        for line in skill_lines:
            parts = re.split(r"[,;|\u2022\u00b7]", line)
            skill_names.extend(part.strip(" -\t") for part in parts if part.strip(" -\t"))

        return [Skill(name=name) for name in self._deduplicate(skill_names)]

    def _extract_education(self, sections: dict[str, list[str]]) -> list[Education]:
        education_lines = self._first_section(sections, self.EDUCATION_SECTION_HEADERS)
        if not education_lines:
            return []
        return [Education(description="\n".join(education_lines))]

    def _extract_experience(self, sections: dict[str, list[str]]) -> list[Experience]:
        experience_lines = self._first_section(sections, self.EXPERIENCE_SECTION_HEADERS)
        if not experience_lines:
            return []
        return [Experience(description="\n".join(experience_lines))]

    def _first_section(
        self,
        sections: dict[str, list[str]],
        headers: tuple[str, ...],
    ) -> list[str]:
        for header in headers:
            content = sections.get(header)
            if content:
                return content
        return []

    def _unique_matches(self, pattern: re.Pattern[str], text: str) -> list[str]:
        return self._deduplicate(match.group(0) for match in pattern.finditer(text))

    def _deduplicate(self, values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        unique_values: list[str] = []

        for value in values:
            if not isinstance(value, str):
                continue
            if value in seen:
                continue
            seen.add(value)
            unique_values.append(value)

        return unique_values

    def _build_provenance(self, candidate: Candidate) -> list[ProvenanceRecord]:
        provenance: list[ProvenanceRecord] = []

        if candidate.full_name:
            provenance.append(self._provenance("full_name", "resume_text", candidate.full_name))
        provenance.extend(
            self._provenance("emails", "resume_text", email) for email in candidate.emails
        )
        provenance.extend(
            self._provenance("phones", "resume_text", phone) for phone in candidate.phones
        )
        if candidate.headline:
            provenance.append(self._provenance("headline", "resume_text", candidate.headline))
        provenance.extend(
            self._provenance("skills", "skills_section", skill.name) for skill in candidate.skills
        )
        provenance.extend(
            self._provenance("education.description", "education_section", item.description)
            for item in candidate.education
            if item.description
        )
        provenance.extend(
            self._provenance("experience.description", "experience_section", item.description)
            for item in candidate.experience
            if item.description
        )

        return provenance

    def _provenance(
        self,
        field_name: str,
        source_field: str,
        value: str,
    ) -> ProvenanceRecord:
        return ProvenanceRecord(
            source=self.SOURCE_NAME,
            field_name=field_name,
            source_field=source_field,
            value=value,
        )
