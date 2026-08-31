"""Consumer compatibility capability labels (informational)."""

from __future__ import annotations

from typing import Dict

CapabilityStatus = str

SUPPORTED = "supported"
PILOT = "pilot"
UNSUPPORTED = "unsupported"
FUTURE = "future"

CAPABILITIES: Dict[str, Dict[str, CapabilityStatus]] = {
    "cursor-core": {"cursor": SUPPORTED},
    "cursor-php": {"cursor": SUPPORTED},
    "cursor-symfony": {"cursor": SUPPORTED},
    "cursor-typescript": {"cursor": SUPPORTED},
    "cursor-frontend": {"cursor": SUPPORTED},
    "cursor-devops": {"cursor": SUPPORTED},
    "cursor-nativescript": {"cursor": SUPPORTED},
    "cursor-flutter": {"cursor": SUPPORTED, "copilot": UNSUPPORTED},
    "ekp-core": {
        "cursor": SUPPORTED,
        "copilot": SUPPORTED,
        "antigravity": PILOT,
        "claude": PILOT,
    },
}


def adapter_status(profile: str, adapter: str) -> CapabilityStatus:
    """Return compatibility status for a profile/adapter pair."""
    profile_caps = CAPABILITIES.get(profile, {})
    return profile_caps.get(adapter, FUTURE)
