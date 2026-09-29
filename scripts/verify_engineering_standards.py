#!/usr/bin/env python3
"""Verify an engineering standards installation and its OpenSpec integration."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from install_engineering_standards import (
    INSTALLATION_FILE,
    LEGACY_VERSION_FILE,
    PLATFORM_SKILL_ROOTS,
    VERSION_FILE,
    bundle_version,
    installation_metadata,
    managed_paths,
    same_rendered_content,
    source_root,
)


def run(command: list[str], target: Path) -> bool:
    result = subprocess.run(command, cwd=target, check=False)
    return result.returncode == 0


def installed_platform(target: Path, requested: str | None) -> tuple[str, list[str]]:
    metadata = target / INSTALLATION_FILE
    if not metadata.is_file():
        return requested or "codex", [f"Missing installation metadata: {INSTALLATION_FILE}"]
    try:
        content = json.loads(metadata.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        return requested or "codex", [f"Invalid installation metadata: {error}"]
    if not isinstance(content, dict):
        return requested or "codex", ["Installation metadata must be a JSON object"]
    platform = content.get("platform")
    if platform not in PLATFORM_SKILL_ROOTS:
        return requested or "codex", [f"Installation metadata contains an unknown platform: {platform!r}"]
    if requested is not None and requested != platform:
        return requested, [
            f"Requested platform {requested}, but installation metadata records {platform}"
        ]
    return platform, []


def verify(
    target: Path,
    run_commands: bool = True,
    platform: str | None = None,
) -> list[str]:
    root = source_root()
    selected_platform, errors = installed_platform(target, platform)
    expected_version = bundle_version(root)
    metadata = target / INSTALLATION_FILE
    if metadata.is_file() and metadata.read_text(encoding="utf-8") != installation_metadata(
        selected_platform, expected_version
    ):
        errors.append(f"Installation metadata does not match version {expected_version} or the platform: {INSTALLATION_FILE}")
    installed_version = target / VERSION_FILE
    legacy_installed_version = target / LEGACY_VERSION_FILE
    if not installed_version.is_file():
        if legacy_installed_version.is_file():
            errors.append(
                f"Legacy marker {LEGACY_VERSION_FILE} detected; use installer --update to migrate"
            )
        else:
            errors.append(f"Missing {VERSION_FILE}")
    elif installed_version.read_text(encoding="utf-8").strip() != expected_version:
        errors.append(
            f"Installed version is not {expected_version}: "
            f"{installed_version.read_text(encoding='utf-8').strip()}"
        )
    elif legacy_installed_version.exists():
        errors.append(f"Legacy marker {LEGACY_VERSION_FILE} remains; use installer --update to remove it")

    for source_relative, destination_relative in managed_paths(selected_platform):
        source = root / source_relative
        destination = target / destination_relative
        if not destination.exists():
            errors.append(f"Missing managed path: {destination_relative}")
        elif not same_rendered_content(source, destination, selected_platform):
            errors.append(
                f"Managed path does not match version {expected_version}: {destination_relative}"
            )

    config = target / "openspec/config.yaml"
    if not config.is_file():
        errors.append("Missing openspec/config.yaml")
    else:
        schema_lines = re.findall(
            r"(?m)^schema\s*:\s*([^#\r\n]+)", config.read_text(encoding="utf-8")
        )
        if len(schema_lines) != 1 or schema_lines[0].strip() != "engineering-governed":
            errors.append("openspec/config.yaml does not specify exactly one schema: engineering-governed")

    if errors or not run_commands:
        return errors

    if shutil.which("openspec") is None:
        errors.append("The openspec command was not found; schema and artifact verification was skipped")
        return errors

    commands = (
        ["openspec", "schema", "validate", "engineering-governed"],
        ["openspec", "validate", "--changes", "--strict", "--no-interactive"],
        [sys.executable, "-B", ".fullstack-engineering-kit/validate_openspec_designs.py"],
    )
    for command in commands:
        if not run(command, target):
            errors.append(f"Command failed: {' '.join(command)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the engineering kit installation")
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--files-only", action="store_true", help="check files and configuration only")
    parser.add_argument(
        "--platform",
        choices=tuple(PLATFORM_SKILL_ROOTS),
        help="override the target platform recorded in installation metadata",
    )
    args = parser.parse_args()
    target = args.target.resolve()
    if not target.is_dir():
        print(f"ERROR: Target project directory does not exist: {target}", file=sys.stderr)
        return 2

    errors = verify(target, run_commands=not args.files_only, platform=args.platform)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"Engineering kit installation verified: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
