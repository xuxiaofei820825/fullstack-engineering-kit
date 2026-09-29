# 发布指南

本文说明如何为 `xuxiaofei820825/fullstack-engineering-kit` 创建 GitHub Release，以及如何修复 Release 已存在但缺少安装资产的情况。

## 发布产物

每个版本必须包含以下五个 Release 资产：

- `fullstack-engineering-kit-<VERSION>.tar.gz`
- `fullstack-engineering-kit-<VERSION>.tar.gz.sha256`
- `fullstack-engineering-kit-cli-<VERSION>.tgz`
- `fullstack-engineering-kit-cli-<VERSION>.tgz.sha256`
- `bootstrap.sh`

`.tgz` 是推荐安装的 npm CLI 包；原压缩包和 `bootstrap.sh` 继续用于兼容已有自动化。只创建 Git 标签或空 Release 无法完成终端程序安装。

## 发布前准备

发布环境需要：

- Git
- Python 3.10 或更高版本
- Node.js 20.19 或更高版本和 npm
- OpenSpec 1.9.0
- 对仓库具有推送标签权限
- 仓库已启用 GitHub Actions，并允许工作流使用 `contents: write` 权限创建 Release

安装并确认 OpenSpec：

```bash
npm install -g @fission-ai/openspec@1.9.0
openspec --version
```

确认工作区只包含准备发布的变更：

```bash
git status --short
```

## 标准自动发布流程

推荐让 `.github/workflows/release.yml` 自动创建 Release 和上传资产。不要在推送标签前手动创建同名 Release，否则工作流中的 `gh release create` 会因 Release 已存在而失败。

以下示例发布 `1.3.1`。实际发布时将版本替换为新的语义版本。

### 1. 更新版本

修改根目录 `VERSION`：

```text
1.3.1
```

同步更新 `package.json`、`package-lock.json` 和 README 中展示给用户的安装版本，确保 npm 包版本、下载标签、`--version` 参数和 `VERSION` 一致。

已经发布的版本不可复用或覆盖。任何内容修复都应递增版本号并创建新标签。

### 2. 执行完整验证

```bash
./scripts/validate-engineering-standards.sh
```

验证必须全部通过后才能继续发布。

### 3. 本地构建并检查发布资产

```bash
./scripts/build-release.sh dist
ls -l dist
tar -tzf dist/fullstack-engineering-kit-1.3.1.tar.gz
tar -tzf dist/fullstack-engineering-kit-cli-1.3.1.tgz
```

预期生成：

```text
dist/bootstrap.sh
dist/fullstack-engineering-kit-1.3.1.tar.gz
dist/fullstack-engineering-kit-1.3.1.tar.gz.sha256
dist/fullstack-engineering-kit-cli-1.3.1.tgz
dist/fullstack-engineering-kit-cli-1.3.1.tgz.sha256
```

`dist/` 已被 `.gitignore` 忽略，不需要提交。

### 4. 提交并推送版本变更

```bash
git add VERSION package.json package-lock.json README.md RELEASE.md
git commit -m "chore: release v1.3.1"
git push origin main
```

等待 `main` 分支上的验证工作流通过，再创建标签。

### 5. 创建并推送标签

标签必须使用 `v<语义版本>` 格式，并与 `VERSION` 完全一致：

```bash
git tag -a v1.3.1 -m "Release v1.3.1"
git push origin v1.3.1
```

推送标签后，GitHub Actions 会自动：

1. 安装 Python、Node.js 和 OpenSpec。
2. 执行完整规范校验。
3. 检查标签版本与 `VERSION` 是否一致。
4. 构建 npm CLI 包、兼容压缩包、SHA-256 文件和 `bootstrap.sh`。
5. 创建 GitHub Release 并上传五个资产。

在仓库的 [Actions](https://github.com/xuxiaofei820825/fullstack-engineering-kit/actions) 页面确认 `Validate and release Fullstack Engineering Kit` 工作流成功。

### 6. 验证 Release

打开 [Releases](https://github.com/xuxiaofei820825/fullstack-engineering-kit/releases)，确认目标版本不是 Draft，并且包含五个发布资产。

也可以检查安装脚本 URL：

```bash
curl -fsSIL \
  "https://github.com/xuxiaofei820825/fullstack-engineering-kit/releases/download/v1.3.1/bootstrap.sh"
```

返回 HTTP 200 后，优先验证终端程序包：

```bash
npm install --global \
  "https://github.com/xuxiaofei820825/fullstack-engineering-kit/releases/download/v1.3.1/fullstack-engineering-kit-cli-1.3.1.tgz"

mkdir /path/to/test-project
fsek init /path/to/test-project --platform codex
fsek doctor /path/to/test-project
fsek verify /path/to/test-project
fsek self-update --check
```

随后再按需执行一次 `bootstrap.sh` 兼容安装验证。

## 处理已存在但为空的 Release

如果 Release 已创建但没有上传资产，对应的安装 URL 会返回 HTTP 404。不要用后续代码重新构建并回填已经发布的旧版本，因为构建内容可能与旧标签不一致。

本仓库的 `v1.0.4` 属于这种情况。后续修复应递增版本并按照“标准自动发布流程”创建新 Release，不回填 `v1.0.4`。README 只推荐已经验证并包含完整资产的当前版本。

空的旧 Release 可以保留作为历史记录。如果确认其中没有需要保留的说明或资产，也可以在 GitHub 页面删除该 Release，但不要删除或重写已经推送的标签。删除 Release 会改变远端状态，执行前应再次核对目标版本。

## 手动发布

仅当 GitHub Actions 无法使用时，才采用手动发布。先完成前述验证和本地构建，然后执行：

```bash
gh release create v1.3.1 \
  dist/fullstack-engineering-kit-1.3.1.tar.gz \
  dist/fullstack-engineering-kit-1.3.1.tar.gz.sha256 \
  dist/fullstack-engineering-kit-cli-1.3.1.tgz \
  dist/fullstack-engineering-kit-cli-1.3.1.tgz.sha256 \
  dist/bootstrap.sh \
  --repo xuxiaofei820825/fullstack-engineering-kit \
  --verify-tag \
  --generate-notes \
  --title "v1.3.1"
```

手动发布前必须先将对应标签推送到远端。发布后仍需检查资产 URL，并执行一次实际安装验证。

## 常见问题

### 安装脚本返回 404

检查目标 Release 是否存在，以及 Release 中是否包含 `bootstrap.sh`。标签存在不代表 Release 资产已经上传。

### 工作流在 Create GitHub Release 失败

常见原因是同名 Release 已被提前手动创建。尚未正式发布时，可以删除空 Release 后重新运行发布任务；旧版本已经公开后，应递增版本号并创建新 Release，避免标签内容与重新构建的资产不一致。

### 标签版本检查失败

确认标签去掉前缀 `v` 后与 `VERSION` 完全一致。例如 `VERSION` 为 `1.3.1` 时，标签必须为 `v1.3.1`。

### 不要使用 main 或 latest 安装

安装器只接受明确的语义版本。固定版本可以确保压缩包、校验文件和安装脚本来自同一个不可变发布版本。
