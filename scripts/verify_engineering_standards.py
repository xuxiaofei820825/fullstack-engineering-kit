#!/usr/bin/env python3
"""Verify an engineering standards installation and its OpenSpec integration."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from install_engineering_standards import (
    MANAGED_PATHS,
    VERSION_FILE,
    bundle_version,
    same_content,
    source_root,
)


def run(command: list[str], target: Path) -> bool:
    result = subprocess.run(command, cwd=target, check=False)
    return result.returncode == 0


def verify(target: Path, run_commands: bool = True) -> list[str]:
    root = source_root()
    errors: list[str] = []
    expected_version = bundle_version(root)
    installed_version = target / VERSION_FILE
    if not installed_version.is_file():
        errors.append(f"缺少 {VERSION_FILE}")
    elif installed_version.read_text(encoding="utf-8").strip() != expected_version:
        errors.append(
            f"安装版本不是 {expected_version}："
            f"{installed_version.read_text(encoding='utf-8').strip()}"
        )

    for relative in MANAGED_PATHS:
        source = root / relative
        destination = target / relative
        if not destination.exists():
            errors.append(f"缺少已管理路径：{relative}")
        elif not same_content(source, destination):
            errors.append(f"已管理路径与版本 {expected_version} 不一致：{relative}")

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
        [sys.executable, "-B", "scripts/validate_openspec_designs.py"],
    )
    for command in commands:
        if not run(command, target):
            errors.append(f"命令执行失败：{' '.join(command)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="验证编码规范套件安装")
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--files-only", action="store_true", help="只检查文件和配置")
    args = parser.parse_args()
    target = args.target.resolve()
    if not target.is_dir():
        print(f"ERROR: 目标项目目录不存在：{target}", file=sys.stderr)
        return 2

    errors = verify(target, run_commands=not args.files_only)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"规范套件安装验证通过：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
