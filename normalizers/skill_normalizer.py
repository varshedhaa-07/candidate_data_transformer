"""Skill normalization utilities."""

from __future__ import annotations


class SkillNormalizer:
    """Normalizes skill names to canonical values."""

    CANONICAL_SKILLS = {
        "c plus plus": "C++",
        "cpp": "C++",
        "c++": "C++",
        "reactjs": "React",
        "react.js": "React",
        "react": "React",
        "nodejs": "Node.js",
        "node.js": "Node.js",
        "node": "Node.js",
    }

    def normalize(self, skills: list[str] | tuple[str, ...] | None) -> list[str]:
        """Return canonical skill names with duplicates removed."""
        if not skills:
            return []

        normalized_skills: list[str] = []
        seen: set[str] = set()

        for skill in skills:
            canonical_skill = self.normalize_one(skill)
            if canonical_skill is None:
                continue

            dedupe_key = canonical_skill.casefold()
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            normalized_skills.append(canonical_skill)

        return normalized_skills

    def normalize_one(self, skill: str | None) -> str | None:
        """Normalize a single skill name."""
        if skill is None:
            return None

        cleaned = skill.strip()
        if not cleaned:
            return None

        return self.CANONICAL_SKILLS.get(cleaned.casefold(), cleaned)

