"""Profile selection for install."""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from ekp.detection.models import DetectionReport
from ekp.install.errors import InstallSelectionError
from ekp.resolution.catalog import list_cursor_profiles, validate_profile_name

PROFILE_LABELS = {
    "cursor-core": "Core engineering only",
    "cursor-php": "PHP",
    "cursor-symfony": "Symfony",
    "cursor-typescript": "TypeScript",
    "cursor-frontend": "Frontend",
    "cursor-devops": "DevOps",
    "cursor-nativescript": "NativeScript",
    "cursor-flutter": "Flutter",
}

PROFILE_CHOICES = tuple(PROFILE_LABELS.keys())


def validate_explicit_profile(profile: str, resource_root=None) -> str:
    """Validate an explicit --profile value."""
    if not validate_profile_name(profile, resource_root):
        available = ", ".join(list_cursor_profiles(resource_root))
        raise InstallSelectionError(
            "Unknown or unsupported Consumer CLI profile:\n{}\n\nAvailable profiles:\n  {}".format(
                profile,
                "\n  ".join(list_cursor_profiles(resource_root)),
            )
        )
    return profile


def select_profile(
    report: DetectionReport,
    explicit_profile: Optional[str],
    assume_yes: bool,
    resource_root=None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> Tuple[str, List[str]]:
    """
    Resolve the profile to install.

    Returns profile name and additional concerns for human output.
    """
    if explicit_profile:
        return validate_explicit_profile(explicit_profile, resource_root), list(
            report.additional_concerns
        )

    if report.recommended_profile:
        return report.recommended_profile, list(report.additional_concerns)

    if report.ambiguous:
        if assume_yes:
            candidates = ", ".join(report.candidate_profiles)
            raise InstallSelectionError(
                "Multiple independent stacks detected.\n\n"
                "Specify one explicitly:\n\n"
                "  ekp install --profile {} --yes".format(
                    report.candidate_profiles[0] if report.candidate_profiles else "cursor-symfony"
                )
                + ("\n\nCandidates: {}".format(candidates) if candidates else "")
            )
        return _prompt_ambiguous(report, input_fn, output_fn)

    if not report.technologies:
        if assume_yes:
            raise InstallSelectionError(
                "No technology stack detected.\n\n"
                "For non-interactive installation specify:\n\n"
                "  ekp install --profile cursor-flutter --yes"
            )
        return _prompt_empty(input_fn, output_fn), list(report.additional_concerns)

    raise InstallSelectionError(
        "Unable to determine a profile automatically. "
        "Specify one with --profile."
    )


def _prompt_ambiguous(
    report: DetectionReport,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> Tuple[str, List[str]]:
    output_fn("")
    output_fn("Multiple stacks detected. Choose a profile:")
    options: List[str] = []
    for candidate in report.candidate_profiles:
        label = PROFILE_LABELS.get(candidate, candidate)
        options.append(candidate)
        output_fn("  {}. {}".format(len(options), label))
    options.append("__other__")
    output_fn("  {}. Choose another supported profile".format(len(options)))

    while True:
        choice = input_fn("Selection: ").strip()
        if not choice.isdigit():
            output_fn("Enter a number from the list.")
            continue
        index = int(choice)
        if 1 <= index <= len(report.candidate_profiles):
            return report.candidate_profiles[index - 1], list(report.additional_concerns)
        if index == len(options):
            return _prompt_supported_profile(input_fn, output_fn), list(report.additional_concerns)
        output_fn("Invalid selection.")


def _prompt_empty(
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> str:
    output_fn("")
    output_fn("No technology stack detected. Choose the intended stack:")
    for index, profile in enumerate(PROFILE_CHOICES, start=1):
        output_fn("  {}. {}".format(index, PROFILE_LABELS[profile]))

    while True:
        choice = input_fn("Selection: ").strip()
        if not choice.isdigit():
            output_fn("Enter a number from the list.")
            continue
        index = int(choice)
        if 1 <= index <= len(PROFILE_CHOICES):
            return PROFILE_CHOICES[index - 1]
        output_fn("Invalid selection.")


def _prompt_supported_profile(
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> str:
    output_fn("")
    output_fn("Supported Cursor profiles:")
    for index, profile in enumerate(PROFILE_CHOICES, start=1):
        output_fn("  {}. {}".format(index, PROFILE_LABELS[profile]))

    while True:
        choice = input_fn("Selection: ").strip()
        if not choice.isdigit():
            output_fn("Enter a number from the list.")
            continue
        index = int(choice)
        if 1 <= index <= len(PROFILE_CHOICES):
            return PROFILE_CHOICES[index - 1]
        output_fn("Invalid selection.")
