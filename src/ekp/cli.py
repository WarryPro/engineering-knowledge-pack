"""Minimal EKP consumer CLI entry point."""

import argparse
import sys

from ekp.detection.render import render_human, render_json
from ekp.detection.service import DetectionService
from ekp.discovery import (
    format_discovery_table,
    list_selectable_components,
    list_supported_assistants,
)
from ekp.install.deploy.registry import build_default_deploy_registry
from ekp.install.service import InstallRequest, InstallService
from ekp.lifecycle.configure_cli import run_configure_cli
from ekp.lifecycle.uninstall import UninstallRequest, UninstallService
from ekp.lifecycle.update import UpdateRequest, UpdateService
from ekp.paths import get_ekp_root
from ekp.status.render import render_human as render_status_human
from ekp.status.render import render_json as render_status_json
from ekp.status.service import StatusRequest, StatusService
from ekp.version import get_version

_EPILOG = """\
examples:
  Existing project (detect -> install -> status):
    ekp detect
    ekp install
    ekp status

  Empty project (explicit components):
    ekp list components
    ekp install --component symfony --component frontend

  Select assistants (default is Cursor when omitted):
    ekp install --component typescript --assistant cursor --assistant copilot

  Declare existing workspace directories (schema2):
    ekp install --no-root-components \\
      --workspace apps/api symfony --workspace apps/web frontend

  After upgrading the EKP package, synchronize the project:
    ekp update

  Change composition intent on a HEALTHY install:
    ekp configure --component typescript --assistant cursor

  Discover package catalogs (offline; no project required):
    ekp list components
    ekp list assistants
"""


class _PrintPackageVersion(argparse.Action):
    """Print the installed package version and exit successfully."""

    def __call__(self, parser, namespace, values, option_string=None):
        print(get_version())
        parser.exit(0)


def _supported_assistants_help():
    return ", ".join(build_default_deploy_registry().supported_assistants())


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="ekp",
        description="Engineering Knowledge Pack — consumer CLI",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action=_PrintPackageVersion,
        nargs=0,
        help="Show installed EKP package version and exit",
    )
    subparsers = parser.add_subparsers(dest="command")

    detect_parser = subparsers.add_parser(
        "detect",
        help="Detect project technologies and propose components (or a legacy Cursor profile)",
    )
    detect_parser.add_argument(
        "--path",
        default=".",
        help="Project directory to scan (default: current directory)",
    )
    detect_parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )

    subparsers.add_parser(
        "version",
        help="Show installed EKP version and resource root",
    )

    list_parser = subparsers.add_parser(
        "list",
        help="List selectable components or supported assistants",
        description=(
            "List catalogs from the installed EKP package.\n\n"
            "Works offline outside a project. Does not detect technologies, "
            "prompt, or write managed project files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  ekp list components\n"
            "  ekp list assistants\n"
        ),
    )
    list_subparsers = list_parser.add_subparsers(dest="list_target")
    list_subparsers.add_parser(
        "components",
        help="List selectable technology component IDs for --component",
    )
    list_subparsers.add_parser(
        "assistants",
        help="List supported Consumer assistant IDs for --assistant",
    )

    install_parser = subparsers.add_parser(
        "install",
        help="Install EKP into a consumer project",
        description=(
            "Install EKP into a consumer project.\n\n"
            "examples:\n"
            "  ekp install\n"
            "  ekp install --component symfony --assistant cursor\n"
            "  ekp install --no-root-components "
            "--workspace apps/api symfony\n"
            "  ekp list components   # choose IDs for --component\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    install_parser.add_argument(
        "--path",
        default=".",
        help="Project directory to install into (default: current directory)",
    )
    install_parser.add_argument(
        "--profile",
        help=(
            "Legacy Cursor profile preset "
            "(mutually exclusive with --component and --assistant)"
        ),
    )
    install_parser.add_argument(
        "--component",
        action="append",
        dest="components",
        metavar="ID",
        help=(
            "Repeatable project technology component "
            "(mutually exclusive with --profile; see `ekp list components`)"
        ),
    )
    install_parser.add_argument(
        "--assistant",
        action="append",
        dest="assistants",
        metavar="ID",
        help=(
            "Repeatable managed AI assistant target "
            "(supported: {}; mutually exclusive with --profile; "
            "see `ekp list assistants`)".format(_supported_assistants_help())
        ),
    )
    install_parser.add_argument(
        "--workspace",
        nargs=2,
        action="append",
        dest="workspaces",
        metavar=("PATH", "COMPONENT"),
        help=(
            "Declare a workspace technology scope (PATH COMPONENT). "
            "Repeat to add workspaces or additional components for the same path. "
            "Implies schema2. Mutually exclusive with --profile. "
            "Workspace directories must already exist."
        ),
    )
    install_parser.add_argument(
        "--no-root-components",
        action="store_true",
        help=(
            "Explicitly use no root components for a schema2 workspace project "
            "(requires --workspace)"
        ),
    )
    install_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts (does not bypass safety checks)",
    )
    install_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show installation plan without writing files",
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Inspect EKP installation state in a consumer project",
    )
    status_parser.add_argument(
        "--path",
        default=".",
        help="Project directory to inspect (default: current directory)",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )

    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help="Remove EKP-managed files from a consumer project",
    )
    uninstall_parser.add_argument(
        "--path",
        default=".",
        help="Project directory to uninstall from (default: current directory)",
    )
    uninstall_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts (does not bypass safety checks)",
    )
    uninstall_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show uninstall plan without removing files",
    )

    update_parser = subparsers.add_parser(
        "update",
        help="Synchronize an installed project with the running EKP package",
        description=(
            "Synchronize an installed project with the running EKP package.\n\n"
            "Package upgrade (pipx/pip) updates the tool; `ekp update` "
            "synchronizes the project's managed files to the running package."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    update_parser.add_argument(
        "--path",
        default=".",
        help="Project directory to update (default: current directory)",
    )
    update_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts (does not bypass safety checks)",
    )
    update_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show update plan without writing files",
    )

    configure_parser = subparsers.add_parser(
        "configure",
        help="Change the managed project configuration",
        description=(
            "Change the exact desired configuration of an existing healthy "
            "composition installation.\n\n"
            "Desired-state semantics: flags together define the complete "
            "desired ProjectConfig (not add/remove deltas).\n\n"
            "With --yes or --dry-run, both component and assistant sets must "
            "be explicit for the desired schema (assistants always required; "
            "root/workspace dimensions via --component / --no-root-components "
            "and --workspace / --no-workspaces as applicable).\n\n"
            "examples:\n"
            "  ekp configure --component typescript --assistant cursor\n"
            "  ekp list components\n"
            "  ekp list assistants\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    configure_parser.add_argument(
        "--path",
        default=".",
        help="Project directory to configure (default: current directory)",
    )
    configure_parser.add_argument(
        "--component",
        action="append",
        dest="components",
        metavar="ID",
        help=(
            "Repeatable exact desired root component ID "
            "(with --yes/--dry-run, required unless --no-root-components; "
            "see `ekp list components`)"
        ),
    )
    configure_parser.add_argument(
        "--assistant",
        action="append",
        dest="assistants",
        metavar="ID",
        help=(
            "Repeatable exact desired assistant ID "
            "(supported: {}; with --yes/--dry-run, at least one is required; "
            "see `ekp list assistants`)".format(_supported_assistants_help())
        ),
    )
    configure_parser.add_argument(
        "--workspace",
        nargs=2,
        action="append",
        dest="workspaces",
        metavar=("PATH", "COMPONENT"),
        help=(
            "Declare a workspace technology scope (PATH COMPONENT). "
            "Repeat to add workspaces or components. "
            "For noninteractive configure, supplies the complete desired "
            "workspace set. Workspace directories must already exist."
        ),
    )
    configure_parser.add_argument(
        "--no-root-components",
        action="store_true",
        help=(
            "Explicitly use no root components for a schema2 workspace project"
        ),
    )
    configure_parser.add_argument(
        "--no-workspaces",
        action="store_true",
        help=(
            "Explicitly remove all workspaces and return to a schema1 root "
            "project (configure only)"
        ),
    )
    configure_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts (does not bypass safety checks)",
    )
    configure_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show configure plan without writing files (noninteractive)",
    )

    return parser, list_parser


def _run_list_command(args, list_parser):
    # type: (argparse.Namespace, argparse.ArgumentParser) -> int
    if args.list_target is None:
        list_parser.print_help()
        return 0
    if args.list_target == "components":
        sys.stdout.write(format_discovery_table(list_selectable_components()))
        return 0
    if args.list_target == "assistants":
        sys.stdout.write(format_discovery_table(list_supported_assistants()))
        return 0
    list_parser.print_help()
    return 0


def main(argv=None):
    # type: (list) -> int
    """CLI entry point registered as the ``ekp`` console script."""
    parser, list_parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(get_version())
        print("resource_root: {}".format(get_ekp_root()))
        return 0

    if args.command == "list":
        return _run_list_command(args, list_parser)

    if args.command == "detect":
        try:
            report = DetectionService().detect(path=args.path)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except OSError as exc:
            print("Detection failed: {}".format(exc), file=sys.stderr)
            return 1

        if args.json:
            print(render_json(report), end="")
        else:
            print(render_human(report))
        return 0

    if args.command == "install":
        try:
            result = InstallService().install(
                InstallRequest(
                    path=args.path,
                    profile=args.profile,
                    components=args.components,
                    assistants=args.assistants,
                    workspaces=args.workspaces,
                    no_root_components=args.no_root_components,
                    assume_yes=args.yes,
                    dry_run=args.dry_run,
                )
            )
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except OSError as exc:
            print("Installation failed: {}".format(exc), file=sys.stderr)
            return 5

        if result.message:
            stream = sys.stderr if result.exit_code != 0 else sys.stdout
            print(result.message, file=stream)
        return result.exit_code

    if args.command == "status":
        try:
            result = StatusService().inspect(StatusRequest(path=args.path))
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except OSError as exc:
            print("Status inspection failed: {}".format(exc), file=sys.stderr)
            return 1

        if args.json:
            print(render_status_json(result), end="")
        else:
            print(render_status_human(result))
        return result.exit_code

    if args.command == "uninstall":
        try:
            result = UninstallService().uninstall(
                UninstallRequest(
                    path=args.path,
                    assume_yes=args.yes,
                    dry_run=args.dry_run,
                )
            )
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except OSError as exc:
            print("Uninstall failed: {}".format(exc), file=sys.stderr)
            return 5

        if result.message:
            stream = sys.stderr if result.exit_code != 0 else sys.stdout
            print(result.message, file=stream)
        return result.exit_code

    if args.command == "update":
        try:
            result = UpdateService().update(
                UpdateRequest(
                    path=args.path,
                    assume_yes=args.yes,
                    dry_run=args.dry_run,
                )
            )
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except OSError as exc:
            print("Update failed: {}".format(exc), file=sys.stderr)
            return 5

        if result.message:
            stream = sys.stderr if result.exit_code != 0 else sys.stdout
            print(result.message, file=stream)
        return result.exit_code

    if args.command == "configure":
        try:
            result = run_configure_cli(
                path=args.path,
                components=args.components,
                assistants=args.assistants,
                workspaces=args.workspaces,
                no_root_components=args.no_root_components,
                no_workspaces=args.no_workspaces,
                assume_yes=args.yes,
                dry_run=args.dry_run,
            )
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except OSError as exc:
            print("Configure failed: {}".format(exc), file=sys.stderr)
            return 5

        if result.message:
            stream = sys.stderr if result.exit_code != 0 else sys.stdout
            print(result.message, file=stream)
        return result.exit_code

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
