# Fullstack Engineering Kit

Fullstack Engineering Kit（`fsek`）将 OpenSpec 的规格驱动流程与工程规范 Skill 结合，用统一规则约束设计、任务拆分、实现、测试、代码审查和交付。

支持以下 AI 编码工具：

| 平台 | Skill 安装目录 |
|---|---|
| Codex | `.codex/skills/` |
| Claude Code | `.claude/skills/` |
| OpenCode | `.opencode/skills/` |

## 使用者指南

### 环境要求

- Node.js 20.19 或更高版本
- Python 3.10 或更高版本

CLI 包内置固定版本的 OpenSpec 1.9.0，无需单独安装 OpenSpec。

### 安装 CLI

从 GitHub Release 安装当前版本：

```bash
npm install --global \
  "https://github.com/xuxiaofei820825/fullstack-engineering-kit/releases/download/v1.3.2/fullstack-engineering-kit-cli-1.3.2.tgz"
```

确认安装：

```bash
fsek version
fsek --help
```

完整命令为 `fullstack-engineering-kit`，本文统一使用短命令 `fsek`。

### 初始化项目

进入目标项目并运行：

```bash
cd /path/to/project
fsek init
```

交互模式会检测已有工具目录并要求选择平台。非交互环境必须明确指定平台，或使用 `--yes` 接受自动检测结果：

```bash
fsek init /path/to/project --platform codex
fsek init /path/to/project --platform claude
fsek init /path/to/project --platform opencode
fsek init /path/to/project --yes
```

初始化会完成以下工作：

1. 初始化 OpenSpec；
2. 将 `full-stack-engineering-practices` Skill 安装到所选平台目录；
3. 安装并启用 `engineering-governed` schema；
4. 将校验工具安装到 `.fullstack-engineering-kit/`；
5. 记录套件版本和平台信息。

不会在项目根目录创建或占用 `scripts/`。选择 Codex 时，OpenSpec 生成的技能最终统一存放在 `.codex/skills/`；`.agents` 中的用户文件不会被删除。

### CLI 命令

| 命令 | 用途 |
|---|---|
| `fsek init [path]` | 初始化 OpenSpec、Skill 和 schema |
| `fsek update [path]` | 升级项目内的规范套件和 OpenSpec 技能 |
| `fsek self-update` | 检查并升级全局 CLI |
| `fsek verify [path]` | 验证安装状态、schema 和活动 change |
| `fsek doctor [path]` | 检查运行环境和项目安装状态 |
| `fsek version` | 显示 CLI 和内置套件版本 |

常用选项：

| 选项 | 用途 |
|---|---|
| `--platform codex\|claude\|opencode` | 指定目标平台 |
| `--yes` | 接受自动检测的平台或默认值 |
| `--dry-run` | 仅显示将发生的变更 |
| `--skip-openspec` | 不执行 `openspec init/update` |
| `--files-only` | `verify` 仅检查文件和配置 |

运行 `fsek --help` 可查看完整参数。

### 日常工作流

创建 OpenSpec change：

```bash
openspec new change add-order-export
openspec status --change add-order-export
```

在支持 OPSX 的工具中，也可以使用：

```text
/opsx:propose add-order-export
/opsx:continue add-order-export
/opsx:apply add-order-export
```

`engineering-governed` schema 会在 design、tasks 和 apply 阶段要求 AI 读取当前平台中的 `full-stack-engineering-practices` Skill，并根据后端、前端或跨端范围加载适用规范。

design 必须包含“编码规范适用性”，明确记录：

- 变更范围；
- 已加载的规范文件及章节；
- 规范约束对应的设计决策和验证方式；
- 不适用项及原因；
- 规范偏离、风险、替代措施和审批状态。

实现完成后运行：

```bash
fsek verify
```

`verify` 只校验活动 change，不检查 `openspec/changes/archive/` 中的归档 change，也不检查已经同步到 `openspec/specs/` 的主规范。

验证通过后归档：

```bash
openspec archive add-order-export
```

### 在 Codex 中使用 Skill

使用 `--platform codex` 初始化后，从项目根目录或其子目录启动 Codex。通常由 schema 自动触发 Skill；需要明确触发时可以使用：

```text
$full-stack-engineering-practices
```

也可以在需求中直接说明：

```text
使用 $full-stack-engineering-practices，按照 OpenSpec 变更 add-order-export 完成设计和实现。
```

### 升级

CLI 升级和项目升级相互独立。先升级全局 CLI，再更新每个已初始化项目：

```bash
fsek self-update

cd /path/to/project
fsek update
fsek verify
```

仅检查是否有新版本：

```bash
fsek self-update --check
```

安装指定版本：

```bash
fsek self-update --version 1.3.2
```

切换平台时显式指定目标：

```bash
fsek update --platform opencode
```

如果 `verify` 报告 CLI 与项目版本不一致，运行 `fsek update` 后再验证。

### CI 集成

CI 中可以直接使用：

```bash
fsek verify
```

也可以调用安装到项目内的入口：

```bash
./.fullstack-engineering-kit/validate-engineering-standards.sh
```

校验失败时命令返回非零状态，可直接作为流水线质量门禁。

## 开发者指南

### 核心组件

| 组件 | 职责 |
|---|---|
| CLI | 提供初始化、升级、自升级、验证和诊断命令 |
| OpenSpec | 管理 proposal、specs、design、tasks、apply 和 archive 生命周期 |
| `engineering-governed` schema | 将工程规范要求注入 design、tasks 和 apply 阶段 |
| `full-stack-engineering-practices` Skill | 根据实际变更范围加载共享、后端、前端或跨端规范 |

工作流：

```text
proposal → specs → design → tasks → apply → 规范 Review → archive
                     │         │       │          │
                     └─────────┴───────┴──────────┘
                         读取 Skill 和适用 references
```

### 仓库结构

```text
.agents/skills/full-stack-engineering-practices/
├── SKILL.md
└── references/

cli/
└── fullstack-engineering-kit.mjs

openspec/
├── config.yaml
└── schemas/engineering-governed/

scripts/
├── build-release.sh
├── install.sh
├── validate-engineering-standards.sh
├── validate_openspec_designs.py
└── verify_engineering_standards.py
```

仓库中的 `.agents/skills/` 是发布包的规范源码目录，不是 CLI 面向目标项目提供的安装平台。

### 本地开发

安装依赖：

```bash
npm ci
```

运行测试和静态检查：

```bash
python3 -B -m unittest discover -s scripts/tests -p 'test_*.py'
node --test cli/tests/cli.test.mjs
node --check cli/fullstack-engineering-kit.mjs
bash -n scripts/*.sh
```

从本地检出安装到测试项目：

```bash
./scripts/install.sh /path/to/project --version 1.3.2 --platform codex
./scripts/verify-installation.sh /path/to/project
```

构建发布资产：

```bash
./scripts/build-release.sh dist
```

产物写入 `dist/`，包括 npm CLI 包、兼容安装包、SHA-256 校验文件和 `bootstrap.sh`。

### 版本与发布

发布前必须同步更新：

- `VERSION`
- `package.json`
- `package-lock.json`
- README 中的安装版本和示例

完整的版本准备、标签、GitHub Actions 和发布验证流程见 [RELEASE.md](RELEASE.md)。发布后的 GitHub Release 标题使用 `v<版本>` 格式。

## 参考资料

- [OpenSpec：Customization](https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md)
- [OpenSpec：CLI Reference](https://github.com/Fission-AI/OpenSpec/blob/main/docs/cli.md)
- [GitHub CLI：创建 Release](https://cli.github.com/manual/gh_release_create)
