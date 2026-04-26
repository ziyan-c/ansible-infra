#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

export ANSIBLE_LOCAL_TEMP="${ANSIBLE_LOCAL_TEMP:-/tmp/ansible-local}"
export ANSIBLE_REMOTE_TEMP="${ANSIBLE_REMOTE_TEMP:-/tmp/ansible-remote}"
mkdir -p "$ANSIBLE_LOCAL_TEMP" "$ANSIBLE_REMOTE_TEMP"

tmp_dir="$(mktemp -d)"
cleanup() {
    rm -rf "$tmp_dir"
}
trap cleanup EXIT

scripts=()
while IFS= read -r script; do
    scripts+=("${script#./}")
done < <(
    find . -type f -name '*.sh' \
        -not -path './.git/*' \
        -not -path './.local/*' \
        -not -path './.ansible/*'
)

for script in "${scripts[@]}"; do
    bash -n "$script"
done

render_dir="$tmp_dir/rendered-shell"
TEST_RENDER_DIR="$render_dir" ansible-playbook \
    -i .local.example/inventory.yml \
    tests/render_shell_templates.yml >/dev/null

rendered_scripts=()
while IFS= read -r script; do
    rendered_scripts+=("$script")
done < <(find "$render_dir" -type f -name '*.sh')

for script in "${rendered_scripts[@]}"; do
    bash -n "$script"
done

if command -v shellcheck >/dev/null 2>&1; then
    shellcheck "${scripts[@]}"
    shellcheck "${rendered_scripts[@]}"
else
    echo "shellcheck not found; skipped shellcheck"
fi
