"""Portable workspace path validation for schema2 project intent."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence, Tuple

from ekp.config.models import ProjectConfigError, WorkspaceIntent

# Glob / portable metacharacters forbidden in workspace paths (D61).
_FORBIDDEN_PATH_CHARS = frozenset(
    {
        "*",
        "?",
        "[",
        "]",
        "{",
        "}",
        "<",
        ">",
        ":",
        '"',
        "|",
        "\\",
    }
)

_WINDOWS_RESERVED_BASENAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
)


def _reject_control_chars(value: str, *, label: str) -> None:
    for ch in value:
        code = ord(ch)
        if code <= 0x1F or code == 0x7F:
            raise ProjectConfigError(
                "{} contains forbidden control character U+{:04X}".format(label, code)
            )


def _device_basename(segment: str) -> str:
    """Windows device name is the portion before the first '.' (case-insensitive)."""
    return segment.split(".", 1)[0].upper()


def canonicalize_workspace_path(raw: str) -> str:
    """
    Validate and return the canonical lexical workspace path.

    Contract (AZ-A): only already-canonical POSIX relative paths are accepted.
    Noncanonical aliases are refused rather than silently rewritten, so results
    are host-independent. Output always uses ``/`` separators with no leading,
    trailing, or empty segments.
    """
    if not isinstance(raw, str):
        raise ProjectConfigError("workspace path must be a string")
    if raw == "":
        raise ProjectConfigError("workspace path must not be empty")
    if raw == ".":
        raise ProjectConfigError('workspace path must not be "."')

    _reject_control_chars(raw, label="workspace path")

    for ch in raw:
        if ch in _FORBIDDEN_PATH_CHARS:
            raise ProjectConfigError(
                "workspace path contains forbidden character {!r}: {}".format(ch, raw)
            )

    if raw.startswith("/") or raw.startswith("\\"):
        raise ProjectConfigError("workspace path must be relative: {}".format(raw))

    # Drive-qualified (Windows) or scheme-like absolute forms.
    if len(raw) >= 2 and raw[1] == ":":
        raise ProjectConfigError(
            "workspace path must not be drive-qualified: {}".format(raw)
        )

    if "\\" in raw:
        raise ProjectConfigError(
            "workspace path must use '/' separators only: {}".format(raw)
        )

    if raw.endswith("/") or "//" in raw:
        raise ProjectConfigError(
            "workspace path must be canonical (no empty segments): {}".format(raw)
        )

    segments = raw.split("/")
    if not segments or any(seg == "" for seg in segments):
        raise ProjectConfigError(
            "workspace path must be canonical (no empty segments): {}".format(raw)
        )

    for segment in segments:
        _reject_control_chars(segment, label="workspace path segment")
        if segment in (".", ".."):
            raise ProjectConfigError(
                "workspace path must not contain {!r} segments: {}".format(
                    segment, raw
                )
            )
        if segment.endswith(".") or segment.endswith(" "):
            raise ProjectConfigError(
                "workspace path segment must not end with '.' or space: {!r}".format(
                    segment
                )
            )
        if _device_basename(segment) in _WINDOWS_RESERVED_BASENAMES:
            raise ProjectConfigError(
                "workspace path segment uses a reserved Windows device name: {!r}".format(
                    segment
                )
            )
        if segment == ".ekp":
            raise ProjectConfigError(
                "workspace path must not use or be under .ekp: {}".format(raw)
            )

    return "/".join(segments)


def workspace_paths_overlap(left: str, right: str) -> bool:
    """True when one canonical path is an ancestor of the other (segment-wise)."""
    if left == right:
        return True
    left_parts = left.split("/")
    right_parts = right.split("/")
    shorter, longer = (
        (left_parts, right_parts)
        if len(left_parts) <= len(right_parts)
        else (right_parts, left_parts)
    )
    return longer[: len(shorter)] == shorter


def validate_workspace_path_uniqueness(paths: Sequence[str]) -> None:
    """Refuse duplicate canonical workspace paths."""
    seen = set()
    for path in paths:
        if path in seen:
            raise ProjectConfigError(
                "duplicate workspace path after canonicalization: {}".format(path)
            )
        seen.add(path)


def validate_workspace_path_overlap(paths: Sequence[str]) -> None:
    """Refuse ancestor/descendant workspace path pairs."""
    ordered = sorted(paths)
    for index, path in enumerate(ordered):
        for other in ordered[index + 1 :]:
            if workspace_paths_overlap(path, other):
                raise ProjectConfigError(
                    "overlapping workspace paths are not allowed: {!r} and {!r}".format(
                        path, other
                    )
                )


def validate_workspace_on_filesystem(project_root: Path, canonical_path: str) -> None:
    """
    Validate that a canonical workspace path exists as a real directory under root.

    Refuses missing paths, non-directories, any symlink path segment (including
    the final component), and escapes outside ``project_root``.
    """
    root = Path(project_root).resolve()
    current = root
    parts = canonical_path.split("/")
    for index, part in enumerate(parts):
        current = current / part
        if current.is_symlink():
            raise ProjectConfigError(
                "workspace path must not contain symlink segments: {}".format(
                    canonical_path
                )
            )
        if not current.exists():
            raise ProjectConfigError(
                "workspace directory does not exist: {}".format(canonical_path)
            )
        if not current.is_dir():
            raise ProjectConfigError(
                "workspace path is not a directory: {}".format(canonical_path)
            )
        # Re-check after existence: some platforms report is_dir True for link targets.
        if current.is_symlink():
            raise ProjectConfigError(
                "workspace path must not contain symlink segments: {}".format(
                    canonical_path
                )
            )

    try:
        current.resolve().relative_to(root)
    except ValueError as exc:
        raise ProjectConfigError(
            "workspace path escapes project root: {}".format(canonical_path)
        ) from exc


def build_workspace_intents(
    raw_workspaces: Iterable[dict],
) -> Tuple[WorkspaceIntent, ...]:
    """
    Lexically validate workspace mappings into canonical WorkspaceIntent values.

    Does not perform filesystem checks. Overlap/uniqueness are enforced here.
    """
    built = []
    for entry in raw_workspaces:
        if not isinstance(entry, dict):
            raise ProjectConfigError("workspace entry must be a mapping/object")
        if set(entry.keys()) - {"path", "components"}:
            raise ProjectConfigError(
                "workspace entry contains unsupported fields: {}".format(
                    sorted(set(entry.keys()) - {"path", "components"})
                )
            )
        if "path" not in entry or "components" not in entry:
            raise ProjectConfigError(
                "workspace entry requires path and components"
            )
        path = canonicalize_workspace_path(str(entry["path"]))
        components = tuple(str(item) for item in entry["components"])
        if not components:
            raise ProjectConfigError(
                "workspace {!r} requires at least one component".format(path)
            )
        built.append(WorkspaceIntent(path=path, components=components))

    paths = [item.path for item in built]
    validate_workspace_path_uniqueness(paths)
    validate_workspace_path_overlap(paths)
    # Stable model order: ascending canonical path (deterministic for render).
    built.sort(key=lambda item: item.path)
    return tuple(built)
