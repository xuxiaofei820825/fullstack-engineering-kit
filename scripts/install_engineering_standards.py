#!/usr/bin/env python3
"""Install the versioned engineering standards bundle into another project."""

from __future__ import annotations

import argparse
import filecmp
import os
import re
import shutil
import stat
import sys
import tempfile
from pathlib import Path


SCHEMA_NAME = "engineering-governed"
VERSION_FILE = ".fullstack-engineering-kit-version"
LEGACY_VERSION_FILE = ".engineering-standards-version"
MANAGED_PATHS = (
    Path(".agents/skills/full-stack-engineering-practices"),
    Path("openspec/schemas/engineering-governed"),
    Path("scripts/validate-engineering-standards.sh"),
    Path("scripts/validate_openspec_designs.py"),
    Path("scripts/tests/test_validate_openspec_designs.py"),
)
IGNORED_NAMES = {"__pycache__", ".DS_Store"}


class InstallationError(RuntimeError):
    pass


def source_root() -> Path:
    return Path(__file__).resolve().parent.parent


def bundle_version(root: Path) -> str:
    path = root / "VERSION"
    if not path.is_file():
        raise InstallationError(f"缺少版本文件：{path}")
    version = path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise InstallationError(f"VERSION 不是有效语义版本：{version!r}")
    return version


def comparable_files(root: Path) -> dict[Path, Path]:
    if root.is_file():
        return {Path(root.name): root}
    files: dict[Path, Path] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in IGNORED_NAMES for part in path.parts):
            continue
        files[path.relative_to(root)] = path
    return files


def same_content(source: Path, destination: Path) -> bool:
    if source.is_file() != destination.is_file():
        return False
    source_files = comparable_files(source)
    destination_files = comparable_files(destination)
    if source_files.keys() != destination_files.keys():
        return False
    return all(
        filecmp.cmp(source_files[relative], destination_files[relative], shallow=False)
        for relative in source_files
    )


def rendered_config(current: str | None, default_config: str) -> str:
    if current is None:
        return default_config

    lines = current.splitlines(keepends=True)
    schema_indexes = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^(?:[\"']schema[\"']|schema)\s*:", line)
    ]
    if len(schema_indexes) > 1:
        raise InstallationError("openspec/config.yaml 包含多个顶层 schema，无法安全更新")
    if schema_indexes:
        index = schema_indexes[0]
        newline = "\r\n" if lines[index].endswith("\r\n") else "\n"
        lines[index] = f"schema: {SCHEMA_NAME}{newline}"
    else:
        insert_at = 1 if lines and lines[0].strip() == "---" else 0
        lines.insert(insert_at, f"schema: {SCHEMA_NAME}\n\n")
    return "".join(lines)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def replace_managed_path(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=".fullstack-engineering-kit-", dir=destination.parent)
    )
    staged = staging_root / destination.name
    backup = staging_root / "previous"
    try:
        if source.is_dir():
            shutil.copytree(source, staged, ignore=shutil.ignore_patterns(*IGNORED_NAMES))
        else:
            shutil.copy2(source, staged)
        if destination.exists():
            destination.rename(backup)
        staged.rename(destination)
    except Exception:
        if not destination.exists() and backup.exists():
            backup.rename(destination)
        raise
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def install(target: Path, update: bool, expected_version: str | None, dry_run: bool) -> list[str]:
    root = source_root()
    version = bundle_version(root)
    if expected_version and expected_version != version:
        raise InstallationError(
            f"请求安装 {expected_version}，当前检出的规范套件版本是 {version}"
        )
    if not target.is_dir():
        raise InstallationError(f"目标项目目录不存在：{target}")

    operations: list[tuple[Path, Path]] = []
    conflicts: list[Path] = []
    for relative in MANAGED_PATHS:
        source = root / relative
        destination = target / relative
        if not source.exists():
            raise InstallationError(f"规范套件缺少源文件：{source}")
        if destination.exists() and same_content(source, destination):
            continue
        if destination.exists() and not update:
            conflicts.append(relative)
            continue
        operations.append((source, destination))

    target_version = target / VERSION_FILE
    legacy_target_version = target / LEGACY_VERSION_FILE
    if target_version.exists() and target_version.read_text(encoding="utf-8").strip() != version:
        if not update:
            conflicts.append(Path(VERSION_FILE))
    elif (
        not target_version.exists()
        and legacy_target_version.exists()
        and legacy_target_version.read_text(encoding="utf-8").strip() != version
        and not update
    ):
        conflicts.append(Path(LEGACY_VERSION_FILE))

    if conflicts:
        formatted = "\n".join(f"  - {path}" for path in conflicts)
        raise InstallationError(
            "以下已管理路径包含不同内容，未写入任何文件：\n"
            f"{formatted}\n如需升级，请检查差异后显式使用 --update。"
        )

    config_path = target / "openspec/config.yaml"
    default_config = (root / "openspec/config.yaml").read_text(encoding="utf-8")
    if config_path.exists():
        with config_path.open("r", encoding="utf-8", newline="") as handle:
            current_config = handle.read()
    else:
        current_config = None
    new_config = rendered_config(current_config, default_config)

    changes = [str(destination.relative_to(target)) for _, destination in operations]
    if current_config != new_config:
        changes.append("openspec/config.yaml")
    if not target_version.exists() or target_version.read_text(encoding="utf-8").strip() != version:
        changes.append(VERSION_FILE)
    if legacy_target_version.exists():
        changes.append(f"{LEGACY_VERSION_FILE}（删除旧版标记）")

    if dry_run:
        return changes

    for source, destination in operations:
        replace_managed_path(source, destination)
    if current_config != new_config:
        atomic_write(config_path, new_config)
    atomic_write(target_version, f"{version}\n")
    legacy_target_version.unlink(missing_ok=True)
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="安装可复用的编码规范和 OpenSpec schema")
    parser.add_argument("target", type=Path, help="目标项目根目录")
    parser.add_argument("--update", action="store_true", help="替换内容不同的已管理文件")
    parser.add_argument("--version", help="要求当前检出版本与该版本完全一致")
    parser.add_argument("--dry-run", action="store_true", help="只显示将发生的变更")
    args = parser.parse_args()

    try:
        changes = install(args.target.resolve(), args.update, args.version, args.dry_run)
    except InstallationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    prefix = "将更新" if args.dry_run else "已更新"
    if changes:
        print(f"{prefix} {len(changes)} 个路径：")
        for path in changes:
            print(f"  - {path}")
    else:
        print("规范套件已经是当前版本，无需更新。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
