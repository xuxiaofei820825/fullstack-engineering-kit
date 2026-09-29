#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  renameSync,
  rmdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
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
  { id: "codex", label: "Codex", directory: ".codex" },
  { id: "claude", label: "Claude Code", directory: ".claude" },
  { id: "opencode", label: "OpenCode", directory: ".opencode" },
];
const openSpecSkillNames = [
  "openspec-explore",
  "openspec-new-change",
  "openspec-continue-change",
  "openspec-apply-change",
  "openspec-update-change",
  "openspec-ff-change",
  "openspec-sync-specs",
  "openspec-archive-change",
  "openspec-bulk-archive-change",
  "openspec-verify-change",
  "openspec-onboard",
  "openspec-propose",
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
      if (!value) throw new CliError(`${token} requires a platform name.`);
      options.platform = value;
      index += 1;
    } else if (token === "--repository") {
      const value = tokens[index + 1];
      if (!value) throw new CliError("--repository requires OWNER/REPO.");
      options.repository = value;
      index += 1;
    } else if (token === "--version" && command === "self-update") {
      const value = tokens[index + 1];
      if (!value) throw new CliError("--version requires a semantic version.");
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
      throw new CliError(`Unknown option: ${token}`);
    } else if (!targetAssigned) {
      options.target = token;
      targetAssigned = true;
    } else {
      throw new CliError(`Unexpected argument: ${token}`);
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
    "Python 3.10 or later is required. Set FSEK_PYTHON to specify the interpreter.",
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
    throw new CliError(`Unable to run ${command}: ${result.error.message}`, 1);
  }
  return result;
}

function readInstallation(target) {
  const path = resolve(target, ".fullstack-engineering-kit/installation.json");
  if (!existsSync(path)) return undefined;
  try {
    const metadata = JSON.parse(readFileSync(path, "utf8"));
    if (metadata.platform === "agents") {
      return { ...metadata, platform: "codex", migratedFrom: "agents" };
    }
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
      throw new CliError(`Unsupported platform: ${requested}. Choose codex, claude, or opencode.`);
    }
    return requested;
  }

  const installed = allowInstalled ? readInstallation(target)?.platform : undefined;
  if (installed) return installed;
  const detected = detectedPlatforms(target);
  const preferred = detected[0]?.id ?? "codex";
  if (assumeYes) return preferred;
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    throw new CliError(
      "Non-interactive environments require --platform codex|claude|opencode, or --yes to accept automatic detection.",
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
        rejectSelection(new CliError("Cancelled.", 130));
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
  const configured = process.env.FSEK_OPENSPEC;
  const candidates = configured
    ? [configured]
    : existsSync(bundledOpenSpec) ? [bundledOpenSpec, "openspec"] : ["openspec"];
  const command = candidates.find((candidate) => commandAvailable(candidate));
  if (command) return command;
  throw new CliError("OpenSpec 1.9.0 was not found. Reinstall the Fullstack Engineering Kit CLI.");
}

function removeEmptyDirectory(path) {
  try {
    rmdirSync(path);
  } catch (error) {
    if (error.code !== "ENOENT" && error.code !== "ENOTEMPTY") throw error;
  }
}

function relocateCodexOpenSpecSkills(target) {
  const agentsSkills = resolve(target, ".agents/skills");
  const marker = resolve(agentsSkills, ".openspec-target");
  const markerOwner = existsSync(marker) ? readFileSync(marker, "utf8").trim() : undefined;
  const inferredCodexOwner = openSpecSkillNames.some((name) => {
    const skill = resolve(agentsSkills, name, "SKILL.md");
    return existsSync(skill) && readFileSync(skill, "utf8").includes("$openspec-");
  });
  const codexOwned = markerOwner ? markerOwner === "codex" : inferredCodexOwner;
  if (!codexOwned) return;

  const codexSkills = resolve(target, ".codex/skills");
  mkdirSync(codexSkills, { recursive: true });
  let moved = 0;
  for (const name of openSpecSkillNames) {
    const source = resolve(agentsSkills, name);
    if (!existsSync(source)) continue;
    const destination = resolve(codexSkills, name);
    rmSync(destination, { recursive: true, force: true });
    renameSync(source, destination);
    moved += 1;
  }
  if (markerOwner === "codex") rmSync(marker, { force: true });
  removeEmptyDirectory(agentsSkills);
  removeEmptyDirectory(resolve(target, ".agents"));
  if (moved > 0) {
    process.stdout.write(`Moved ${moved} OpenSpec skill(s) to .codex/skills.\n`);
  }
}

function installBundle(python, target, platform, options) {
  const args = ["-B", installer, target, "--version", bundleVersion, "--platform", platform];
  if (options.force || options.command === "update") args.push("--update");
  if (options.dryRun) args.push("--dry-run");
  const result = run(python, args);
  if (result.status !== 0) throw new CliError("The engineering kit installation failed.", result.status ?? 1);
}

async function initialize(options, colors) {
  const target = resolve(options.target);
  if (options.dryRun && !existsSync(target)) {
    throw new CliError(`Dry run requires an existing target directory: ${target}`);
  }
  mkdirSync(target, { recursive: true });
  if (readInstallation(target) && !options.force) {
    throw new CliError("This project is already initialized. Use update, or init --force to reinstall.");
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
    if (result.status !== 0) throw new CliError("OpenSpec initialization failed.", result.status ?? 1);
    if (platform === "codex") relocateCodexOpenSpecSkills(target);
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
  if (!existsSync(target)) throw new CliError(`Target project directory does not exist: ${target}`);
  const python = findPython();
  const platform = await selectPlatform(target, options.platform, options.yes, true);
  printWelcome(colors);
  process.stdout.write(`Updating ${target} for ${platform}...\n\n`);
  let openSpec;
  if (!options.dryRun && !options.skipOpenSpec) {
    if (!existsSync(resolve(target, "openspec/config.yaml"))) {
      throw new CliError("OpenSpec is not initialized in the target project. Run fsek init first.", 1);
    }
    openSpec = findOpenSpec();
  }
  installBundle(python, target, platform, options);

  if (openSpec) {
    const result = run(openSpec, ["update", target]);
    if (result.status !== 0) throw new CliError("OpenSpec instruction update failed.", result.status ?? 1);
    if (platform === "codex") relocateCodexOpenSpecSkills(target);
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
  if (result.status !== 0) throw new CliError("Verification failed.", result.status ?? 1);
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
  if (failed) throw new CliError("The environment or installation has problems.", 1);
}

function normalizedVersion(value) {
  const match = /^v?(\d+)\.(\d+)\.(\d+)$/.exec(value);
  if (!match) throw new CliError(`Invalid semantic version: ${value}`);
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
    throw new CliError(`Unable to access the GitHub Release: ${error.message}`, 1);
  }
  if (!response.ok) {
    throw new CliError(`GitHub Release request failed: HTTP ${response.status}`, 1);
  }
  return response;
}

async function downloadAsset(asset, fixtureMode) {
  if (fixtureMode && asset.fixture_path) return readFileSync(asset.fixture_path);
  const downloadUrl = asset.url || asset.browser_download_url;
  if (!downloadUrl) throw new CliError(`Release asset ${asset.name} has no download URL.`, 1);
  const response = await githubRequest(downloadUrl, "application/octet-stream");
  return Buffer.from(await response.arrayBuffer());
}

async function selfUpdate(options, colors) {
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(options.repository)) {
    throw new CliError("--repository must use the OWNER/REPO format.");
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
      throw new CliError(`Unable to read Release fixture data: ${error.message}`, 1);
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
      `Requested ${options.targetVersion}, but the Release returned ${release.tag_name}.`,
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
      `Target version ${targetVersion} is older than the current version ${packageJson.version}. Use --force to downgrade.`,
    );
  }
  const archiveName = `fullstack-engineering-kit-cli-${targetVersion}.tgz`;
  const checksumName = `${archiveName}.sha256`;
  const assets = Array.isArray(release.assets) ? release.assets : [];
  const archiveAsset = assets.find(({ name }) => name === archiveName);
  const checksumAsset = assets.find(({ name }) => name === checksumName);
  if (!archiveAsset || !checksumAsset) {
    throw new CliError(`Release v${targetVersion} is missing ${archiveName} or its checksum file.`, 1);
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
  if (!checksumMatch) throw new CliError("The Release SHA-256 file has an invalid format.", 1);
  const actualChecksum = createHash("sha256").update(archive).digest("hex");
  if (actualChecksum.toLowerCase() !== checksumMatch[1].toLowerCase()) {
    throw new CliError("CLI package SHA-256 verification failed. The update was stopped.", 1);
  }

  const temporaryDirectory = mkdtempSync(resolve(tmpdir(), "fullstack-engineering-kit-update-"));
  const archivePath = resolve(temporaryDirectory, archiveName);
  try {
    writeFileSync(archivePath, archive);
    const npm = process.env.FSEK_NPM || "npm";
    const result = run(npm, ["install", "--global", archivePath]);
    if (result.status !== 0) throw new CliError("The global npm update failed.", result.status ?? 1);
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
  init        Initialize OpenSpec and the engineering standards
  update      Update the engineering standards and OpenSpec instructions
  self-update Check and update the globally installed CLI
  verify      Verify the installation, schema, and OpenSpec artifacts
  doctor      Check the environment and installation status
  version     Show the CLI and bundled kit versions

Options:
  -p, --platform <name>  codex, claude, or opencode
  -y, --yes              Accept the detected platform or default
      --force            Replace managed content during initialization
      --dry-run          Show installation changes without writing files
      --files-only       Verify files and configuration only
      --skip-openspec    Skip openspec init/update
      --check            Check for a self-update without installing it
      --version <ver>    Install a specific CLI version during self-update
      --repository <r>   Release repository; defaults to xuxiaofei820825/fullstack-engineering-kit
      --no-color         Disable ANSI colors
  -h, --help             Show help
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
      throw new CliError(`Unknown command: ${options.command}\nRun fsek --help to see available commands.`);
  }
}

main().catch((error) => {
  const colors = palette(process.stderr.isTTY);
  process.stderr.write(`${colors.red("ERROR:")} ${error.message}\n`);
  process.exitCode = error.exitCode ?? 1;
});
