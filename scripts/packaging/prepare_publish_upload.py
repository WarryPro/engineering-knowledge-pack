#!/usr/bin/env python3
"""Verify publication artifacts and prepare a Twine-safe upload directory.

Release-only tooling — not an EKP runtime dependency.

The retained build artifact keeps wheel + sdist + SHA256SUMS together.
Twine / pypa/gh-action-pypi-publish pass ``packages-dir/*`` to upload, so
SHA256SUMS must not sit in the upload directory.

This helper:
  - requires exactly one wheel, one sdist, and SHA256SUMS in --artifact-dir
  - verifies the checksum manifest (fail closed on missing, unexpected,
    malformed, or mismatched entries)
  - copies the verified distributions into --upload-dir unchanged
  - never rebuilds or rewrites distribution bytes
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from pathlib import Path

MANIFEST_NAME = "SHA256SUMS"
# GNU coreutils ``sha256sum`` text mode: "<hex>  <filename>"
_MANIFEST_LINE_RE = re.compile(
    r"^([0-9a-fA-F]{64})  ([^/\0\n\r]+)$"
)


class UploadPrepareError(Exception):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _list_top_level_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise UploadPrepareError(
            "artifact directory does not exist: {}".format(directory)
        )
    files = sorted(
        (p for p in directory.iterdir() if p.is_file()),
        key=lambda p: p.name,
    )
    extras = [p for p in directory.iterdir() if not p.is_file()]
    if extras:
        raise UploadPrepareError(
            "unexpected non-file entries in artifact directory: {}".format(
                ", ".join(sorted(p.name for p in extras))
            )
        )
    return files


def parse_sha256sums(manifest: Path) -> dict[str, str]:
    if not manifest.is_file():
        raise UploadPrepareError("missing checksum manifest: {}".format(MANIFEST_NAME))
    text = manifest.read_text(encoding="utf-8")
    if not text.strip():
        raise UploadPrepareError("checksum manifest is empty")
    mapping: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\r")
        if not line.strip():
            raise UploadPrepareError(
                "checksum manifest has blank line at line {}".format(lineno)
            )
        match = _MANIFEST_LINE_RE.match(line)
        if match is None:
            raise UploadPrepareError(
                "malformed checksum manifest line {}: {!r}".format(lineno, raw)
            )
        digest, name = match.group(1).lower(), match.group(2)
        if name == MANIFEST_NAME:
            raise UploadPrepareError(
                "checksum manifest must not list {}".format(MANIFEST_NAME)
            )
        if name in mapping:
            raise UploadPrepareError(
                "duplicate checksum manifest entry: {}".format(name)
            )
        mapping[name] = digest
    return mapping


def classify_distributions(files: list[Path]) -> tuple[Path, Path, Path]:
    wheels = [p for p in files if p.name.endswith(".whl")]
    sdists = [p for p in files if p.name.endswith(".tar.gz")]
    manifests = [p for p in files if p.name == MANIFEST_NAME]
    others = [
        p
        for p in files
        if p not in wheels and p not in sdists and p not in manifests
    ]
    if others:
        raise UploadPrepareError(
            "unexpected files in artifact directory: {}".format(
                ", ".join(p.name for p in others)
            )
        )
    if len(manifests) != 1:
        raise UploadPrepareError(
            "expected exactly one {}; found {}".format(MANIFEST_NAME, len(manifests))
        )
    if len(wheels) != 1:
        raise UploadPrepareError(
            "expected exactly one wheel; found {}".format(len(wheels))
        )
    if len(sdists) != 1:
        raise UploadPrepareError(
            "expected exactly one sdist; found {}".format(len(sdists))
        )
    if len(files) != 3:
        raise UploadPrepareError(
            "expected exactly 3 artifact files (wheel, sdist, {}); found {}".format(
                MANIFEST_NAME, len(files)
            )
        )
    return wheels[0], sdists[0], manifests[0]


def verify_checksums(wheel: Path, sdist: Path, manifest: Path) -> dict[str, str]:
    expected = parse_sha256sums(manifest)
    actual_names = {wheel.name, sdist.name}
    expected_names = set(expected)
    if expected_names != actual_names:
        missing = sorted(actual_names - expected_names)
        unexpected = sorted(expected_names - actual_names)
        parts = []
        if missing:
            parts.append("missing from manifest: {}".format(", ".join(missing)))
        if unexpected:
            parts.append("unexpected in manifest: {}".format(", ".join(unexpected)))
        raise UploadPrepareError("; ".join(parts) or "checksum manifest name mismatch")
    for path in (wheel, sdist):
        digest = _sha256(path)
        if digest != expected[path.name]:
            raise UploadPrepareError(
                "checksum mismatch for {}: expected {} got {}".format(
                    path.name, expected[path.name], digest
                )
            )
    return expected


def prepare_upload(*, artifact_dir: Path, upload_dir: Path) -> dict:
    artifact_dir = artifact_dir.resolve()
    upload_dir = upload_dir.resolve()
    files = _list_top_level_files(artifact_dir)
    wheel, sdist, manifest = classify_distributions(files)
    verify_checksums(wheel, sdist, manifest)

    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    upload_dir.mkdir(parents=True)

    dest_wheel = upload_dir / wheel.name
    dest_sdist = upload_dir / sdist.name
    shutil.copy2(wheel, dest_wheel)
    shutil.copy2(sdist, dest_sdist)

    if _sha256(dest_wheel) != _sha256(wheel) or _sha256(dest_sdist) != _sha256(sdist):
        raise UploadPrepareError("upload copy altered distribution bytes")

    uploaded = sorted(p.name for p in upload_dir.iterdir() if p.is_file())
    if uploaded != sorted([wheel.name, sdist.name]):
        raise UploadPrepareError(
            "upload directory contents incorrect: {}".format(", ".join(uploaded))
        )
    if (upload_dir / MANIFEST_NAME).exists():
        raise UploadPrepareError(
            "{} must not be present in upload directory".format(MANIFEST_NAME)
        )

    return {
        "wheel": wheel.name,
        "sdist": sdist.name,
        "wheel_sha256": _sha256(dest_wheel),
        "sdist_sha256": _sha256(dest_sdist),
        "upload_dir": str(upload_dir),
        "upload_files": uploaded,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir",
        required=True,
        help="downloaded publication artifact directory (wheel + sdist + SHA256SUMS)",
    )
    parser.add_argument(
        "--upload-dir",
        required=True,
        help="Twine packages-dir output (verified wheel + sdist only)",
    )
    args = parser.parse_args(argv)
    try:
        result = prepare_upload(
            artifact_dir=Path(args.artifact_dir),
            upload_dir=Path(args.upload_dir),
        )
    except UploadPrepareError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    print(
        "upload-ready wheel={wheel} sdist={sdist} files={upload_files}".format(
            **result
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
