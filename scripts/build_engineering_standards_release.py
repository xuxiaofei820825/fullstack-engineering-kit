#!/usr/bin/env python3
"""Build deterministic engineering standards assets for a GitHub Release."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

from install_engineering_standards import MANAGED_PATHS, bundle_version, source_root


PACKAGE_NAME = "fullstack-engineering-kit"
PACKAGE_PATHS = (
    Path("VERSION"),
    Path("README.md"),
    Path("openspec/config.yaml"),
    Path("scripts/install.sh"),
    Path("scripts/install_engineering_standards.py"),
    Path("scripts/verify-installation.sh"),
    Path("scripts/verify_engineering_standards.py"),
    *MANAGED_PATHS,
)
IGNORED_NAMES = {"__pycache__", ".DS_Store"}


def package_files(root: Path) -> list[Path]:
    files: set[Path] = set()
    for relative in PACKAGE_PATHS:
        source = root / relative
        if not source.exists():
            raise FileNotFoundError(f"Release package is missing a required path: {relative}")
        if source.is_file():
            files.add(relative)
            continue
        for path in source.rglob("*"):
            if path.is_file() and not any(part in IGNORED_NAMES for part in path.parts):
                files.add(path.relative_to(root))
    return sorted(files)


def add_file(archive: tarfile.TarFile, root: Path, relative: Path, prefix: str) -> None:
    source = root / relative
    info = archive.gettarinfo(str(source), arcname=f"{prefix}/{relative.as_posix()}")
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    with source.open("rb") as handle:
        archive.addfile(info, handle)


def build(output_dir: Path) -> tuple[Path, Path, Path]:
    root = source_root()
    version = bundle_version(root)
    prefix = f"{PACKAGE_NAME}-{version}"
    filename = f"{prefix}.tar.gz"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / filename

    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{filename}.", dir=output_dir)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as archive:
                    for relative in package_files(root):
                        add_file(archive, root, relative, prefix)
        os.replace(temporary, archive_path)
    finally:
        temporary.unlink(missing_ok=True)

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path = output_dir / f"{filename}.sha256"
    checksum_path.write_text(f"{digest}  {filename}\n", encoding="utf-8")
    bootstrap_path = output_dir / "bootstrap.sh"
    shutil.copy2(root / "scripts/bootstrap.sh", bootstrap_path)
    return archive_path, checksum_path, bootstrap_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the engineering kit GitHub Release assets")
    parser.add_argument(
        "output_dir",
        nargs="?",
        type=Path,
        default=Path("dist"),
        help="output directory (default: dist)",
    )
    args = parser.parse_args()
    archive, checksum, bootstrap = build(args.output_dir.resolve())
    print(archive)
    print(checksum)
    print(bootstrap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
