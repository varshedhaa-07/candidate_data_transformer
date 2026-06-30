"""Source parser interfaces and implementations."""

from parsers.source_parser import SourceParser

__all__ = [
    "RecruiterCSVParser",
    "ResumeParser",
    "SourceParser",
]


def __getattr__(name: str) -> object:
    """Lazily import parser implementations with optional dependencies."""
    if name == "RecruiterCSVParser":
        from parsers.recruiter_csv_parser import RecruiterCSVParser

        return RecruiterCSVParser
    if name == "ResumeParser":
        from parsers.resume_parser import ResumeParser

        return ResumeParser
    raise AttributeError(f"module 'parsers' has no attribute {name!r}")
