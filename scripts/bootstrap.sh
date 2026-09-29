#!/usr/bin/env bash
set -euo pipefail

package_name="fullstack-engineering-kit"
repository="${ENGINEERING_STANDARDS_GITHUB_REPOSITORY:-}"
repository="${FULLSTACK_ENGINEERING_KIT_GITHUB_REPOSITORY:-$repository}"
target="."
version=""
update=false
dry_run=false
use_gh=false
platform="codex"

usage() {
  echo "Usage: bootstrap.sh --repository OWNER/REPO --version VERSION [--target DIRECTORY] [--platform codex|claude|opencode] [--use-gh] [--update] [--dry-run]" >&2
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
    --platform)
      platform="${2:-}"
      shift 2
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
      echo "ERROR: Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: --version must be an explicit semantic version, for example 1.0.0" >&2
  exit 2
fi
if [[ ! "$repository" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "ERROR: Provide OWNER/REPO through --repository or FULLSTACK_ENGINEERING_KIT_GITHUB_REPOSITORY" >&2
  exit 2
fi
if [[ ! -d "$target" ]]; then
  echo "ERROR: Target project directory does not exist: $target" >&2
  exit 2
fi
if [[ "$platform" != "codex" && "$platform" != "claude" && "$platform" != "opencode" ]]; then
  echo "ERROR: --platform must be codex, claude, or opencode" >&2
  exit 2
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  echo "ERROR: Python 3.10 or later is required to install the engineering standards" >&2
  exit 2
fi
if [[ "$use_gh" == true ]]; then
  if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: --use-gh requires the GitHub CLI" >&2
    exit 2
  fi
  if [[ -z "${GH_TOKEN:-}" && -z "${GITHUB_TOKEN:-}" ]] && ! gh auth status >/dev/null 2>&1; then
    echo "ERROR: GitHub CLI is not authenticated; run gh auth login or set GH_TOKEN" >&2
    exit 2
  fi
fi

temporary_dir="$(mktemp -d "${TMPDIR:-/tmp}/fullstack-engineering-kit.XXXXXX")"
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
  echo "ERROR: sha256sum or shasum is required to verify the release archive" >&2
  exit 1
fi
if [[ ! "$expected_checksum" =~ ^[0-9a-fA-F]{64}$ || "$actual_checksum" != "$expected_checksum" ]]; then
  echo "ERROR: Release archive SHA-256 verification failed" >&2
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
            raise SystemExit(f"ERROR: Release archive contains an unsafe path or file type: {member.name}")
    for member in members:
        target = destination.joinpath(*PurePosixPath(member.name).parts)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise SystemExit(f"ERROR: Unable to read a release archive file: {member.name}")
        with source, target.open("wb") as output:
            shutil.copyfileobj(source, output)
        os.chmod(target, member.mode & 0o777)
PY
installer="$temporary_dir/${package_name}-${version}/scripts/install.sh"
if [[ ! -x "$installer" ]]; then
  echo "ERROR: Release archive does not contain an executable installer" >&2
  exit 1
fi

install_arguments=("$target" --version "$version" --platform "$platform")
if [[ "$update" == true ]]; then
  install_arguments+=(--update)
fi
if [[ "$dry_run" == true ]]; then
  install_arguments+=(--dry-run)
fi
"$installer" "${install_arguments[@]}"

if [[ "$dry_run" == false ]]; then
  "$temporary_dir/${package_name}-${version}/scripts/verify-installation.sh" \
    "$target" --files-only --platform "$platform"
fi
