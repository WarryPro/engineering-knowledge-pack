"""Safe exclusive temporary files for consumer mutations."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


class ExclusiveTempFile:
    """EKP-owned exclusive temporary file in a destination directory."""

    def __init__(self, fd: int, path: Path):
        self._fd = fd
        self.path = path

    @classmethod
    def create(cls, directory: Path) -> "ExclusiveTempFile":
        directory.mkdir(parents=True, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix="ekp-", suffix=".tmp", dir=str(directory))
        return cls(fd, Path(path))

    def write_from_source(self, source: Path) -> None:
        with source.open("rb") as src, os.fdopen(self._fd, "wb") as dst:
            self._fd = -1
            shutil.copyfileobj(src, dst)
            dst.flush()
            try:
                os.fsync(dst.fileno())
            except OSError:
                pass

    def write_text(self, text: str, *, encoding: str = "utf-8") -> None:
        with os.fdopen(self._fd, "wb") as dst:
            self._fd = -1
            dst.write(text.encode(encoding))
            dst.flush()
            try:
                os.fsync(dst.fileno())
            except OSError:
                pass

    def close_fd(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def commit(self, target: Path) -> None:
        self.close_fd()
        os.replace(str(self.path), str(target))
        self.path = None

    def cleanup(self) -> None:
        self.close_fd()
        if self.path is not None:
            try:
                self.path.unlink()
            except OSError:
                pass
            self.path = None
