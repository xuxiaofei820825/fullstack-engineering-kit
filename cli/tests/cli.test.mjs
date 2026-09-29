import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { chmodSync, existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repositoryRoot = fileURLToPath(new URL("../..", import.meta.url));
const cli = resolve(repositoryRoot, "cli/fullstack-engineering-kit.mjs");
const bundleVersion = readFileSync(resolve(repositoryRoot, "VERSION"), "utf8").trim();

function run(...args) {
  return spawnSync(process.execPath, [cli, ...args], {
    cwd: repositoryRoot,
    encoding: "utf8",
  });
}

function runAsync(args, environment = {}) {
  return new Promise((resolveRun) => {
    const child = spawn(process.execPath, [cli, ...args], {
      cwd: repositoryRoot,
      env: { ...process.env, ...environment },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8").on("data", (chunk) => { stdout += chunk; });
    child.stderr.setEncoding("utf8").on("data", (chunk) => { stderr += chunk; });
    child.on("close", (status) => resolveRun({ status, stdout, stderr }));
  });
}

function releaseFixture(targetVersion, validChecksum = true) {
  const temporary = mkdtempSync(resolve(tmpdir(), "fsek-release-fixture-"));
  const archive = Buffer.from("test CLI package");
  const checksum = validChecksum
    ? createHash("sha256").update(archive).digest("hex")
    : "0".repeat(64);
  const archiveName = `fullstack-engineering-kit-cli-${targetVersion}.tgz`;
  const archivePath = resolve(temporary, archiveName);
  const checksumPath = resolve(temporary, `${archiveName}.sha256`);
  const metadataPath = resolve(temporary, "release.json");
  writeFileSync(archivePath, archive);
  writeFileSync(checksumPath, `${checksum}  ${archiveName}\n`, "utf8");
  writeFileSync(metadataPath, JSON.stringify({
    tag_name: `v${targetVersion}`,
    assets: [
      { name: archiveName, fixture_path: archivePath },
      { name: `${archiveName}.sha256`, fixture_path: checksumPath },
    ],
  }), "utf8");
  return metadataPath;
}

test("prints help and version", () => {
  const help = run("--help");
  assert.equal(help.status, 0, help.stderr);
  assert.match(help.stdout, /init/);
  assert.match(help.stdout, /update/);

  const versionResult = run("version");
  assert.equal(versionResult.status, 0, versionResult.stderr);
  assert.equal(versionResult.stdout.trim(), `${bundleVersion} (bundle ${bundleVersion})`);
});

test("init installs the selected platform without creating project scripts", () => {
  const target = mkdtempSync(resolve(tmpdir(), "fsek-cli-init-"));
  const projectScript = resolve(target, "scripts-placeholder");
  writeFileSync(projectScript, "preserve\n", "utf8");

  const result = run("init", target, "--platform", "codex", "--skip-openspec");

  assert.equal(result.status, 0, result.stderr);
  assert.equal(
    readFileSync(resolve(target, ".fullstack-engineering-kit/installation.json"), "utf8")
      .includes('"platform": "codex"'),
    true,
  );
  assert.equal(
    readFileSync(resolve(target, ".codex/skills/full-stack-engineering-practices/SKILL.md"), "utf8")
      .includes("name: full-stack-engineering-practices"),
    true,
  );
  assert.equal(readFileSync(projectScript, "utf8"), "preserve\n");
});

test("update keeps the platform recorded during initialization", () => {
  const target = mkdtempSync(resolve(tmpdir(), "fsek-cli-update-"));
  const initialized = run("init", target, "--platform", "claude", "--skip-openspec");
  assert.equal(initialized.status, 0, initialized.stderr);

  const updated = run("update", target, "--skip-openspec");

  assert.equal(updated.status, 0, updated.stderr);
  assert.match(updated.stdout, /for claude/);
});

test("update rejects an uninitialized project before writing files", () => {
  const target = mkdtempSync(resolve(tmpdir(), "fsek-cli-uninitialized-"));

  const updated = run("update", target, "--platform", "codex");

  assert.equal(updated.status, 1);
  assert.match(updated.stderr, /尚未初始化 OpenSpec/);
  assert.equal(existsSync(resolve(target, ".fullstack-engineering-kit-version")), false);
});

test("non-interactive init requires an explicit or accepted platform", () => {
  const target = mkdtempSync(resolve(tmpdir(), "fsek-cli-platform-"));

  const result = run("init", target, "--skip-openspec");

  assert.equal(result.status, 2);
  assert.match(result.stderr, /非交互环境必须指定 --platform/);
});

test("verify delegates to the bundle verifier", () => {
  const target = mkdtempSync(resolve(tmpdir(), "fsek-cli-verify-"));
  assert.equal(
    run("init", target, "--platform", "agents", "--skip-openspec").status,
    0,
  );

  const verified = run("verify", target, "--files-only");

  assert.equal(verified.status, 0, verified.stderr);
  assert.match(verified.stdout, /安装验证通过/);
});

test("self-update verifies the release checksum before invoking npm", async () => {
  const [major, minor] = bundleVersion.split(".").map(Number);
  const targetVersion = `${major}.${minor + 1}.0`;
  const metadataPath = releaseFixture(targetVersion);
  const temporary = mkdtempSync(resolve(tmpdir(), "fsek-self-update-"));
  const npmLog = resolve(temporary, "npm.log");
  const fakeNpm = resolve(temporary, "npm-mock.mjs");
  writeFileSync(
    fakeNpm,
    `#!/usr/bin/env node\nimport { writeFileSync } from "node:fs";\nwriteFileSync(process.env.FSEK_UPDATE_LOG, process.argv.slice(2).join("\\n"));\n`,
    "utf8",
  );
  chmodSync(fakeNpm, 0o755);

  const result = await runAsync(
    ["self-update", "--repository", "company/project"],
    {
      FSEK_RELEASE_FIXTURE: metadataPath,
      FSEK_NPM: fakeNpm,
      FSEK_UPDATE_LOG: npmLog,
    },
  );

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, new RegExp(`CLI updated to ${targetVersion}`));
  assert.match(readFileSync(npmLog, "utf8"), /^install\n--global\n/);
});

test("self-update refuses a package whose checksum does not match", async () => {
  const [major, minor] = bundleVersion.split(".").map(Number);
  const targetVersion = `${major}.${minor + 1}.0`;
  const metadataPath = releaseFixture(targetVersion, false);

  const result = await runAsync(
    ["self-update", "--repository", "company/project"],
    { FSEK_RELEASE_FIXTURE: metadataPath },
  );

  assert.equal(result.status, 1);
  assert.match(result.stderr, /SHA-256 校验失败/);
});

test("self-update can check a specific version without invoking npm", async () => {
  const [major, minor] = bundleVersion.split(".").map(Number);
  const targetVersion = `${major}.${minor + 1}.0`;
  const metadataPath = releaseFixture(targetVersion);

  const result = await runAsync(
    ["self-update", "--version", targetVersion, "--check", "--repository", "company/project"],
    {
      FSEK_RELEASE_FIXTURE: metadataPath,
      FSEK_NPM: "/command/that/must/not/run",
    },
  );

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, new RegExp(`CLI update available: ${targetVersion}`));
});

test("self-update refuses downgrades unless force is explicit", async () => {
  const [major, minor] = bundleVersion.split(".").map(Number);
  const targetVersion = minor > 0 ? `${major}.${minor - 1}.0` : `${major - 1}.0.0`;
  const metadataPath = releaseFixture(targetVersion);

  const result = await runAsync(
    ["self-update", "--repository", "company/project"],
    { FSEK_RELEASE_FIXTURE: metadataPath },
  );

  assert.equal(result.status, 2);
  assert.match(result.stderr, /如需降级请使用 --force/);
});
