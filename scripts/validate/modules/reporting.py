"""Validation result formatting and reporting."""

import sys


class ValidationResult(object):
    def __init__(self):
        self.errors = []  # type: list
        self.warnings = []  # type: list

    def add_errors(self, items):
        # type: (list) -> None
        self.errors.extend(items)

    def add_warnings(self, items):
        # type: (list) -> None
        self.warnings.extend(items)

    @property
    def passed(self):
        # type: () -> bool
        return not self.errors

    def format_output(self):
        # type: () -> str
        lines = ["EKP Validator v2.3", ""]

        if self.errors:
            lines.append("Errors:")
            lines.extend("  {}".format(item) for item in self.errors)
            lines.append("")

        if self.warnings:
            lines.append("Warnings:")
            lines.extend("  {}".format(item) for item in self.warnings)
            lines.append("")

        lines.append("Result:")
        lines.append("PASSED" if self.passed else "FAILED")
        return "\n".join(lines)

    def print_report(self, strict=False):
        # type: (bool) -> int
        output = self.format_output()
        if self.errors or (strict and self.warnings):
            print(output, file=sys.stderr)
            return 1

        if self.warnings:
            print(output)

        print("Validation passed.")
        return 0
