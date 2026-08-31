"""Minimal EKP consumer CLI entry point."""

import argparse
import sys

from ekp.detection.render import render_human, render_json
from ekp.detection.service import DetectionService
from ekp.paths import get_ekp_root
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

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
