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
REFERENCE_PATTERN = re.compile(
    r"(?:`)?(\.agents/skills/full-stack-engineering-practices/"
    r"references/[A-Za-z0-9_./-]+\.md)(?:`)?"
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
        return ["缺少二级章节“编码规范适用性”"]

    if "<!--" in standards_section or "-->" in standards_section:
        errors.append("“编码规范适用性”仍包含模板占位注释")

    subsection_content: dict[str, str] = {}
    for title in REQUIRED_SUBSECTIONS:
        content = extract_section(standards_section, 3, title)
        if content is None:
            errors.append(f"缺少三级章节“{title}”")
            continue
        cleaned = meaningful_content(content)
        subsection_content[title] = cleaned
        if not cleaned:
            errors.append(f"三级章节“{title}”没有实际内容")

    loaded_content = subsection_content.get("已加载规范", "")
    references = sorted(set(REFERENCE_PATTERN.findall(loaded_content)))
    if not references:
        errors.append("“已加载规范”未引用任何 full-stack-engineering-practices reference")
    for reference in references:
        if not (project_root / reference).is_file():
            errors.append(f"引用的规范文件不存在：{reference}")

    loaded_rows = table_data_rows(loaded_content, 3)
    if not loaded_rows or any(not all(row) for row in loaded_rows):
        errors.append("“已加载规范”必须至少包含一行三列均非空的规范映射")
    for row in loaded_rows:
        reference_cell = row[0]
        if not REFERENCE_PATTERN.fullmatch(reference_cell):
            errors.append(f"“已加载规范”的规范文件不是有效 reference 路径：{reference_cell}")

    implementation_rows = table_data_rows(subsection_content.get("规范落实", ""), 3)
    if not implementation_rows or any(not all(row) for row in implementation_rows):
        errors.append("“规范落实”必须至少包含一行三列均非空的约束、设计决策和验证方式映射")

    if re.search(r"coding-standards\.md", standards_section, re.IGNORECASE):
        errors.append("不得在规范映射中引用原始 coding-standards.md")
    if OLD_CHAPTER_PATTERN.search(standards_section):
        errors.append("不得在规范映射中使用原始文档章节号")
    if "遵循编码规范" in standards_section:
        errors.append("不得使用笼统的“遵循编码规范”代替规范映射")

    deviation = subsection_content.get("规范偏离", "").strip().rstrip("。")
    if deviation and deviation != "无":
        for keyword in ("风险", "替代措施", "审批"):
            if keyword not in deviation:
                errors.append(f"存在规范偏离时必须说明{keyword}")

    return errors


def discover_designs(project_root: Path) -> list[Path]:
    return sorted((project_root / "openspec" / "changes").glob("*/design.md"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="校验活动 OpenSpec design.md 中的编码规范映射"
    )
    parser.add_argument("paths", nargs="*", type=Path, help="可选的 design.md 路径")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    paths = [path.resolve() for path in args.paths] or discover_designs(project_root)
    failures = 0

    for path in paths:
        if not path.is_file():
            print(f"ERROR {path}: 文件不存在", file=sys.stderr)
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
        print(f"OpenSpec design 校验失败：{failures} 个问题", file=sys.stderr)
        return 1

    print(f"OpenSpec design 校验通过：{len(paths)} 个活动设计")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
