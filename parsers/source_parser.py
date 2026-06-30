"""Parser plugin interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from models import Candidate


class SourceParser(ABC):
    """Base interface for source-specific candidate profile parsers."""

    @abstractmethod
    def parse(self, file_path: str | Path) -> Candidate:
        """Parse a source file into a canonical candidate profile."""
        raise NotImplementedError

