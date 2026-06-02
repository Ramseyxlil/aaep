#!/usr/bin/env python3
"""
build_addon.py — Package this directory as a .nvda-addon archive.

A .nvda-addon file is a renamed ZIP archive containing:
- manifest.ini at the root
- An appropriately structured set of Python modules

This script reads manifest.ini, validates that required files exist,
and produces aaep-subscriber-VERSION.nvda-addon for NVDA installation.

Usage:
    python build_addon.py [--output FILE] [--verbose]
"""

from __future__ import annotations

import argparse
import configparser
import sys
import zipfile
from pathlib import Path


def parse_manifest(manifest_path: Path) -> dict[str, str]:
    """Read NVDA add-on manifest.ini into a flat dict."""
    parser = configparser.ConfigParser()
    text = manifest_path.read_text(encoding="utf-8")
    # NVDA manifests don't use [section] headers; configparser needs one
    parser.read_string("[manifest]\n" + text)
    return {key: parser.get("manifest", key).strip('"')
            for key in parser["manifest"]}


def collect_files(root: Path) -> list[tuple[Path, str]]:
    """
    Collect files to include in the add-on.

    Returns a list of (source_path, archive_path) tuples.
    """
    includes: list[tuple[Path, str]] = []

    # manifest.ini at the archive root
    includes.append((root / "manifest.ini", "manifest.ini"))

    # The aaep_nvda_subscriber package as a globalPlugin
    package_dir = root / "aaep_nvda_subscriber"
    if not package_dir.is_dir():
        raise FileNotFoundError(f"Package directory not found: {package_dir}")

    # NVDA expects globalPlugins/<plugin_name>.py or globalPlugins/<plugin_pkg>/...
    # We register globalPlugin.py as the entry point.
    for source in package_dir.iterdir():
        if source.is_file() and source.suffix == ".py":
            if source.name == "globalPlugin.py":
                # NVDA's globalPlugins loader will see this as aaepSubscriber
                archive_path = "globalPlugins/aaepSubscriber.py"
            else:
                # Supporting modules live in a subpackage
                archive_path = f"globalPlugins/aaep_nvda_subscriber/{source.name}"
            includes.append((source, archive_path))

    return includes


def validate_includes(includes: list[tuple[Path, str]]) -> None:
    """Check that all required files exist and are readable."""
    required = ["manifest.ini", "globalPlugins/aaepSubscriber.py"]
    archive_paths = {ap for _, ap in includes}
    missing = [r for r in required if r not in archive_paths]
    if missing:
        raise FileNotFoundError(f"Required files missing from archive: {missing}")
    for source, _ in includes:
        if not source.is_file():
            raise FileNotFoundError(f"Source file not found: {source}")


def build(root: Path, output: Path, *, verbose: bool = False) -> Path:
    """Build the .nvda-addon archive and return its path."""
    manifest = parse_manifest(root / "manifest.ini")
    name = manifest.get("name", "aaep-subscriber")
    version = manifest.get("version", "0.0.0")

    if output.is_dir() or str(output).endswith("/"):
        output = output / f"{name}-{version}.nvda-addon"

    includes = collect_files(root)
    validate_includes(includes)

    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for source, archive_path in includes:
            if verbose:
                print(f"  {archive_path} <- {source}")
            zf.write(source, archive_path)

    print(f"Created {output}")
    print(f"  Add-on name: {name}")
    print(f"  Version: {version}")
    print(f"  Files: {len(includes)}")
    print(f"  Size: {output.stat().st_size:,} bytes")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_addon.py",
        description="Package the NVDA add-on prototype as a .nvda-addon archive",
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=Path("."),
        help="Output file or directory (default: current directory)",
    )
    parser.add_argument(
        "--root", "-r", type=Path, default=Path(__file__).resolve().parent,
        help="Root of the source directory (default: this script's directory)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show every file being added",
    )

    args = parser.parse_args(argv)

    try:
        build(args.root, args.output, verbose=args.verbose)
        return 0
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"build_addon: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
