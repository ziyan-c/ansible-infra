#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if command -v yamllint >/dev/null 2>&1; then
	yamllint -c .yamllint site.yml roles .local.example collections tests .github
else
	echo "yamllint not found; skipped YAML lint"
fi

dockerfiles=()
while IFS= read -r dockerfile; do
	dockerfiles+=("$dockerfile")
done < <(
	find . -type f \( -name 'Dockerfile' -o -name '*.Dockerfile' \) \
		-not -path './.git/*' \
		-not -path './.local/*' \
		-not -path './.ansible/*'
)

if [ "${#dockerfiles[@]}" -gt 0 ]; then
	if command -v hadolint >/dev/null 2>&1; then
		hadolint "${dockerfiles[@]}"
	else
		echo "hadolint not found; skipped Dockerfile lint"
	fi
fi
