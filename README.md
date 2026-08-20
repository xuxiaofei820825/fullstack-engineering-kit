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
```

## 安装到项目

目标环境需要安装 OpenSpec 1.9.0、Python 3.9 或更高版本，并先在项目中初始化 OpenSpec：

```bash
npm install -g @fission-ai/openspec@1.9.0
cd /path/to/target-project
openspec init
```

### 从 GitHub Releases 一步安装

本仓库通过 GitHub Releases 发布版本化的完整安装包。用户不需要 clone 本仓库；`bootstrap.sh` 会把指定版本下载到临时目录，校验 SHA-256，调用原有安装器，并在完成后清理临时文件。

公开仓库在已经执行过 `openspec init` 的目标项目中运行：

```bash
curl -fsSL \
  "https://github.com/xuxiaofei820825/fullstack-engineering-kit/releases/download/v1.0.5/bootstrap.sh" \
| bash -s -- \
    --repository xuxiaofei820825/fullstack-engineering-kit \
    --target . \
    --version 1.0.5
```

私有仓库使用已经通过 `gh auth login` 认证的 GitHub CLI，或提前设置具有仓库读取权限的 `GH_TOKEN`：

```bash
gh release download v1.0.5 \
  --repo xuxiaofei820825/fullstack-engineering-kit \
  --pattern bootstrap.sh \
  --output - \
| bash -s -- \
    --repository xuxiaofei820825/fullstack-engineering-kit \
    --target . \
    --version 1.0.5 \
    --use-gh
```

也可以通过 `FULLSTACK_ENGINEERING_KIT_GITHUB_REPOSITORY=xuxiaofei820825/fullstack-engineering-kit` 设置默认仓库。旧环境变量 `ENGINEERING_STANDARDS_GITHUB_REPOSITORY` 暂时兼容；同时设置时优先使用新名称。安装命令必须明确指定语义版本，不接受 `main` 或 `latest`。升级时把版本改为目标版本并增加 `--update`。

应将发布标签配置为受保护标签，并要求用户从可信渠道取得版本号和仓库地址。SHA-256 可以发现传输损坏或发布资产不一致，但不能替代 GitHub 权限控制、HTTPS 和受保护标签。

### 从本地检出安装

开发或排查发布流程时，也可以从本仓库对应版本执行安装：

```bash
cd /path/to/fullstack-engineering-kit
./scripts/install.sh /path/to/target-project --version 1.0.5
./scripts/verify-installation.sh /path/to/target-project
```

安装器会安装：

- `.agents/skills/full-stack-engineering-practices/`
- `openspec/schemas/engineering-governed/`
- design 校验器及其测试
- 平台无关的统一质量门禁脚本
- `.fullstack-engineering-kit-version`

从旧版本升级时，安装器会识别 `.engineering-standards-version`；使用 `--update` 成功升级后会写入新标记并删除旧标记。

目标项目没有 `openspec/config.yaml` 时，安装器使用本仓库的配置作为初始值。执行过 `openspec init` 的项目通常已经存在配置；此时安装器只把顶层 `schema` 更新为 `engineering-governed`，保留已有 context、rules 和其他项目配置。强制工作流规则维护在 schema 中，因此不会依赖目标项目复制本仓库的 context。

安装后确认解析结果：

```bash
cd /path/to/target-project
openspec schema which engineering-governed
openspec schema validate engineering-governed
```

`schema which` 的结果应显示 `Source: project`，路径应位于当前项目的 `openspec/schemas/engineering-governed`。

## 在 Codex 中使用 Skill

从项目根目录或其子目录启动 Codex。Codex 会扫描仓库根目录到当前工作目录之间的 `.agents/skills`，因此项目内的 `full-stack-engineering-practices` 可以被自动发现。

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

1. 读取 `.agents/skills/full-stack-engineering-practices/SKILL.md`。
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
| `.agents/skills/full-stack-engineering-practices/references/backend/architecture-and-api.md` | API 设计 | 新增查询接口 |
| `.agents/skills/full-stack-engineering-practices/references/integration.md` | 契约优先 | 前后端共同使用分页契约 |

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
python3 -B scripts/validate_openspec_designs.py
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
python3 -B scripts/validate_openspec_designs.py
openspec archive add-order-export
```

归档前应确认 tasks 全部完成，实际测试、构建、契约核对和规范 Review 结果已经记录。

## 质量门禁

安装后的项目通过一个平台无关的入口执行全部规范校验：

```bash
./scripts/validate-engineering-standards.sh
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

在目标项目中直接使用 GitHub Release 提供的 `bootstrap.sh`，把版本号改为需要升级到的明确版本，并增加 `--update`：

```bash
cd /path/to/target-project

curl -fsSL \
  "https://github.com/xuxiaofei820825/fullstack-engineering-kit/releases/download/v1.0.5/bootstrap.sh" \
| bash -s -- \
    --repository xuxiaofei820825/fullstack-engineering-kit \
    --target . \
    --version 1.0.5 \
    --update
```

如果已经检出本仓库，也可以使用本地安装器：

```bash
./scripts/install.sh /path/to/target-project --update --version 1.0.5
./scripts/verify-installation.sh /path/to/target-project
```

安装器遇到内容不同的已管理文件时默认停止且不写入。`--update` 会替换 Skill、schema、校验器和统一质量门禁脚本等已管理文件，但不会覆盖目标项目的 `openspec/config.yaml`；该文件仍只更新顶层 `schema`。建议通过项目实际采用的代码审查流程检查安装或升级产生的差异。

## 本仓库验证

```bash
./scripts/validate-engineering-standards.sh
```

## 发布到 GitHub Releases

完整的版本准备、自动发布、验证和空 Release 修复步骤见 [发布指南](RELEASE.md)。

`.github/workflows/release.yml` 只用于发布本规范仓库，不要求安装规范的目标项目托管在 GitHub。Pull Request 和 `main` 分支推送会运行验证；推送形如 `v1.0.5` 的标签时，发布任务会：

1. 检查标签版本与 `VERSION` 完全一致。
2. 在 GitHub 托管的 Ubuntu Runner 上执行完整 OpenSpec、Python 和安装流程验证。
3. 构建可复现的 `fullstack-engineering-kit-1.0.5.tar.gz`。
4. 生成对应的 `.sha256` 文件。
5. 使用工作流内置的 `GITHUB_TOKEN` 创建 GitHub Release，并上传归档、校验文件和 `bootstrap.sh`。

发布前可以在本地检查产物：

```bash
./scripts/build-release.sh dist
tar -tzf dist/fullstack-engineering-kit-1.0.5.tar.gz
```

创建标签前，应先更新 `VERSION`，运行完整验证，并通过代码审查。标签发布后不要复用同一版本覆盖包；修复内容应递增版本并发布新标签。

## 参考资料

- [OpenAI Docs：Build skills](https://learn.chatgpt.com/docs/build-skills)
- [OpenSpec：Customization](https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md)
- [OpenSpec：CLI Reference](https://github.com/Fission-AI/OpenSpec/blob/main/docs/cli.md)
- [GitHub CLI：创建 Release](https://cli.github.com/manual/gh_release_create)
- [GitHub CLI：下载 Release 资产](https://cli.github.com/manual/gh_release_download)
