#!/usr/bin/env python3
"""Validate coding-standard traceability in active OpenSpec designs."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_SUBSECTIONS = (
    "变更范围",
    "已加载规范",
    "规范落实",
    "不适用项",
    "规范偏离",
)
SUBSECTION_LABELS = {
    "变更范围": "change scope",
    "已加载规范": "loaded standards",
    "规范落实": "standards implementation",
    "不适用项": "not-applicable items",
    "规范偏离": "standards deviations",
}
SKILL_PATH = ".agents/skills/full-stack-engineering-practices"
REFERENCE_PATTERN = re.compile(
    rf"(?:`)?({re.escape(SKILL_PATH)}/references/[A-Za-z0-9_./-]+\.md)(?:`)?"
)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
OLD_CHAPTER_PATTERN = re.compile(r"第\s*\d+(?:\.\d+)*(?:\s*[-–—]\s*\d+(?:\.\d+)*)?\s*[章节]")


def extract_section(text: str, level: int, title: str) -> str | None:
    marker = "#" * level
    match = re.search(
        rf"(?m)^{re.escape(marker)}\s+{re.escape(title)}\s*$",
        text,
    )
    if not match:
        return None
    following_heading = re.search(
        rf"(?m)^#{{1,{level}}}\s+",
        text[match.end() :],
    )
    end = match.end() + following_heading.start() if following_heading else len(text)
    return text[match.end() : end].strip()


def meaningful_content(content: str) -> str:
    return HTML_COMMENT_PATTERN.sub("", content).strip()


def table_data_rows(content: str, column_count: int) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped[1:-1].split("|")]
        if len(cells) != column_count:
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def validate_design(path: Path, project_root: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    standards_section = extract_section(text, 2, "编码规范适用性")
    if standards_section is None:
        return ["Missing the required level-2 standards applicability section"]

    if "<!--" in standards_section or "-->" in standards_section:
        errors.append("The standards applicability section still contains template placeholders")

    subsection_content: dict[str, str] = {}
    for title in REQUIRED_SUBSECTIONS:
        content = extract_section(standards_section, 3, title)
        if content is None:
            errors.append(f"Missing level-3 section for {SUBSECTION_LABELS[title]}")
            continue
        cleaned = meaningful_content(content)
        subsection_content[title] = cleaned
        if not cleaned:
            errors.append(f"The {SUBSECTION_LABELS[title]} section has no content")

    loaded_content = subsection_content.get("已加载规范", "")
    references = sorted(set(REFERENCE_PATTERN.findall(loaded_content)))
    if not references:
        errors.append("The loaded standards section does not reference any full-stack-engineering-practices file")
    for reference in references:
        if not (project_root / reference).is_file():
            errors.append(f"Referenced standards file does not exist: {reference}")

    loaded_rows = table_data_rows(loaded_content, 3)
    if not loaded_rows or any(not all(row) for row in loaded_rows):
        errors.append("The loaded standards section must contain at least one mapping row with three non-empty columns")
    for row in loaded_rows:
        reference_cell = row[0]
        if not REFERENCE_PATTERN.fullmatch(reference_cell):
            errors.append(f"Invalid reference path in the loaded standards section: {reference_cell}")

    implementation_rows = table_data_rows(subsection_content.get("规范落实", ""), 3)
    if not implementation_rows or any(not all(row) for row in implementation_rows):
        errors.append("The standards implementation section must contain at least one three-column mapping for constraint, design decision, and verification")

    if re.search(r"coding-standards\.md", standards_section, re.IGNORECASE):
        errors.append("Standards mappings must not reference the original coding-standards.md")
    if OLD_CHAPTER_PATTERN.search(standards_section):
        errors.append("Standards mappings must not use chapter numbers from the original document")
    if "遵循编码规范" in standards_section:
        errors.append("Do not replace a standards mapping with a generic compliance statement")

    deviation = subsection_content.get("规范偏离", "").strip().rstrip("。")
    if deviation and deviation != "无":
        for keyword, label in (
            ("风险", "risk"),
            ("替代措施", "mitigation"),
            ("审批", "approval"),
        ):
            if keyword not in deviation:
                errors.append(f"Standards deviations must describe {label}")

    return errors


def discover_designs(project_root: Path) -> list[Path]:
    changes_root = project_root / "openspec" / "changes"
    if not changes_root.is_dir():
        return []
    return sorted(
        entry / "design.md"
        for entry in changes_root.iterdir()
        if entry.is_dir()
        and entry.name != "archive"
        and not entry.name.startswith(".")
        and (entry / "design.md").is_file()
    )


def is_archived_design(path: Path, project_root: Path) -> bool:
    archive_root = (project_root / "openspec" / "changes" / "archive").resolve()
    return path.resolve().is_relative_to(archive_root)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate engineering standards mappings in active OpenSpec design.md files"
    )
    parser.add_argument("paths", nargs="*", type=Path, help="optional design.md paths")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    requested_paths = [path.resolve() for path in args.paths]
    paths = requested_paths or discover_designs(project_root)
    paths = [path for path in paths if not is_archived_design(path, project_root)]
    failures = 0

    for path in paths:
        if not path.is_file():
            print(f"ERROR {path}: File does not exist", file=sys.stderr)
            failures += 1
            continue
        errors = validate_design(path, project_root)
        try:
            display_path = path.relative_to(project_root)
        except ValueError:
            display_path = path
        for error in errors:
            print(f"ERROR {display_path}: {error}", file=sys.stderr)
        failures += len(errors)

    if failures:
        print(f"OpenSpec design validation failed: {failures} issue(s)", file=sys.stderr)
        return 1

    print(f"OpenSpec design validation passed: {len(paths)} active design(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
