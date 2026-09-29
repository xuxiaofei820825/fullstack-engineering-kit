from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = REPOSITORY_ROOT / "scripts/build-release.sh"
BOOTSTRAP = REPOSITORY_ROOT / "scripts/bootstrap.sh"
VERSION = (REPOSITORY_ROOT / "VERSION").read_text(encoding="utf-8").strip()
ARCHIVE_NAME = f"fullstack-engineering-kit-{VERSION}.tar.gz"
CLI_ARCHIVE_NAME = f"fullstack-engineering-kit-cli-{VERSION}.tgz"


class ReleaseDistributionTest(unittest.TestCase):
    def build(self, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(BUILD_SCRIPT), str(output)],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_release_title_matches_the_version_tag(self) -> None:
        workflow = (REPOSITORY_ROOT / ".github/workflows/release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn('--title "v${version}"', workflow)
        self.assertNotIn('--title "Fullstack Engineering Kit ${version}"', workflow)

    def test_release_archive_is_deterministic_and_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            first_result = self.build(first)
            second_result = self.build(second)

            self.assertEqual(0, first_result.returncode, first_result.stderr)
            self.assertEqual(0, second_result.returncode, second_result.stderr)
            first_archive = first / ARCHIVE_NAME
            second_archive = second / ARCHIVE_NAME
            self.assertEqual(first_archive.read_bytes(), second_archive.read_bytes())
            first_cli_archive = first / CLI_ARCHIVE_NAME
            second_cli_archive = second / CLI_ARCHIVE_NAME
            self.assertEqual(first_cli_archive.read_bytes(), second_cli_archive.read_bytes())

            checksum_line = (first / f"{ARCHIVE_NAME}.sha256").read_text(encoding="utf-8")
            self.assertEqual(
                f"{hashlib.sha256(first_archive.read_bytes()).hexdigest()}  {ARCHIVE_NAME}\n",
                checksum_line,
            )
            cli_checksum_line = (first / f"{CLI_ARCHIVE_NAME}.sha256").read_text(
                encoding="utf-8"
            )
            self.assertEqual(
                f"{hashlib.sha256(first_cli_archive.read_bytes()).hexdigest()}  "
                f"{CLI_ARCHIVE_NAME}\n",
                cli_checksum_line,
            )
            self.assertEqual(
                (REPOSITORY_ROOT / "scripts/bootstrap.sh").read_bytes(),
                (first / "bootstrap.sh").read_bytes(),
            )
            with tarfile.open(first_archive, "r:gz") as archive:
                names = set(archive.getnames())
                prefix = f"fullstack-engineering-kit-{VERSION}"
                self.assertIn(f"{prefix}/VERSION", names)
                self.assertIn(f"{prefix}/scripts/install.sh", names)
                self.assertIn(
                    f"{prefix}/.agents/skills/full-stack-engineering-practices/SKILL.md",
                    names,
                )
                self.assertFalse(any("/.git/" in name for name in names))
            with tarfile.open(first_cli_archive, "r:gz") as archive:
                names = set(archive.getnames())
                self.assertIn("package/cli/fullstack-engineering-kit.mjs", names)
                self.assertIn(
                    "package/.agents/skills/full-stack-engineering-practices/SKILL.md",
                    names,
                )

    def test_bootstrap_downloads_verifies_and_installs_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_dir = root / "build"
            result = self.build(build_dir)
            self.assertEqual(0, result.returncode, result.stderr)

            package_dir = root / "release-assets"
            package_dir.mkdir(parents=True)
            shutil.copy2(build_dir / ARCHIVE_NAME, package_dir / ARCHIVE_NAME)
            shutil.copy2(
                build_dir / f"{ARCHIVE_NAME}.sha256",
                package_dir / f"{ARCHIVE_NAME}.sha256",
            )
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_curl = fake_bin / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env python3
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

arguments = sys.argv[1:]
output = Path(arguments[arguments.index('--output') + 1])
url = next(argument for argument in arguments if argument.startswith(('http://', 'https://')))
source = Path(os.environ['FAKE_CURL_PACKAGE_DIR']) / Path(urlparse(url).path).name
shutil.copyfile(source, output)
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)
            target = root / "target"
            target.mkdir()
            installed = subprocess.run(
                [
                    str(BOOTSTRAP),
                    "--version",
                    VERSION,
                    "--target",
                    str(target),
                    "--platform",
                    "codex",
                ],
                cwd=REPOSITORY_ROOT,
                env={
                    **os.environ,
                    "ENGINEERING_STANDARDS_GITHUB_REPOSITORY": "invalid",
                    "FAKE_CURL_PACKAGE_DIR": str(package_dir),
                    "FULLSTACK_ENGINEERING_KIT_GITHUB_REPOSITORY": (
                        "company/fullstack-engineering-kit"
                    ),
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                },
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, installed.returncode, installed.stderr)
            self.assertEqual(
                VERSION,
                (target / ".fullstack-engineering-kit-version")
                .read_text(encoding="utf-8")
                .strip(),
            )
            self.assertTrue(
                (target / ".codex/skills/full-stack-engineering-practices/SKILL.md").is_file()
            )
            self.assertFalse((target / "scripts").exists())

    def test_bootstrap_requires_an_explicit_version(self) -> None:
        result = subprocess.run(
            [str(BOOTSTRAP), "--repository", "company/fullstack-engineering-kit"],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("--version", result.stderr)

    def test_bootstrap_supports_private_releases_through_github_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = root / "release-assets"
            result = self.build(package_dir)
            self.assertEqual(0, result.returncode, result.stderr)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_gh = fake_bin / "gh"
            fake_gh.write_text(
                """#!/usr/bin/env python3
import os
import shutil
import sys
from pathlib import Path
arguments = sys.argv[1:]
asset = arguments[arguments.index('--pattern') + 1]
output = Path(arguments[arguments.index('--output') + 1])
shutil.copyfile(Path(os.environ['FAKE_GH_RELEASE_DIR']) / asset, output)
""",
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            target = root / "target"
            target.mkdir()

            installed = subprocess.run(
                [
                    str(BOOTSTRAP),
                    "--repository",
                    "company/fullstack-engineering-kit",
                    "--version",
                    VERSION,
                    "--target",
                    str(target),
                    "--use-gh",
                    "--dry-run",
                ],
                cwd=REPOSITORY_ROOT,
                env={
                    **os.environ,
                    "GH_TOKEN": "test-token",
                    "FAKE_GH_RELEASE_DIR": str(package_dir),
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                },
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, installed.returncode, installed.stderr)
            self.assertFalse((target / ".agents").exists())

    def test_bootstrap_rejects_a_package_with_wrong_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = root / "package"
            result = self.build(package_dir)
            self.assertEqual(0, result.returncode, result.stderr)
            (package_dir / f"{ARCHIVE_NAME}.sha256").write_text(
                f"{'0' * 64}  {ARCHIVE_NAME}\n", encoding="utf-8"
            )
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_curl = fake_bin / "curl"
            fake_curl.write_text(
                """#!/usr/bin/env python3
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse
arguments = sys.argv[1:]
output = Path(arguments[arguments.index('--output') + 1])
url = next(argument for argument in arguments if argument.startswith(('http://', 'https://')))
shutil.copyfile(Path(os.environ['FAKE_CURL_PACKAGE_DIR']) / Path(urlparse(url).path).name, output)
""",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)
            target = root / "target"
            target.mkdir()

            installed = subprocess.run(
                [
                    str(BOOTSTRAP),
                    "--version",
                    VERSION,
                    "--target",
                    str(target),
                ],
                cwd=REPOSITORY_ROOT,
                env={
                    **os.environ,
                    "ENGINEERING_STANDARDS_GITHUB_REPOSITORY": "company/fullstack-engineering-kit",
                    "FULLSTACK_ENGINEERING_KIT_GITHUB_REPOSITORY": "",
                    "FAKE_CURL_PACKAGE_DIR": str(package_dir),
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                },
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, installed.returncode)
            self.assertIn("SHA-256", installed.stderr)
            self.assertFalse((target / ".agents").exists())


if __name__ == "__main__":
    unittest.main()
