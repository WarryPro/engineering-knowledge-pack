"""JSON Schema validation for knowledge frontmatter."""

import json
from pathlib import Path
from typing import Dict, List

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schema" / "knowledge-frontmatter.schema.json"


def load_schema():
    # type: () -> Dict
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_schema(frontmatter, path):
    # type: (Dict, str) -> List[str]
    """Validate frontmatter against knowledge-frontmatter.schema.json."""
    schema = load_schema()
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(frontmatter), key=lambda e: list(e.path)):
        location = ".".join(str(part) for part in error.path) or "frontmatter"
        errors.append("[SCHEMA] {}: {}: {}".format(path, location, error.message))
    return errors
