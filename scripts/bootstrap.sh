#!/usr/bin/env bash
set -euo pipefail

package_name="fullstack-engineering-kit"
repository="${ENGINEERING_STANDARDS_GITHUB_REPOSITORY:-}"
target="."
version=""
update=false
dry_run=false
use_gh=false

usage() {
  echo "Usage: bootstrap.sh --repository OWNER/REPO --version VERSION [--target DIRECTORY] [--use-gh] [--update] [--dry-run]" >&2
}

while (($#)); do
  case "$1" in
    --version)
      version="${2:-}"
      shift 2
      ;;
    --target)
      target="${2:-}"
      shift 2
      ;;
    --repository)
      repository="${2:-}"
      shift 2
      ;;
    --use-gh)
      use_gh=true
      shift
      ;;
    --update)
      update=true
      shift
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: 未知参数：$1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: --version 必须是明确的语义版本，例如 1.0.0" >&2
  exit 2
fi
if [[ ! "$repository" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "ERROR: 必须通过 --repository 或 ENGINEERING_STANDARDS_GITHUB_REPOSITORY 提供 OWNER/REPO" >&2
  exit 2
fi
if [[ ! -d "$target" ]]; then
  echo "ERROR: 目标项目目录不存在：$target" >&2
  exit 2
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
  echo "ERROR: 安装编码规范需要 Python 3.9 或更高版本" >&2
  exit 2
fi
if [[ "$use_gh" == true ]]; then
  if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: --use-gh 需要已安装的 GitHub CLI" >&2
    exit 2
  fi
  if [[ -z "${GH_TOKEN:-}" && -z "${GITHUB_TOKEN:-}" ]] && ! gh auth status >/dev/null 2>&1; then
    echo "ERROR: GitHub CLI 尚未认证，请执行 gh auth login 或设置 GH_TOKEN" >&2
    exit 2
  fi
fi

temporary_dir="$(mktemp -d "${TMPDIR:-/tmp}/engineering-standards.XXXXXX")"
trap 'rm -rf "$temporary_dir"' EXIT

archive_name="${package_name}-${version}.tar.gz"
archive_path="$temporary_dir/$archive_name"
checksum_path="$temporary_dir/$archive_name.sha256"
download_asset() {
  local asset_name="$1"
  if [[ "$use_gh" == true ]]; then
    gh release download "v${version}" \
      --repo "$repository" \
      --pattern "$asset_name" \
      --output "$temporary_dir/$asset_name"
  else
    curl -fsSL --retry 3 \
      "https://github.com/${repository}/releases/download/v${version}/${asset_name}" \
      --output "$temporary_dir/$asset_name"
  fi
}

download_asset "$archive_name"
download_asset "$archive_name.sha256"

expected_checksum="$(awk 'NR == 1 { print $1 }' "$checksum_path")"
actual_checksum=""
if command -v sha256sum >/dev/null 2>&1; then
  actual_checksum="$(sha256sum "$archive_path" | awk '{ print $1 }')"
elif command -v shasum >/dev/null 2>&1; then
  actual_checksum="$(shasum -a 256 "$archive_path" | awk '{ print $1 }')"
else
  echo "ERROR: 找不到 sha256sum 或 shasum，无法校验发布包" >&2
  exit 1
fi
if [[ ! "$expected_checksum" =~ ^[0-9a-fA-F]{64}$ || "$actual_checksum" != "$expected_checksum" ]]; then
  echo "ERROR: 发布包 SHA-256 校验失败" >&2
  exit 1
fi

python3 -B - "$archive_path" "$temporary_dir" "${package_name}-${version}" <<'PY'
import os
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

archive_path = Path(sys.argv[1])
destination = Path(sys.argv[2])
expected_prefix = sys.argv[3]

with tarfile.open(archive_path, "r:gz") as archive:
    members = archive.getmembers()
    for member in members:
        path = PurePosixPath(member.name)
        if (
            not (member.isfile() or member.isdir())
            or len(path.parts) < (1 if member.isdir() else 2)
            or path.parts[0] != expected_prefix
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.as_posix() != member.name.rstrip("/")
        ):
            raise SystemExit(f"ERROR: 发布包包含不安全的路径或文件类型：{member.name}")
    for member in members:
        target = destination.joinpath(*PurePosixPath(member.name).parts)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise SystemExit(f"ERROR: 无法读取发布包文件：{member.name}")
        with source, target.open("wb") as output:
            shutil.copyfileobj(source, output)
        os.chmod(target, member.mode & 0o777)
PY
installer="$temporary_dir/${package_name}-${version}/scripts/install.sh"
if [[ ! -x "$installer" ]]; then
  echo "ERROR: 发布包中缺少可执行安装器" >&2
  exit 1
fi

install_arguments=("$target" --version "$version")
if [[ "$update" == true ]]; then
  install_arguments+=(--update)
fi
if [[ "$dry_run" == true ]]; then
  install_arguments+=(--dry-run)
fi
"$installer" "${install_arguments[@]}"

if [[ "$dry_run" == false ]]; then
  "$temporary_dir/${package_name}-${version}/scripts/verify-installation.sh" "$target" --files-only
fi
