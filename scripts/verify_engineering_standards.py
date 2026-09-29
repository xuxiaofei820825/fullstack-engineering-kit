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
        return requested or "agents", [f"缺少安装元数据：{INSTALLATION_FILE}"]
    try:
        content = json.loads(metadata.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        return requested or "agents", [f"安装元数据无效：{error}"]
    if not isinstance(content, dict):
        return requested or "agents", ["安装元数据必须是 JSON 对象"]
    platform = content.get("platform")
    if platform not in PLATFORM_SKILL_ROOTS:
        return requested or "agents", [f"安装元数据包含未知平台：{platform!r}"]
    if requested is not None and requested != platform:
        return requested, [
            f"请求验证平台 {requested}，但安装元数据记录的平台是 {platform}"
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
        errors.append(f"安装元数据与版本 {expected_version} 或平台不一致：{INSTALLATION_FILE}")
    installed_version = target / VERSION_FILE
    legacy_installed_version = target / LEGACY_VERSION_FILE
    if not installed_version.is_file():
        if legacy_installed_version.is_file():
            errors.append(
                f"检测到旧版标记 {LEGACY_VERSION_FILE}，请使用安装器的 --update 完成迁移"
            )
        else:
            errors.append(f"缺少 {VERSION_FILE}")
    elif installed_version.read_text(encoding="utf-8").strip() != expected_version:
        errors.append(
            f"安装版本不是 {expected_version}："
            f"{installed_version.read_text(encoding='utf-8').strip()}"
        )
    elif legacy_installed_version.exists():
        errors.append(f"仍残留旧版标记 {LEGACY_VERSION_FILE}，请使用安装器的 --update 清理")

    for source_relative, destination_relative in managed_paths(selected_platform):
        source = root / source_relative
        destination = target / destination_relative
        if not destination.exists():
            errors.append(f"缺少已管理路径：{destination_relative}")
        elif not same_rendered_content(source, destination, selected_platform):
            errors.append(
                f"已管理路径与版本 {expected_version} 不一致：{destination_relative}"
            )

    config = target / "openspec/config.yaml"
    if not config.is_file():
        errors.append("缺少 openspec/config.yaml")
    else:
        schema_lines = re.findall(
            r"(?m)^schema\s*:\s*([^#\r\n]+)", config.read_text(encoding="utf-8")
        )
        if len(schema_lines) != 1 or schema_lines[0].strip() != "engineering-governed":
            errors.append("openspec/config.yaml 未唯一指定 schema: engineering-governed")

    if errors or not run_commands:
        return errors

    if shutil.which("openspec") is None:
        errors.append("找不到 openspec 命令，未执行 schema 和产物校验")
        return errors

    commands = (
        ["openspec", "schema", "validate", "engineering-governed"],
        ["openspec", "validate", "--all", "--strict", "--no-interactive"],
        [sys.executable, "-B", ".fullstack-engineering-kit/validate_openspec_designs.py"],
    )
    for command in commands:
        if not run(command, target):
            errors.append(f"命令执行失败：{' '.join(command)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="验证编码规范套件安装")
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--files-only", action="store_true", help="只检查文件和配置")
    parser.add_argument(
        "--platform",
        choices=tuple(PLATFORM_SKILL_ROOTS),
        help="覆盖安装元数据中的目标平台",
    )
    args = parser.parse_args()
    target = args.target.resolve()
    if not target.is_dir():
        print(f"ERROR: 目标项目目录不存在：{target}", file=sys.stderr)
        return 2

    errors = verify(target, run_commands=not args.files_only, platform=args.platform)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"规范套件安装验证通过：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
