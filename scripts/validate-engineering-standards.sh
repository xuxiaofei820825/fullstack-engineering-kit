#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$script_dir/.." && pwd)"

cd "$project_root"

openspec schema validate engineering-governed
openspec validate --changes --strict --no-interactive
python3 -B -m unittest discover -s "$script_dir/tests" -p "test_*.py"
python3 -B "$script_dir/validate_openspec_designs.py"
if [[ "$(basename "$script_dir")" == "scripts" ]]; then
  npm test
fi
