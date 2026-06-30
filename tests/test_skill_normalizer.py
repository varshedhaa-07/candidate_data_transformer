"""Tests for skill normalization."""

from normalizers import SkillNormalizer


def test_skill_normalizer_returns_canonical_names_and_removes_duplicates() -> None:
    skills = ["C Plus Plus", "CPP", "ReactJS", "react", "NodeJS", "Python"]

    assert SkillNormalizer().normalize(skills) == ["C++", "React", "Node.js", "Python"]


def test_skill_normalizer_handles_empty_values() -> None:
    normalizer = SkillNormalizer()

    assert normalizer.normalize([" ", "", "CPP"]) == ["C++"]
    assert normalizer.normalize(None) == []
    assert normalizer.normalize_one(None) is None

