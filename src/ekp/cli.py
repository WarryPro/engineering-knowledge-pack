"""Minimal EKP consumer CLI entry point."""

import argparse
import sys

from ekp.detection.render import render_human, render_json
from ekp.detection.service import DetectionService
from ekp.install.service import InstallRequest, InstallService
from ekp.lifecycle.uninstall import UninstallRequest, UninstallService
from ekp.paths import get_ekp_root
from ekp.status.render import render_human as render_status_human
from ekp.status.render import render_json as render_status_json
from ekp.status.service import StatusRequest, StatusService
from ekp.version import get_version


def main(argv=None):
    # type: (list) -> int
    """CLI entry point registered as the ``ekp`` console script."""
    parser = argparse.ArgumentParser(
        prog="ekp",
        description="Engineering Knowledge Pack — consumer CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    detect_parser = subparsers.add_parser(
        "detect",
        help="Detect project technologies and recommend an existing Cursor profile",
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

    subparsers.add_parser("version", help="Show installed EKP version")

    install_parser = subparsers.add_parser(
        "install",
        help="Install EKP Cursor rules into a consumer project",
    )
    install_parser.add_argument(
        "--path",
        default=".",
        help="Project directory to install into (default: current directory)",
    )
    install_parser.add_argument(
        "--profile",
        help="Explicit Cursor profile to install (bypasses auto-detection)",
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
        help="Remove EKP-managed Cursor files from a consumer project",
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

    args = parser.parse_args(argv)

    if args.command == "version":
        print(get_version())
        print("resource_root: {}".format(get_ekp_root()))
        return 0

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

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
