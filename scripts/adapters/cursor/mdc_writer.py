"""Render GeneratedRule objects as Cursor .mdc rule files."""

from pathlib import Path

from common.models import GeneratedRule


def _yaml_value(value):
    # type: (str) -> str
    """Quote YAML values when required."""
    if not value:
        return '""'
    if any(char in value for char in ':{}[]&*#?|-<>=!%@\\"'):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return '"{}"'.format(escaped)
    return value


def render_mdc(rule, source_path, heading_title, preferences=None):
    # type: (GeneratedRule, str, str, list) -> str
    """Render a GeneratedRule as Cursor .mdc markdown."""
    lines = [
        "---",
        "description: {}".format(_yaml_value(rule.description)),
        "alwaysApply: {}".format("true" if rule.always_apply else "false"),
        "---",
        "",
        "# {}".format(heading_title),
        "",
        "> **Source:** `{}`".format(source_path),
        "",
    ]

    if rule.directives:
        lines.append("## Directives")
        lines.append("")
        for directive in rule.directives:
            if directive.startswith("- "):
                lines.append(directive)
            else:
                lines.append("- {}".format(directive))
        lines.append("")

    if rule.constraints:
        lines.append("## Constraints")
        lines.append("")
        for constraint in rule.constraints:
            if constraint.startswith("- "):
                lines.append(constraint)
            else:
                lines.append("- {}".format(constraint))
        lines.append("")

    if preferences:
        lines.append("## Preferences")
        lines.append("")
        for item in preferences:
            if item.startswith("- "):
                lines.append(item)
            else:
                lines.append("- {}".format(item))
        lines.append("")

    if rule.references:
        lines.append("## References")
        lines.append("")
        for reference in rule.references:
            lines.append("- {}".format(reference))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_mdc_file(output_path, rule, source_path, heading_title, preferences=None):
    # type: (Path, GeneratedRule, str, str, list) -> None
    """Write a GeneratedRule to a .mdc file."""
    content = render_mdc(rule, source_path, heading_title, preferences=preferences)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
