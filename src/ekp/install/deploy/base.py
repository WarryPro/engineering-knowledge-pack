"""Deployer abstract contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from ekp.install.deploy.models import DesiredManagedFile


class Deployer(ABC):
    """Assistant-specific mapping from an assembled bundle to desired managed files."""

    @property
    @abstractmethod
    def assistant_id(self) -> str:
        """Stable assistant identifier (e.g. ``cursor``)."""

    @abstractmethod
    def collect_desired_files(self, bundle_path: Path) -> List[DesiredManagedFile]:
        """Map ``bundle_path`` contents to validated desired consumer targets."""
