from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "validate_openspec_designs.py"
SPEC = importlib.util.spec_from_file_location("validate_openspec_designs", SCRIPT_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ValidateOpenSpecDesignsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.reference = (
            self.root
            / ".agents/skills/full-stack-engineering-practices/references/shared/engineering-workflow.md"
        )
        self.reference.parent.mkdir(parents=True)
        self.reference.write_text("# 通用工程工作流\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_design(self, standards_section: str) -> Path:
        path = self.root / "openspec/changes/example/design.md"
        path.parent.mkdir(parents=True)
        path.write_text(f"# 设计\n\n{standards_section}\n\n## Decisions\n\n采用现有结构。\n", encoding="utf-8")
        return path

    def test_accepts_complete_mapping(self) -> None:
        path = self.write_design(
            """## 编码规范适用性

### 变更范围
后端变更，涉及应用服务和测试。

### 已加载规范
| 规范文件 | 章节标题 | 适用原因 |
|---|---|---|
| `.agents/skills/full-stack-engineering-practices/references/shared/engineering-workflow.md` | 先分层，再编码 | 约束分层 |

### 规范落实
| 规范约束 | 设计决策 | 验证方式 |
|---|---|---|
| 分层边界 | 设计决策采用应用服务 | 验证方式为单元测试 |

### 不适用项
数据迁移不适用，因为没有数据结构变化。

### 规范偏离
无。"""
        )

        self.assertEqual([], VALIDATOR.validate_design(path, self.root))

    def test_rejects_placeholders_and_missing_reference(self) -> None:
        path = self.write_design(
            """## 编码规范适用性

### 变更范围
<!-- 待填写 -->

### 已加载规范
无。

### 规范落实
无。

### 不适用项
无。

### 规范偏离
无。"""
        )

        errors = VALIDATOR.validate_design(path, self.root)

        self.assertTrue(any("template placeholders" in error for error in errors))
        self.assertTrue(any("does not reference any" in error for error in errors))

    def test_rejects_invalid_deviation(self) -> None:
        path = self.write_design(
            """## 编码规范适用性

### 变更范围
后端变更。

### 已加载规范
`.agents/skills/full-stack-engineering-practices/references/shared/engineering-workflow.md` → 先分层，再编码

### 规范落实
设计决策：保持分层。验证方式：运行测试。

### 不适用项
无。

### 规范偏离
因为历史原因暂不遵守。"""
        )

        errors = VALIDATOR.validate_design(path, self.root)

        self.assertTrue(any("risk" in error for error in errors))
        self.assertTrue(any("mitigation" in error for error in errors))
        self.assertTrue(any("approval" in error for error in errors))

    def test_rejects_empty_mapping_tables(self) -> None:
        path = self.write_design(
            """## 编码规范适用性

### 变更范围
后端变更。

### 已加载规范
`.agents/skills/full-stack-engineering-practices/references/shared/engineering-workflow.md` → 先分层，再编码

| 规范文件 | 章节标题 | 适用原因 |
|---|---|---|

### 规范落实
| 规范约束 | 设计决策 | 验证方式 |
|---|---|---|

### 不适用项
无。

### 规范偏离
无。"""
        )

        errors = VALIDATOR.validate_design(path, self.root)

        self.assertTrue(any("loaded standards" in error and "mapping row" in error for error in errors))
        self.assertTrue(any("standards implementation" in error and "three-column" in error for error in errors))

    def test_rejects_non_reference_path_in_loaded_standards_table(self) -> None:
        path = self.write_design(
            """## 编码规范适用性

### 变更范围
后端变更。

### 已加载规范
| 规范文件 | 章节标题 | 适用原因 |
|---|---|---|
| docs/general.md | 通用规则 | 约束实现 |

### 规范落实
| 规范约束 | 设计决策 | 验证方式 |
|---|---|---|
| 分层边界 | 采用应用服务 | 运行单元测试 |

### 不适用项
无。

### 规范偏离
无。"""
        )

        errors = VALIDATOR.validate_design(path, self.root)

        self.assertTrue(any("Invalid reference path" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
