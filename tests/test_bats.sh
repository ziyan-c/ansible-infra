#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if command -v bats >/dev/null 2>&1; then
	bats tests/*.bats
else
	echo "bats not found; skipped Bats tests"
fi
