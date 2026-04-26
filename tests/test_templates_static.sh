#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

export ANSIBLE_LOCAL_TEMP="${ANSIBLE_LOCAL_TEMP:-/tmp/ansible-local}"
export ANSIBLE_REMOTE_TEMP="${ANSIBLE_REMOTE_TEMP:-/tmp/ansible-remote}"
export ANSIBLE_HOME="${ANSIBLE_HOME:-$PWD/.ansible}"
mkdir -p "$ANSIBLE_LOCAL_TEMP" "$ANSIBLE_REMOTE_TEMP" "$ANSIBLE_HOME"

tmp_dir="$(mktemp -d)"
cleanup() {
	rm -rf "$tmp_dir"
}
trap cleanup EXIT

render_dir="$tmp_dir/rendered-config"
TEST_RENDER_DIR="$render_dir" ansible-playbook \
	-i .local.example/inventory.yml \
	tests/render_config_templates.yml >/dev/null

if command -v jq >/dev/null 2>&1; then
	while IFS= read -r config; do
		jq -e . "$config" >/dev/null
	done < <(find "$render_dir/json" -type f -name '*.json')
else
	echo "jq not found; skipped JSON template validation"
fi

if command -v docker >/dev/null 2>&1; then
	export RAILS_TRUSTED_PROXIES='["127.0.0.1","172.16.0.0/12","172.18.0.0/16"]'
	export ZAMMAD_FQDN="support.example.com"
	export ZAMMAD_HTTP_TYPE="https"

	while IFS= read -r compose_file; do
		docker compose -f "$compose_file" config >/dev/null
	done < <(find "$render_dir/compose" -type f -name '*.yml')
else
	echo "docker not found; skipped docker compose template validation"
fi
