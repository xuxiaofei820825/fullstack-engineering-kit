# fullstack-engineering-kit

本仓库将 OpenSpec 的规格驱动流程与 Codex Skill 结合，用同一套编码规范约束设计、任务拆分、实现、测试、代码审查和交付。

## 工作方式

三个核心组件各自承担不同职责：

| 组件 | 职责 |
|---|---|
| OpenSpec | 管理 proposal、specs、design、tasks、apply 和 archive 生命周期 |
| `engineering-governed` schema | 在 design、tasks 和 apply 阶段强制注入规范使用要求 |
| `full-stack-engineering-practices` Skill | 作为编码规范入口，根据后端、前端或跨端范围加载适用 references |

完整流程如下：

```text
proposal → specs → design → tasks → apply → 规范 Review → archive
                     │         │       │          │
                     └─────────┴───────┴──────────┘
                         读取 Skill 和适用 references
```

OpenSpec 负责确定当前阶段和产物结构，不直接保存全部编码规范。schema 要求代理在需要技术决策或代码操作时读取 Skill；Skill 再根据实际变更范围选择共享、后端、前端或跨端规范，避免把无关规范全部加载进上下文。

## 目录结构

```text
.agents/skills/full-stack-engineering-practices/
├── SKILL.md
└── references/
    ├── shared/
    ├── backend/
    ├── frontend/
    └── integration.md

openspec/
├── config.yaml
└── schemas/engineering-governed/
    ├── schema.yaml
    └── templates/

scripts/
├── bootstrap.sh
├── build-release.sh
├── install.sh
├── verify-installation.sh
├── validate-engineering-standards.sh
└── validate_openspec_designs.py

cli/
└── fullstack-engineering-kit.mjs
```

## 安装到项目

推荐使用随 GitHub Release 发布的终端程序。目标环境只需 Node.js 20.19 或更高版本和 Python 3.10 或更高版本；CLI 的 npm 包会安装固定版本的 OpenSpec 1.9.0。

### 安装终端程序

```bash
npm install --global \
  "https://github.com/xuxiaofei820825/fullstack-engineering-kit/releases/download/v1.3.1/fullstack-engineering-kit-cli-1.3.1.tgz"
```

安装后可以使用完整命令 `fullstack-engineering-kit`，也可以使用短命令 `fsek`：

```bash
cd /path/to/target-project
fsek init
```

在交互终端中，`init` 会检测 `.codex`、`.claude` 和 `.opencode`，显示平台选择界面，然后完成以下操作：

1. 使用所选平台初始化 OpenSpec；
2. 安装对应平台的 `full-stack-engineering-practices` Skill；
3. 安装并启用 `engineering-governed` schema；
4. 写入安装版本和平台元数据；
5. 将校验工具放入 `.fullstack-engineering-kit/`，不占用项目的 `scripts/`。

CI 或其他非交互环境必须明确指定平台，或者使用 `--yes` 接受自动检测结果：

```bash
fsek init /path/to/target-project --platform codex
fsek init /path/to/target-project --yes
```

### CLI 命令

| 命令 | 用途 |
|---|---|
| `fsek init [path]` | 初始化 OpenSpec、Skill 和 schema |
| `fsek update [path]` | 按安装元数据中的平台升级规范，并更新 OpenSpec 指令 |
| `fsek self-update` | 从 GitHub Release 校验并升级全局 CLI |
| `fsek verify [path]` | 验证受管文件、schema 和 OpenSpec 产物 |
| `fsek doctor [path]` | 检查 Node.js、Python、OpenSpec 和项目安装状态 |
| `fsek version` | 显示 CLI 和内置规范套件版本 |

`verify` 只校验活动 change；`openspec/changes/archive/` 下已经归档的 change 不参与校验。主规范 `openspec/specs/` 仍会校验，因为它们是归档合并后的当前规范基线。

`--platform` 决定项目级 Skill 的安装位置：

| 参数 | Skill 目录 |
|---|---|
| `codex` | `.codex/skills/full-stack-engineering-practices/` |
| `claude` | `.claude/skills/full-stack-engineering-practices/` |
| `opencode` | `.opencode/skills/full-stack-engineering-practices/` |

未指定平台时默认使用 Codex。`update` 默认沿用初始化时记录的平台；显式传入另一个 `--platform` 可以迁移平台。旧版安装在 `.agents` 中的 Skill 会在升级时迁移，但 `.agents` 不再作为新安装平台。`--dry-run` 只展示规范文件变更，`--skip-openspec` 用于已经由外部流程管理 OpenSpec 的环境。

### 兼容旧版 bootstrap 安装

原有 `bootstrap.sh` 安装方式继续保留，便于已有自动化平滑迁移。新项目优先使用 `fsek init`。

已初始化 OpenSpec 的项目可以运行：

```bash
curl -fsSL \
  "https://github.com/xuxiaofei820825/fullstack-engineering-kit/releases/download/v1.3.1/bootstrap.sh" \
| bash -s -- \
    --repository xuxiaofei820825/fullstack-engineering-kit \
    --target . \
    --version 1.3.1 \
    --platform codex
```

私有仓库仍可使用 `gh release download` 获取 `bootstrap.sh` 并传入 `--use-gh`。`FULLSTACK_ENGINEERING_KIT_GITHUB_REPOSITORY` 可设置默认仓库；旧变量 `ENGINEERING_STANDARDS_GITHUB_REPOSITORY` 继续兼容。

### 从本地检出安装

开发或排查发布流程时，也可以从本仓库对应版本执行安装：

```bash
cd /path/to/fullstack-engineering-kit
./scripts/install.sh /path/to/target-project --version 1.3.1 --platform codex
./scripts/verify-installation.sh /path/to/target-project
```

安装器会安装：

- 所选平台对应的 Skill 目录
- `openspec/schemas/engineering-governed/`
- `.fullstack-engineering-kit/` 下的 design 校验器、测试和统一质量门禁脚本
- `.fullstack-engineering-kit-version`

安装器不会创建或占用目标项目的 `scripts/`。从旧版本升级时，使用 `--update` 会迁移旧版放在 `scripts/` 下的受管校验文件，并迁移到新选择的平台目录；项目中其他脚本不受影响。安装器也会识别 `.engineering-standards-version`，升级后写入新标记并删除旧标记。

目标项目没有 `openspec/config.yaml` 时，安装器使用本仓库的配置作为初始值。执行过 `openspec init` 的项目通常已经存在配置；此时安装器只把顶层 `schema` 更新为 `engineering-governed`，保留已有 context、rules 和其他项目配置。强制工作流规则维护在 schema 中，因此不会依赖目标项目复制本仓库的 context。

安装后确认解析结果：

```bash
cd /path/to/target-project
openspec schema which engineering-governed
openspec schema validate engineering-governed
```

`schema which` 的结果应显示 `Source: project`，路径应位于当前项目的 `openspec/schemas/engineering-governed`。

## 在 Codex 中使用 Skill

使用 `--platform codex` 安装后，从项目根目录或其子目录启动 Codex。项目内的 `.codex/skills/full-stack-engineering-practices` 会被自动发现。

通常不需要手动指定 Skill：`engineering-governed` 会在 design、tasks 和 apply 指令中要求加载它。需要明确触发时，可以在 Codex CLI 或 IDE 中使用：

```text
$full-stack-engineering-practices
```

也可以在需求中直接说明：

```text
使用 $full-stack-engineering-practices，按照 OpenSpec 变更 add-order-export 完成设计和实现。
```

Skill 会先判断变更范围：

- 所有变更读取共享工程工作流。
- 后端变更按需读取架构、API、安全、可观测性、测试和交付规范。
- 前端变更按需读取工程、测试、交付和反模式规范。
- 跨端变更同时读取两侧相关规范及集成规范。

## 日常开发流程

### 创建变更

```bash
openspec new change add-order-export
openspec status --change add-order-export
```

在支持 OPSX 命令的 Codex 环境中，可以逐个生成并审查产物：

```text
/opsx:propose add-order-export
/opsx:continue add-order-export
```

也可以获取当前 schema 注入后的原始指令：

```bash
openspec instructions proposal --change add-order-export
openspec instructions specs --change add-order-export
openspec instructions design --change add-order-export
openspec instructions tasks --change add-order-export
```

建议逐个生成和审查产物，不要在设计尚未确认时直接进入实现。

### Proposal 和 Specs

proposal 说明为什么修改、修改范围及受影响能力；specs 描述用户或下游系统可以观察和验证的行为。内部架构、类名和实现步骤放在 design，不要混入行为规格。

### Design

design 阶段是 OpenSpec 与编码规范结合的关键点。schema 会要求代理：

1. 读取当前平台目录下的 `full-stack-engineering-practices/SKILL.md`（Codex 为 `.codex/skills/...`）。
2. 判断变更是后端、前端还是跨端。
3. 按 Skill 路由加载全部适用 references。
4. 完整填写“编码规范适用性”。
5. 使用“reference 文件路径 + 章节标题”引用规范。
6. 把规范约束映射为具体设计决策和验证方式。
7. 说明关键不适用项及任何规范偏离。

规范映射示例：

```markdown
## 编码规范适用性

### 变更范围

跨端变更，涉及后端查询 API、前端列表页面和契约测试。

### 已加载规范

| 规范文件 | 章节标题 | 适用原因 |
|---|---|---|
| `.codex/skills/full-stack-engineering-practices/references/backend/architecture-and-api.md` | API 设计 | 新增查询接口 |
| `.codex/skills/full-stack-engineering-practices/references/integration.md` | 契约优先 | 前后端共同使用分页契约 |

### 规范落实

| 规范约束 | 设计决策 | 验证方式 |
|---|---|---|
| 请求响应对象边界明确 | 为查询条件和分页响应定义独立类型 | 后端契约测试和前端 Service 测试 |

### 不适用项

数据迁移不适用，本次不改变数据库结构和存量数据。

### 规范偏离

无。
```

不得只写“遵循编码规范”，也不得引用已经废弃的原始文档章节号。

完成 design 后运行：

```bash
python3 -B .fullstack-engineering-kit/validate_openspec_designs.py
```

### Tasks

tasks 必须继承 design 中已经确定的规范约束。实现任务应引用对应的 reference 路径和章节标题，并明确拆分：

- 前端、后端或跨端实现任务
- 测试对象、类型、场景、隔离边界、断言和执行命令
- 联调或契约核对任务
- 完成前的规范 Review、修复、回归验证和重新 Review

### Apply 和 Review

开始实现前获取 apply 指令，或使用 OPSX：

```bash
openspec instructions apply --change add-order-export
```

```text
/opsx:apply add-order-export
```

apply 阶段会再次加载 Skill、design 和适用 references。代码修改完成后，必须执行：

```text
完整变更 → 按适用规范 Review → 修复 → 回归验证 → 重新 Review
```

只有最新一轮完整 Review 没有未解决问题、必要验证全部通过、没有未说明的未验证项时，才能把任务标记为完成。每个 Review 问题都应包含代码位置、证据、风险以及对应的规范文件和章节标题。

### 验证和归档

```bash
openspec validate --all --strict --no-interactive
python3 -B .fullstack-engineering-kit/validate_openspec_designs.py
openspec archive add-order-export
```

归档前应确认 tasks 全部完成，实际测试、构建、契约核对和规范 Review 结果已经记录。

## 质量门禁

安装后的项目通过一个平台无关的入口执行全部规范校验：

```bash
./.fullstack-engineering-kit/validate-engineering-standards.sh
```

该脚本会执行：

- 校验 `engineering-governed` schema
- 严格校验全部 OpenSpec 产物
- 运行 design 校验器测试
- 校验活动变更中的编码规范映射

它不依赖特定 CI 平台，可以直接作为任意流水线的一个 shell 步骤。例如 Jenkins、GitHub Actions 或其他内部平台只需准备 Node.js、OpenSpec 1.9.0 和 Python 3，然后在项目根目录执行上述命令。没有 CI 平台时，也可以把该命令作为提交前或交付前的本地门禁。

以下情况会使脚本以非零状态退出，从而阻止流水线继续：

- design 缺少必要规范章节或仍保留模板占位符
- “已加载规范”没有引用真实存在的 reference
- “规范落实”没有建立规范、设计决策和验证方式之间的映射
- 使用原始 `coding-standards.md` 章节号代替 Skill references
- 规范偏离没有说明风险、替代措施和审批状态
- OpenSpec 产物格式不合法

## 升级规范套件

先升级全局 CLI，再在项目中执行 `update`。项目的平台会从安装元数据自动读取：

```bash
fsek self-update

cd /path/to/target-project
fsek update
fsek verify
```

只检查新版本或安装指定版本：

```bash
fsek self-update --check
fsek self-update --version 1.3.1
```

`self-update` 会下载 CLI 包及对应 `.sha256`，校验通过后才调用 npm 全局安装。默认拒绝降级；私有 Release 可以通过 `GH_TOKEN` 或 `GITHUB_TOKEN` 认证。CLI 升级与项目升级保持分离，因此升级 CLI 后仍需在各项目中运行 `fsek update`。

切换平台时显式指定目标：

```bash
fsek update --platform codex
```

安装器遇到内容不同的已管理文件时默认停止且不写入。`--update` 会替换 Skill、schema、校验器和统一质量门禁脚本等已管理文件，但不会覆盖目标项目的 `openspec/config.yaml`；该文件仍只更新顶层 `schema`。建议通过项目实际采用的代码审查流程检查安装或升级产生的差异。

## 本仓库验证

```bash
./scripts/validate-engineering-standards.sh
```

## 发布到 GitHub Releases

完整的版本准备、自动发布、验证和空 Release 修复步骤见 [发布指南](RELEASE.md)。

`.github/workflows/release.yml` 只用于发布本规范仓库，不要求安装规范的目标项目托管在 GitHub。Pull Request 和 `main` 分支推送会运行验证；推送形如 `v1.3.1` 的标签时，发布任务会：

1. 检查标签版本与 `VERSION` 完全一致。
2. 在 GitHub 托管的 Ubuntu Runner 上执行完整 OpenSpec、Python 和安装流程验证。
3. 构建可复现的 `fullstack-engineering-kit-1.3.1.tar.gz`。
4. 生成对应的 `.sha256` 文件。
5. 使用工作流内置的 `GITHUB_TOKEN` 创建 GitHub Release，并上传 CLI 包、兼容安装包、校验文件和 `bootstrap.sh`。

发布前可以在本地检查产物：

```bash
./scripts/build-release.sh dist
tar -tzf dist/fullstack-engineering-kit-1.3.1.tar.gz
tar -tzf dist/fullstack-engineering-kit-cli-1.3.1.tgz
```

创建标签前，应先更新 `VERSION`，运行完整验证，并通过代码审查。标签发布后不要复用同一版本覆盖包；修复内容应递增版本并发布新标签。

## 参考资料

- [OpenAI Docs：Build skills](https://learn.chatgpt.com/docs/build-skills)
- [OpenSpec：Customization](https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md)
- [OpenSpec：CLI Reference](https://github.com/Fission-AI/OpenSpec/blob/main/docs/cli.md)
- [GitHub CLI：创建 Release](https://cli.github.com/manual/gh_release_create)
- [GitHub CLI：下载 Release 资产](https://cli.github.com/manual/gh_release_download)
