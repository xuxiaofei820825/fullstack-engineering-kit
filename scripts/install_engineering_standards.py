#!/usr/bin/env python3
"""Install the versioned engineering standards bundle into another project."""

from __future__ import annotations

import argparse
import json
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
TOOL_DIRECTORY = Path(".fullstack-engineering-kit")
INSTALLATION_FILE = TOOL_DIRECTORY / "installation.json"
SKILL_NAME = "full-stack-engineering-practices"
SKILL_SOURCE = Path(f".agents/skills/{SKILL_NAME}")
PLATFORM_SKILL_ROOTS = {
    "agents": Path(".agents/skills"),
    "codex": Path(".codex/skills"),
    "claude": Path(".claude/skills"),
}
MANAGED_PATHS = (
    SKILL_SOURCE,
    Path("openspec/schemas/engineering-governed"),
    Path("scripts/validate-engineering-standards.sh"),
    Path("scripts/validate_openspec_designs.py"),
    Path("scripts/tests/test_validate_openspec_designs.py"),
)
LEGACY_INSTALLED_TOOL_PATHS = MANAGED_PATHS[2:]
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


def skill_path(platform: str) -> Path:
    return PLATFORM_SKILL_ROOTS[platform] / SKILL_NAME


def managed_paths(platform: str) -> tuple[tuple[Path, Path], ...]:
    return (
        (SKILL_SOURCE, skill_path(platform)),
        (
            Path("openspec/schemas/engineering-governed"),
            Path("openspec/schemas/engineering-governed"),
        ),
        (
            Path("scripts/validate-engineering-standards.sh"),
            TOOL_DIRECTORY / "validate-engineering-standards.sh",
        ),
        (
            Path("scripts/validate_openspec_designs.py"),
            TOOL_DIRECTORY / "validate_openspec_designs.py",
        ),
        (
            Path("scripts/tests/test_validate_openspec_designs.py"),
            TOOL_DIRECTORY / "tests/test_validate_openspec_designs.py",
        ),
    )


def render_bytes(content: bytes, platform: str) -> bytes:
    return content.replace(
        SKILL_SOURCE.as_posix().encode(),
        skill_path(platform).as_posix().encode(),
    )


def same_rendered_content(source: Path, destination: Path, platform: str) -> bool:
    if source.is_file() != destination.is_file():
        return False
    source_files = comparable_files(source)
    destination_files = comparable_files(destination)
    if source_files.keys() != destination_files.keys():
        return False
    return all(
        render_bytes(source_files[relative].read_bytes(), platform)
        == destination_files[relative].read_bytes()
        for relative in source_files
    )


def rendered_config(current: str | None, default_config: str, platform: str) -> str:
    selected_skill_path = skill_path(platform).as_posix()
    default_config = default_config.replace(SKILL_SOURCE.as_posix(), selected_skill_path)
    if current is None:
        return default_config

    current = current.replace(SKILL_SOURCE.as_posix(), selected_skill_path)

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


def replace_managed_path(source: Path, destination: Path, platform: str) -> None:
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
        for staged_file in comparable_files(staged).values():
            rendered = render_bytes(staged_file.read_bytes(), platform)
            if rendered != staged_file.read_bytes():
                staged_file.write_bytes(rendered)
        if destination.exists():
            destination.rename(backup)
        staged.rename(destination)
    except Exception:
        if not destination.exists() and backup.exists():
            backup.rename(destination)
        raise
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def installation_metadata(platform: str, version: str) -> str:
    return json.dumps(
        {
            "platform": platform,
            "skillPath": skill_path(platform).as_posix(),
            "version": version,
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def remove_empty_parents(path: Path, stop: Path) -> None:
    parent = path.parent
    while parent != stop and parent != parent.parent:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def install(
    target: Path,
    update: bool,
    expected_version: str | None,
    dry_run: bool,
    platform: str = "agents",
) -> list[str]:
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
    for source_relative, destination_relative in managed_paths(platform):
        source = root / source_relative
        destination = target / destination_relative
        if not source.exists():
            raise InstallationError(f"规范套件缺少源文件：{source}")
        if destination.exists() and same_rendered_content(source, destination, platform):
            continue
        if destination.exists() and not update:
            conflicts.append(destination_relative)
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

    config_path = target / "openspec/config.yaml"
    default_config = (root / "openspec/config.yaml").read_text(encoding="utf-8")
    if config_path.exists():
        with config_path.open("r", encoding="utf-8", newline="") as handle:
            current_config = handle.read()
    else:
        current_config = None
    new_config = rendered_config(current_config, default_config, platform)

    metadata_path = target / INSTALLATION_FILE
    new_metadata = installation_metadata(platform, version)
    current_metadata = (
        metadata_path.read_text(encoding="utf-8") if metadata_path.is_file() else None
    )
    if current_metadata is not None and current_metadata != new_metadata and not update:
        conflicts.append(INSTALLATION_FILE)

    if conflicts:
        formatted = "\n".join(f"  - {path}" for path in conflicts)
        raise InstallationError(
            "以下已管理路径包含不同内容，未写入任何文件：\n"
            f"{formatted}\n如需升级，请检查差异后显式使用 --update。"
        )

    has_previous_installation = target_version.exists() or legacy_target_version.exists()
    legacy_tool_paths = [
        target / relative
        for relative in LEGACY_INSTALLED_TOOL_PATHS
        if update and has_previous_installation and (target / relative).exists()
    ]
    previous_platform: str | None = None
    if current_metadata is not None:
        try:
            recorded_platform = json.loads(current_metadata).get("platform")
        except (AttributeError, json.JSONDecodeError):
            recorded_platform = None
        if recorded_platform in PLATFORM_SKILL_ROOTS:
            previous_platform = recorded_platform
    elif has_previous_installation:
        previous_platform = "agents"
    previous_skill_path = skill_path(previous_platform) if previous_platform else None
    legacy_skill_paths: list[Path] = []
    if (
        update
        and previous_skill_path is not None
        and previous_skill_path != skill_path(platform)
        and (target / previous_skill_path).exists()
    ):
        legacy_skill_paths.append(target / previous_skill_path)

    changes = [str(destination.relative_to(target)) for _, destination in operations]
    if current_config != new_config:
        changes.append("openspec/config.yaml")
    if not target_version.exists() or target_version.read_text(encoding="utf-8").strip() != version:
        changes.append(VERSION_FILE)
    if legacy_target_version.exists():
        changes.append(f"{LEGACY_VERSION_FILE}（删除旧版标记）")
    if current_metadata != new_metadata:
        changes.append(str(INSTALLATION_FILE))
    if update:
        changes.extend(
            f"{path.relative_to(target)}（迁移旧版路径）"
            for path in (*legacy_tool_paths, *legacy_skill_paths)
        )

    if dry_run:
        return changes

    for source, destination in operations:
        replace_managed_path(source, destination, platform)
    if current_config != new_config:
        atomic_write(config_path, new_config)
    atomic_write(metadata_path, new_metadata)
    atomic_write(target_version, f"{version}\n")
    legacy_target_version.unlink(missing_ok=True)
    if update and target != root:
        for legacy_path in (*legacy_tool_paths, *legacy_skill_paths):
            if legacy_path.is_dir():
                shutil.rmtree(legacy_path)
            else:
                legacy_path.unlink()
            remove_empty_parents(legacy_path, target)
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="安装可复用的编码规范和 OpenSpec schema")
    parser.add_argument("target", type=Path, help="目标项目根目录")
    parser.add_argument("--update", action="store_true", help="替换内容不同的已管理文件")
    parser.add_argument("--version", help="要求当前检出版本与该版本完全一致")
    parser.add_argument("--dry-run", action="store_true", help="只显示将发生的变更")
    parser.add_argument(
        "--platform",
        choices=tuple(PLATFORM_SKILL_ROOTS),
        default="agents",
        help="Skill 目标平台（默认 agents；可选 codex 或 claude）",
    )
    args = parser.parse_args()

    try:
        changes = install(
            args.target.resolve(),
            args.update,
            args.version,
            args.dry_run,
            args.platform,
        )
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
