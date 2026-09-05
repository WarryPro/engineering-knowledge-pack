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


def exclusive_create_from_temp(temp_path: Path, target: Path) -> None:
    """
    Publish ``temp_path`` to ``target`` only if ``target`` does not already exist.

    Raises ``FileExistsError`` when the destination already exists or is a symlink.
    """
    if target.exists() or target.is_symlink():
        raise FileExistsError(str(target))

    try:
        os.link(str(temp_path), str(target))
        try:
            temp_path.unlink()
        except OSError:
            pass
        return
    except FileExistsError:
        raise
    except OSError:
        pass

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    data = temp_path.read_bytes()
    try:
        fd = os.open(str(target), flags)
    except FileExistsError:
        raise
    try:
        os.write(fd, data)
        try:
            os.fsync(fd)
        except OSError:
            pass
    finally:
        os.close(fd)

    try:
        temp_path.unlink()
    except OSError:
        pass
