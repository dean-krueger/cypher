"""Command-line interface for Cypher discovery."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .catalog import Catalog, cache_file
from .discovery import compatibility_report, discover
from .errors import CypherError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cypher", description="Python input authoring tools for Cyclus."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    discover_parser = subparsers.add_parser(
        "discover", help="discover installed Cyclus archetypes"
    )
    discover_parser.add_argument(
        "--cyclus", help="path to the Cyclus executable to inspect"
    )
    discover_parser.add_argument(
        "--cache", type=Path, help="override the normalized metadata cache path"
    )
    discover_parser.add_argument(
        "--strict",
        action="store_true",
        help="fail if any discovered schema uses unsupported constructs",
    )
    report_parser = subparsers.add_parser(
        "compatibility", help="show the cached discovery compatibility report"
    )
    report_parser.add_argument(
        "--cache", type=Path, help="override the normalized metadata cache path"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "discover":
            result = discover(
                executable=arguments.cyclus,
                cache_path=arguments.cache,
                strict=arguments.strict,
            )
            print(compatibility_report(result.catalog))
            print(f"Cache: {result.cache_path}")
            stub_location = result.stub_paths[0].parent if result.stub_paths else "none"
            print(f"Type stubs: {stub_location}")
            return 0
        if arguments.command == "compatibility":
            catalog = Catalog.load(arguments.cache or cache_file())
            print(compatibility_report(catalog))
            return 0
    except CypherError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    parser.error(f"unknown command: {arguments.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
