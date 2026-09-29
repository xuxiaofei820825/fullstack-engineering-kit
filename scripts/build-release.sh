#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -B "$script_dir/build_engineering_standards_release.py" "$@"
exec python3 -B "$script_dir/build_cli_package.py" "$@"
