"""Minimal EKP consumer CLI entry point (Phase W packaging smoke)."""

import argparse
import sys

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

    subparsers.add_parser("version", help="Show installed EKP version")

    args = parser.parse_args(argv)
    if args.command == "version":
        print(get_version())
        print("resource_root: {}".format(get_ekp_root()))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
