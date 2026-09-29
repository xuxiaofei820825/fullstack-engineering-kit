#!/usr/bin/env python3
"""Build the installable npm CLI tarball for a GitHub Release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from install_engineering_standards import InstallationError, bundle_version, source_root


PACKAGE_FILENAME = "fullstack-engineering-kit-cli-{version}.tgz"


def build(output_dir: Path) -> tuple[Path, Path]:
    root = source_root()
    version = bundle_version(root)
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    if package.get("version") != version:
        raise InstallationError(
            f"package.json 版本 {package.get('version')!r} 与 VERSION {version!r} 不一致"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fullstack-engineering-kit-npm-") as cache:
        environment = {**os.environ, "npm_config_cache": cache}
        result = subprocess.run(
            ["npm", "pack", "--json", "--pack-destination", str(output_dir)],
            cwd=root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        raise InstallationError(f"npm CLI 包构建失败：\n{result.stderr.strip()}")
    try:
        npm_output = json.loads(result.stdout)
        generated = output_dir / npm_output[0]["filename"]
    except (IndexError, KeyError, json.JSONDecodeError) as error:
        raise InstallationError(f"无法解析 npm pack 输出：{error}") from error

    archive = output_dir / PACKAGE_FILENAME.format(version=version)
    if archive.exists():
        archive.unlink()
    generated.replace(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = archive.with_name(f"{archive.name}.sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive, checksum


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 Fullstack Engineering Kit npm CLI 包")
    parser.add_argument(
        "output_dir",
        nargs="?",
        type=Path,
        default=Path("dist"),
        help="产物目录，默认 dist",
    )
    args = parser.parse_args()
    try:
        archive, checksum = build(args.output_dir.resolve())
    except (InstallationError, OSError) as error:
        parser.error(str(error))
    print(archive)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
