"""Data models for adapter extraction and rule generation."""

import sys

if sys.version_info >= (3, 7):
    from dataclasses import dataclass, field
else:
    def field(default_factory=None):  # type: ignore
        """Minimal field helper for Python 3.6 compatibility."""
        return {"default_factory": default_factory}

    def dataclass(cls):  # type: ignore
        """Minimal dataclass decorator for Python 3.6 compatibility."""
        annotations = getattr(cls, "__annotations__", {})
        defaults = {}
        for name, value in list(cls.__dict__.items()):
            if isinstance(value, dict) and "default_factory" in value:
                defaults[name] = value["default_factory"]
            elif not name.startswith("__") and not callable(value):
                defaults[name] = value

        def __init__(self, **kwargs):
            for name in annotations:
                if name in kwargs:
                    setattr(self, name, kwargs[name])
                elif name in defaults:
                    factory = defaults[name]
                    setattr(
                        self,
                        name,
                        factory() if callable(factory) else factory,
                    )
                else:
                    setattr(self, name, None)

        def __repr__(self):
            parts = []
            for name in annotations:
                parts.append("{}={!r}".format(name, getattr(self, name)))
            return "{}({})".format(cls.__name__, ", ".join(parts))

        cls.__init__ = __init__
        cls.__repr__ = __repr__
        return cls

from typing import Dict, List, Optional


@dataclass
class ConceptRule:
    """A single EKP concept extracted from a knowledge document body."""

    concept_id: str
    title: str
    implements: List[str]
    intent: str
    rules: List[str]
    source_document: str
    good_examples: Optional[str] = None
    bad_examples: Optional[str] = None
    review_signals: Optional[str] = None


@dataclass
class DocumentFlow:
    """An AI Decision Flow section extracted from a knowledge document."""

    document_path: str
    title: str
    decision_flow: str
    enforcement_rules: List[Dict[str, str]]
    source_document: str


@dataclass
class GeneratedRule:
    """A tool-ready rule derived from extracted knowledge (used by target adapters)."""

    name: str
    description: str
    always_apply: bool
    directives: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
