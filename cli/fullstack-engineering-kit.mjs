#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { delimiter, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { emitKeypressEvents } from "node:readline";

const require = createRequire(import.meta.url);
const packageJson = require("../package.json");
const packageRoot = fileURLToPath(new URL("..", import.meta.url));
const installer = resolve(packageRoot, "scripts/install_engineering_standards.py");
const verifier = resolve(packageRoot, "scripts/verify_engineering_standards.py");
const bundledOpenSpec = resolve(
  packageRoot,
  "node_modules/.bin",
  process.platform === "win32" ? "openspec.cmd" : "openspec",
);
const bundleVersion = readFileSync(resolve(packageRoot, "VERSION"), "utf8").trim();
const platforms = [
  { id: "agents", label: "Shared .agents skills", directory: ".agents" },
  { id: "codex", label: "Codex", directory: ".codex" },
  { id: "claude", label: "Claude Code", directory: ".claude" },
];

class CliError extends Error {
  constructor(message, exitCode = 2) {
    super(message);
    this.exitCode = exitCode;
  }
}

function parseArguments(argv) {
  const command = argv[0] && !argv[0].startsWith("-") ? argv[0] : "help";
  const tokens = command === "help" ? argv : argv.slice(1);
  const options = {
    command,
    target: ".",
    platform: undefined,
    yes: false,
    force: false,
    dryRun: false,
    filesOnly: false,
    skipOpenSpec: false,
    noColor: false,
    check: false,
    repository: "xuxiaofei820825/fullstack-engineering-kit",
    targetVersion: undefined,
  };
  let targetAssigned = false;
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token === "--platform" || token === "-p") {
      const value = tokens[index + 1];
      if (!value) throw new CliError(`${token} 需要平台名称`);
      options.platform = value;
      index += 1;
    } else if (token === "--repository") {
      const value = tokens[index + 1];
      if (!value) throw new CliError("--repository 需要 OWNER/REPO");
      options.repository = value;
      index += 1;
    } else if (token === "--version" && command === "self-update") {
      const value = tokens[index + 1];
      if (!value) throw new CliError("--version 需要语义版本号");
      options.targetVersion = value;
      index += 1;
    } else if (token === "--check") {
      options.check = true;
    } else if (token === "--yes" || token === "-y") {
      options.yes = true;
    } else if (token === "--force") {
      options.force = true;
    } else if (token === "--dry-run") {
      options.dryRun = true;
    } else if (token === "--files-only") {
      options.filesOnly = true;
    } else if (token === "--skip-openspec") {
      options.skipOpenSpec = true;
    } else if (token === "--no-color") {
      options.noColor = true;
    } else if (token === "--help" || token === "-h") {
      options.command = "help";
    } else if (token === "--version" || token === "-V") {
      options.command = "version";
    } else if (token.startsWith("-")) {
      throw new CliError(`未知参数：${token}`);
    } else if (!targetAssigned) {
      options.target = token;
      targetAssigned = true;
    } else {
      throw new CliError(`多余参数：${token}`);
    }
  }
  return options;
}

function palette(enabled) {
  const wrap = (code) => (text) => (enabled ? `\u001B[${code}m${text}\u001B[0m` : text);
  return {
    cyan: wrap("36"),
    dim: wrap("2"),
    green: wrap("32"),
    red: wrap("31"),
    yellow: wrap("33"),
  };
}

function printWelcome(colors) {
  process.stdout.write(`
${colors.cyan("      ██╗")}
${colors.cyan("  ████████╗")}   Fullstack Engineering Kit
${colors.cyan("    ████╔═╝")}   ${colors.dim("OpenSpec-governed engineering workflow")}
${colors.cyan("  ████████╗")}
${colors.cyan("      ██╔═╝")}

`);
}

function commandAvailable(command, args = ["--version"]) {
  const result = spawnSync(command, args, { encoding: "utf8", stdio: "pipe" });
  return !result.error && result.status === 0;
}

function findPython() {
  const configured = process.env.FSEK_PYTHON;
  const candidates = configured ? [configured] : ["python3", "python"];
  for (const command of candidates) {
    const result = spawnSync(
      command,
      ["-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"],
      { stdio: "ignore" },
    );
    if (!result.error && result.status === 0) return command;
  }
  throw new CliError(
    "需要 Python 3.10 或更高版本。可通过 FSEK_PYTHON 指定解释器路径。",
  );
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd,
    encoding: "utf8",
    env: options.env,
    stdio: options.capture ? "pipe" : "inherit",
  });
  if (result.error) {
    throw new CliError(`无法执行 ${command}：${result.error.message}`, 1);
  }
  return result;
}

function readInstallation(target) {
  const path = resolve(target, ".fullstack-engineering-kit/installation.json");
  if (!existsSync(path)) return undefined;
  try {
    const metadata = JSON.parse(readFileSync(path, "utf8"));
    return platforms.some(({ id }) => id === metadata.platform) ? metadata : undefined;
  } catch {
    return undefined;
  }
}

function detectedPlatforms(target) {
  return platforms.filter(({ directory }) => existsSync(resolve(target, directory)));
}

async function selectPlatform(target, requested, assumeYes, allowInstalled) {
  if (requested) {
    if (!platforms.some(({ id }) => id === requested)) {
      throw new CliError(`不支持的平台：${requested}。可选值：agents、codex、claude`);
    }
    return requested;
  }

  const installed = allowInstalled ? readInstallation(target)?.platform : undefined;
  if (installed) return installed;
  const detected = detectedPlatforms(target);
  const preferred = detected[0]?.id ?? "agents";
  if (assumeYes) return preferred;
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    throw new CliError(
      "非交互环境必须指定 --platform agents|codex|claude，或使用 --yes 接受自动检测结果。",
    );
  }

  process.stdout.write(
    `Detected tool directories: ${
      detected.length ? detected.map(({ directory }) => directory).join(", ") : "none"
    }\n? Select a tool to set up\n`,
  );
  process.stdout.write("  ↑↓ navigate • Enter confirm • Ctrl+C cancel\n");
  let selectedIndex = platforms.findIndex(({ id }) => id === preferred);
  const render = (redraw = false) => {
    if (redraw) process.stdout.write(`\u001B[${platforms.length}A`);
    platforms.forEach((platform, index) => {
      const flags = [
        detected.some(({ id }) => id === platform.id) ? "detected" : "",
        platform.id === preferred ? "recommended" : "",
      ].filter(Boolean);
      const marker = index === selectedIndex ? "›" : " ";
      process.stdout.write(
        `\r\u001B[2K${marker} ${platform.label}${flags.length ? ` (${flags.join(", ")})` : ""}\n`,
      );
    });
  };
  render();
  emitKeypressEvents(process.stdin);
  const wasRaw = process.stdin.isRaw;
  process.stdin.setRawMode(true);
  process.stdin.resume();
  return new Promise((resolveSelection, rejectSelection) => {
    const finish = () => {
      process.stdin.off("keypress", onKeypress);
      process.stdin.setRawMode(Boolean(wasRaw));
      process.stdin.pause();
    };
    const onKeypress = (_character, key) => {
      if (key?.ctrl && key.name === "c") {
        finish();
        rejectSelection(new CliError("已取消。", 130));
      } else if (key?.name === "up") {
        selectedIndex = (selectedIndex - 1 + platforms.length) % platforms.length;
        render(true);
      } else if (key?.name === "down") {
        selectedIndex = (selectedIndex + 1) % platforms.length;
        render(true);
      } else if (key?.name === "return") {
        finish();
        process.stdout.write(`Selected: ${platforms[selectedIndex].label}\n\n`);
        resolveSelection(platforms[selectedIndex].id);
      }
    };
    process.stdin.on("keypress", onKeypress);
  });
}

function findOpenSpec() {
  const candidates = existsSync(bundledOpenSpec) ? [bundledOpenSpec, "openspec"] : ["openspec"];
  const command = candidates.find((candidate) => commandAvailable(candidate));
  if (command) return command;
  throw new CliError("找不到 OpenSpec 1.9.0，请重新安装 Fullstack Engineering Kit CLI。");
}

function installBundle(python, target, platform, options) {
  const args = ["-B", installer, target, "--version", bundleVersion, "--platform", platform];
  if (options.force || options.command === "update") args.push("--update");
  if (options.dryRun) args.push("--dry-run");
  const result = run(python, args);
  if (result.status !== 0) throw new CliError("规范套件安装失败。", result.status ?? 1);
}

async function initialize(options, colors) {
  const target = resolve(options.target);
  if (options.dryRun && !existsSync(target)) {
    throw new CliError(`dry-run 要求目标项目目录已经存在：${target}`);
  }
  mkdirSync(target, { recursive: true });
  if (readInstallation(target) && !options.force) {
    throw new CliError("该项目已经初始化。请使用 update，或使用 init --force 重新安装。");
  }
  const python = findPython();
  printWelcome(colors);
  const platform = await selectPlatform(target, options.platform, options.yes, false);
  process.stdout.write(`Target: ${target}\nTool:   ${platform}\n\n`);

  if (
    !options.dryRun
    && !options.skipOpenSpec
    && !existsSync(resolve(target, "openspec/config.yaml"))
  ) {
    const openSpec = findOpenSpec();
    const arguments_ = ["init", target, "--tools", platform, "--no-animation"];
    if (options.force) arguments_.push("--force");
    const result = run(openSpec, arguments_);
    if (result.status !== 0) throw new CliError("OpenSpec 初始化失败。", result.status ?? 1);
  }
  installBundle(python, target, platform, options);
  if (!options.dryRun) {
    process.stdout.write(
      colors.green(`\nInitialization complete. Run: fsek verify ${options.target}\n`),
    );
  }
}

async function update(options, colors) {
  const target = resolve(options.target);
  if (!existsSync(target)) throw new CliError(`目标项目目录不存在：${target}`);
  const python = findPython();
  const platform = await selectPlatform(target, options.platform, options.yes, true);
  printWelcome(colors);
  process.stdout.write(`Updating ${target} for ${platform}...\n\n`);
  let openSpec;
  if (!options.dryRun && !options.skipOpenSpec) {
    if (!existsSync(resolve(target, "openspec/config.yaml"))) {
      throw new CliError("目标项目尚未初始化 OpenSpec，请先运行 fsek init。", 1);
    }
    openSpec = findOpenSpec();
  }
  installBundle(python, target, platform, options);

  if (openSpec) {
    const result = run(openSpec, ["update", target]);
    if (result.status !== 0) throw new CliError("OpenSpec 指令更新失败。", result.status ?? 1);
  }
  if (!options.dryRun) process.stdout.write(colors.green("\nUpdate complete.\n"));
}

function verify(options) {
  const target = resolve(options.target);
  const python = findPython();
  const args = ["-B", verifier, target];
  if (options.filesOnly) args.push("--files-only");
  if (options.platform) args.push("--platform", options.platform);
  const openSpec = options.filesOnly ? undefined : findOpenSpec();
  const environment = openSpec && openSpec !== "openspec"
    ? { ...process.env, PATH: `${dirname(openSpec)}${delimiter}${process.env.PATH ?? ""}` }
    : process.env;
  const result = run(python, args, { env: environment });
  if (result.status !== 0) throw new CliError("验证失败。", result.status ?? 1);
}

function doctor(options, colors) {
  const target = resolve(options.target);
  const [nodeMajor, nodeMinor] = process.versions.node.split(".").map(Number);
  const checks = [
    ["Node.js >= 20.19", nodeMajor > 20 || (nodeMajor === 20 && nodeMinor >= 19)],
    ["Python >= 3.10", (() => { try { findPython(); return true; } catch { return false; } })()],
    ["OpenSpec", (() => { try { findOpenSpec(); return true; } catch { return false; } })()],
    ["Installation metadata", Boolean(readInstallation(target))],
  ];
  let failed = false;
  for (const [label, passed] of checks) {
    failed ||= !passed;
    process.stdout.write(`${passed ? colors.green("✓") : colors.red("✗")} ${label}\n`);
  }
  if (!failed) {
    try {
      verify({ ...options, filesOnly: true });
    } catch {
      failed = true;
    }
  }
  if (failed) throw new CliError("环境或安装状态存在问题。", 1);
}

function normalizedVersion(value) {
  const match = /^v?(\d+)\.(\d+)\.(\d+)$/.exec(value);
  if (!match) throw new CliError(`无效语义版本：${value}`);
  return match.slice(1).map(Number);
}

function compareVersions(left, right) {
  const leftParts = normalizedVersion(left);
  const rightParts = normalizedVersion(right);
  for (let index = 0; index < leftParts.length; index += 1) {
    if (leftParts[index] !== rightParts[index]) return leftParts[index] - rightParts[index];
  }
  return 0;
}

async function githubRequest(url, accept = "application/vnd.github+json") {
  const token = process.env.GH_TOKEN || process.env.GITHUB_TOKEN;
  const headers = {
    Accept: accept,
    "User-Agent": `fullstack-engineering-kit/${packageJson.version}`,
    "X-GitHub-Api-Version": "2022-11-28",
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  let response;
  try {
    response = await fetch(url, { headers, redirect: "follow" });
  } catch (error) {
    throw new CliError(`无法访问 GitHub Release：${error.message}`, 1);
  }
  if (!response.ok) {
    throw new CliError(`GitHub Release 请求失败：HTTP ${response.status}`, 1);
  }
  return response;
}

async function downloadAsset(asset, fixtureMode) {
  if (fixtureMode && asset.fixture_path) return readFileSync(asset.fixture_path);
  const downloadUrl = asset.url || asset.browser_download_url;
  if (!downloadUrl) throw new CliError(`Release asset ${asset.name} 缺少下载地址。`, 1);
  const response = await githubRequest(downloadUrl, "application/octet-stream");
  return Buffer.from(await response.arrayBuffer());
}

async function selfUpdate(options, colors) {
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(options.repository)) {
    throw new CliError("--repository 必须使用 OWNER/REPO 格式");
  }
  const apiBase = (process.env.FSEK_GITHUB_API_URL || "https://api.github.com").replace(/\/$/, "");
  const releasePath = options.targetVersion
    ? `releases/tags/v${normalizedVersion(options.targetVersion).join(".")}`
    : "releases/latest";
  process.stdout.write(`Checking ${options.repository} releases...\n`);
  const releaseFixture = process.env.FSEK_RELEASE_FIXTURE;
  let release;
  if (releaseFixture) {
    try {
      release = JSON.parse(readFileSync(releaseFixture, "utf8"));
    } catch (error) {
      throw new CliError(`无法读取 Release 测试数据：${error.message}`, 1);
    }
  } else {
    const releaseResponse = await githubRequest(
      `${apiBase}/repos/${options.repository}/${releasePath}`,
    );
    release = await releaseResponse.json();
  }
  const targetVersion = normalizedVersion(release.tag_name).join(".");
  if (
    options.targetVersion
    && normalizedVersion(options.targetVersion).join(".") !== targetVersion
  ) {
    throw new CliError(
      `请求版本 ${options.targetVersion}，但 Release 返回的是 ${release.tag_name}。`,
      1,
    );
  }
  const comparison = compareVersions(targetVersion, packageJson.version);
  process.stdout.write(`Current: ${packageJson.version}\nLatest:  ${targetVersion}\n`);
  if (options.check) {
    if (comparison > 0) {
      process.stdout.write(colors.yellow(`CLI update available: ${targetVersion}\n`));
    } else if (comparison === 0) {
      process.stdout.write(colors.green("CLI is already up to date.\n"));
    } else {
      process.stdout.write(colors.green("Installed CLI is newer than the selected Release.\n"));
    }
    return;
  }
  if (comparison === 0 && !options.force) {
    process.stdout.write(colors.green("CLI is already up to date.\n"));
    return;
  }
  if (comparison < 0 && !options.force) {
    throw new CliError(
      `目标版本 ${targetVersion} 低于当前版本 ${packageJson.version}；如需降级请使用 --force。`,
    );
  }
  const archiveName = `fullstack-engineering-kit-cli-${targetVersion}.tgz`;
  const checksumName = `${archiveName}.sha256`;
  const assets = Array.isArray(release.assets) ? release.assets : [];
  const archiveAsset = assets.find(({ name }) => name === archiveName);
  const checksumAsset = assets.find(({ name }) => name === checksumName);
  if (!archiveAsset || !checksumAsset) {
    throw new CliError(`Release v${targetVersion} 缺少 ${archiveName} 或校验文件。`, 1);
  }

  process.stdout.write(`Downloading ${archiveName}...\n`);
  const [archive, checksum] = await Promise.all([
    downloadAsset(archiveAsset, Boolean(releaseFixture)),
    downloadAsset(checksumAsset, Boolean(releaseFixture)),
  ]);
  const checksumText = checksum.toString("utf8");
  const checksumMatch = new RegExp(
    `^([0-9a-fA-F]{64})\\s+${archiveName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`,
    "m",
  ).exec(checksumText.trim());
  if (!checksumMatch) throw new CliError("Release SHA-256 文件格式无效。", 1);
  const actualChecksum = createHash("sha256").update(archive).digest("hex");
  if (actualChecksum.toLowerCase() !== checksumMatch[1].toLowerCase()) {
    throw new CliError("CLI 包 SHA-256 校验失败，已停止升级。", 1);
  }

  const temporaryDirectory = mkdtempSync(resolve(tmpdir(), "fullstack-engineering-kit-update-"));
  const archivePath = resolve(temporaryDirectory, archiveName);
  try {
    writeFileSync(archivePath, archive);
    const npm = process.env.FSEK_NPM || "npm";
    const result = run(npm, ["install", "--global", archivePath]);
    if (result.status !== 0) throw new CliError("npm 全局升级失败。", result.status ?? 1);
  } finally {
    rmSync(temporaryDirectory, { recursive: true, force: true });
  }
  process.stdout.write(
    colors.green(`CLI updated to ${targetVersion}. Run "fsek update" in each project.\n`),
  );
}

function printHelp() {
  process.stdout.write(`Fullstack Engineering Kit ${packageJson.version}

Usage:
  fullstack-engineering-kit <command> [target] [options]
  fsek <command> [target] [options]

Commands:
  init       初始化 OpenSpec 和工程规范
  update     升级项目中的工程规范并更新 OpenSpec 指令
  self-update 检查并升级全局 CLI
  verify     验证安装、schema 和 OpenSpec 产物
  doctor     检查运行环境和安装状态
  version    显示 CLI 与规范套件版本

Options:
  -p, --platform <name>  agents、codex 或 claude
  -y, --yes             接受检测到的平台或默认值
      --force           初始化时替换已有受管内容
      --dry-run         只显示将发生的安装变更
      --files-only      verify 只检查文件和配置
      --skip-openspec   不执行 openspec init/update
      --check           self-update 只检查可用版本
      --version <ver>   self-update 安装指定版本
      --repository <r>  Release 仓库，默认 xuxiaofei820825/fullstack-engineering-kit
      --no-color        禁用 ANSI 颜色
  -h, --help            显示帮助
`);
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  const colors = palette(!options.noColor && process.stdout.isTTY);
  switch (options.command) {
    case "init":
      await initialize(options, colors);
      break;
    case "update":
      await update(options, colors);
      break;
    case "self-update":
      await selfUpdate(options, colors);
      break;
    case "verify":
      verify(options);
      break;
    case "doctor":
      doctor(options, colors);
      break;
    case "version":
    case "--version":
    case "-V":
      process.stdout.write(`${packageJson.version} (bundle ${bundleVersion})\n`);
      break;
    case "help":
      printHelp();
      break;
    default:
      throw new CliError(`未知命令：${options.command}\n运行 fsek --help 查看可用命令。`);
  }
}

main().catch((error) => {
  const colors = palette(process.stderr.isTTY);
  process.stderr.write(`${colors.red("ERROR:")} ${error.message}\n`);
  process.exitCode = error.exitCode ?? 1;
});
