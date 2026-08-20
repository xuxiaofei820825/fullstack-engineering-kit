#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$script_dir/.." && pwd)"

cd "$project_root"

openspec schema validate engineering-governed
openspec validate --all --strict --no-interactive
python3 -B -m unittest discover -s scripts/tests -p "test_*.py"
python3 -B scripts/validate_openspec_designs.py
