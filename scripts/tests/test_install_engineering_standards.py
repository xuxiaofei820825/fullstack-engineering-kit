from __future__ import annotations

import json
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPOSITORY_ROOT / "scripts/install_engineering_standards.py"
VERIFIER = REPOSITORY_ROOT / "scripts/verify_engineering_standards.py"
BUNDLE_VERSION = (REPOSITORY_ROOT / "VERSION").read_text(encoding="utf-8").strip()


class InstallEngineeringStandardsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.target = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_script(self, script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", str(script), *arguments],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_installs_bundle_and_preserves_existing_config(self) -> None:
        config = self.target / "openspec/config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text(
            "schema: spec-driven\n\ncontext: |\n  Domain: example\n",
            encoding="utf-8",
        )
        config.chmod(0o640)

        result = self.run_script(INSTALLER, str(self.target), "--version", BUNDLE_VERSION)

        self.assertEqual(0, result.returncode, result.stderr)
        installed_config = config.read_text(encoding="utf-8")
        self.assertIn("schema: engineering-governed", installed_config)
        self.assertIn("Domain: example", installed_config)
        self.assertEqual(0o640, stat.S_IMODE(config.stat().st_mode))
        self.assertEqual(
            BUNDLE_VERSION,
            (self.target / ".fullstack-engineering-kit-version")
            .read_text(encoding="utf-8")
            .strip(),
        )
        validation_entrypoint = (
            self.target / ".fullstack-engineering-kit/validate-engineering-standards.sh"
        )
        self.assertTrue(validation_entrypoint.is_file())
        self.assertTrue(validation_entrypoint.stat().st_mode & 0o111)
        self.assertFalse((self.target / ".github").exists())
        self.assertFalse((self.target / "scripts").exists())
        verification = self.run_script(VERIFIER, str(self.target), "--files-only")
        self.assertEqual(0, verification.returncode, verification.stderr)

    def test_is_idempotent(self) -> None:
        first = self.run_script(INSTALLER, str(self.target))
        second = self.run_script(INSTALLER, str(self.target))

        self.assertEqual(0, first.returncode, first.stderr)
        self.assertIn(
            ".codex/skills/full-stack-engineering-practices",
            (self.target / "openspec/config.yaml").read_text(encoding="utf-8"),
        )
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertIn("already up to date", second.stdout)

    def test_installs_platform_specific_skill_without_touching_project_scripts(self) -> None:
        project_script = self.target / "scripts/validate-engineering-standards.sh"
        project_script.parent.mkdir(parents=True)
        project_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

        result = self.run_script(INSTALLER, str(self.target), "--platform", "codex")

        self.assertEqual(0, result.returncode, result.stderr)
        skill = self.target / ".codex/skills/full-stack-engineering-practices/SKILL.md"
        self.assertTrue(skill.is_file())
        self.assertFalse((self.target / ".agents").exists())
        self.assertEqual("#!/usr/bin/env bash\n", project_script.read_text(encoding="utf-8"))
        schema = self.target / "openspec/schemas/engineering-governed/schema.yaml"
        self.assertIn(".codex/skills/full-stack-engineering-practices", schema.read_text())
        verification = self.run_script(VERIFIER, str(self.target), "--files-only")
        self.assertEqual(0, verification.returncode, verification.stderr)

    def test_supports_claude_code_platform(self) -> None:
        result = self.run_script(
            INSTALLER,
            str(self.target),
            "--platform",
            "claude",
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(
            (self.target / ".claude/skills/full-stack-engineering-practices/SKILL.md").is_file()
        )

    def test_supports_opencode_platform(self) -> None:
        result = self.run_script(
            INSTALLER,
            str(self.target),
            "--platform",
            "opencode",
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(
            (self.target / ".opencode/skills/full-stack-engineering-practices/SKILL.md").is_file()
        )
        self.assertFalse((self.target / ".agents").exists())
        schema = self.target / "openspec/schemas/engineering-governed/schema.yaml"
        self.assertIn(".opencode/skills/full-stack-engineering-practices", schema.read_text())
        installed_validation_tests = self.run_script(
            self.target / ".fullstack-engineering-kit/tests/test_validate_openspec_designs.py"
        )
        self.assertEqual(
            0,
            installed_validation_tests.returncode,
            installed_validation_tests.stderr,
        )

    def test_update_migrates_legacy_managed_paths(self) -> None:
        installed = self.run_script(INSTALLER, str(self.target))
        self.assertEqual(0, installed.returncode, installed.stderr)
        codex_skill = self.target / ".codex/skills/full-stack-engineering-practices"
        legacy_skill = self.target / ".agents/skills/full-stack-engineering-practices"
        legacy_skill.parent.mkdir(parents=True)
        shutil.move(codex_skill, legacy_skill)
        metadata_path = self.target / ".fullstack-engineering-kit/installation.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["platform"] = "agents"
        metadata["skillPath"] = ".agents/skills/full-stack-engineering-practices"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        legacy_script = self.target / "scripts/validate-engineering-standards.sh"
        legacy_script.parent.mkdir(parents=True)
        legacy_script.write_text("legacy\n", encoding="utf-8")

        updated = self.run_script(
            INSTALLER,
            str(self.target),
            "--platform",
            "codex",
            "--update",
        )

        self.assertEqual(0, updated.returncode, updated.stderr)
        self.assertFalse((self.target / ".agents/skills/full-stack-engineering-practices").exists())
        self.assertFalse(legacy_script.exists())
        self.assertTrue(
            (self.target / ".codex/skills/full-stack-engineering-practices/SKILL.md").is_file()
        )

    def test_platform_switch_only_removes_the_previously_selected_skill(self) -> None:
        installed = self.run_script(INSTALLER, str(self.target), "--platform", "codex")
        self.assertEqual(0, installed.returncode, installed.stderr)
        unrelated_skill = self.target / ".agents/skills/full-stack-engineering-practices/SKILL.md"
        unrelated_skill.parent.mkdir(parents=True)
        unrelated_skill.write_text("user managed\n", encoding="utf-8")

        switched = self.run_script(
            INSTALLER,
            str(self.target),
            "--platform",
            "claude",
            "--update",
        )

        self.assertEqual(0, switched.returncode, switched.stderr)
        self.assertFalse(
            (self.target / ".codex/skills/full-stack-engineering-practices").exists()
        )
        self.assertEqual("user managed\n", unrelated_skill.read_text(encoding="utf-8"))

    def test_update_migrates_legacy_version_file(self) -> None:
        legacy_version = self.target / ".engineering-standards-version"
        legacy_version.write_text("1.0.4\n", encoding="utf-8")

        refused = self.run_script(INSTALLER, str(self.target))

        self.assertEqual(2, refused.returncode)
        self.assertIn(".engineering-standards-version", refused.stderr)
        self.assertTrue(legacy_version.exists())
        self.assertFalse((self.target / ".fullstack-engineering-kit-version").exists())

        legacy_verification = self.run_script(VERIFIER, str(self.target), "--files-only")
        self.assertEqual(1, legacy_verification.returncode)
        self.assertIn("Legacy marker", legacy_verification.stderr)

        updated = self.run_script(INSTALLER, str(self.target), "--update")

        self.assertEqual(0, updated.returncode, updated.stderr)
        self.assertFalse(legacy_version.exists())
        self.assertEqual(
            BUNDLE_VERSION,
            (self.target / ".fullstack-engineering-kit-version")
            .read_text(encoding="utf-8")
            .strip(),
        )

    def test_conflict_requires_explicit_update(self) -> None:
        installed = self.run_script(INSTALLER, str(self.target))
        self.assertEqual(0, installed.returncode, installed.stderr)
        template = (
            self.target / "openspec/schemas/engineering-governed/templates/design.md"
        )
        template.write_text(template.read_text(encoding="utf-8") + "\nlocal edit\n", encoding="utf-8")

        refused = self.run_script(INSTALLER, str(self.target))

        self.assertEqual(2, refused.returncode)
        self.assertIn("no files were written", refused.stderr)
        self.assertIn("local edit", template.read_text(encoding="utf-8"))

        updated = self.run_script(INSTALLER, str(self.target), "--update")
        self.assertEqual(0, updated.returncode, updated.stderr)
        self.assertNotIn("local edit", template.read_text(encoding="utf-8"))

    def test_version_mismatch_and_dry_run_do_not_write(self) -> None:
        mismatch = self.run_script(INSTALLER, str(self.target), "--version", "9.9.9")
        self.assertEqual(2, mismatch.returncode)
        self.assertFalse((self.target / ".agents").exists())

        dry_run = self.run_script(INSTALLER, str(self.target), "--dry-run")
        self.assertEqual(0, dry_run.returncode, dry_run.stderr)
        self.assertFalse((self.target / ".agents").exists())
        self.assertFalse((self.target / "openspec/config.yaml").exists())

    def test_ambiguous_config_is_rejected_before_writes(self) -> None:
        config = self.target / "openspec/config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("schema: first\nschema: second\n", encoding="utf-8")

        result = self.run_script(INSTALLER, str(self.target))

        self.assertEqual(2, result.returncode)
        self.assertIn("multiple top-level schema", result.stderr)
        self.assertFalse((self.target / ".agents").exists())

    def test_preserves_crlf_and_yaml_document_marker(self) -> None:
        config = self.target / "openspec/config.yaml"
        config.parent.mkdir(parents=True)
        config.write_bytes(b"---\r\nschema: spec-driven\r\ncontext: value\r\n")

        result = self.run_script(INSTALLER, str(self.target))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            b"---\r\nschema: engineering-governed\r\ncontext: value\r\n",
            config.read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
