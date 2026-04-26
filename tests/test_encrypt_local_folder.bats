#!/usr/bin/env bats

setup() {
	TEST_REPO="$(mktemp -d)"
	FAKE_BIN="$TEST_REPO/fake-bin"
	mkdir -p "$FAKE_BIN"
	cp "$BATS_TEST_DIRNAME/../encrypt_.local_folder.sh" "$TEST_REPO/"

	cat >"$FAKE_BIN/ansible-vault" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [ "$1" != "encrypt" ]; then
    echo "unsupported ansible-vault command: $1" >&2
    exit 2
fi

input="$2"
shift 2
output=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --output)
            output="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

if [ -z "$output" ]; then
    echo "missing --output" >&2
    exit 2
fi

cp "$input" "$output"
EOF
	chmod +x "$FAKE_BIN/ansible-vault"
}

teardown() {
	rm -rf "$TEST_REPO"
}

@test "fails when .local is missing" {
	cd "$TEST_REPO"

	run env PATH="$FAKE_BIN:$PATH" ./encrypt_.local_folder.sh

	[ "$status" -eq 1 ]
	[[ "$output" == *"找不到 .local"* ]]
}

@test "archives local content and removes temporary archive" {
	cd "$TEST_REPO"
	mkdir .local
	printf 'secret-token\n' >.local/token.txt

	run env PATH="$FAKE_BIN:$PATH" ./encrypt_.local_folder.sh

	[ "$status" -eq 0 ]
	[ -s .local_encrypted.vault ]
	[ ! -e .local.tar.gz ]

	run tar -tzf .local_encrypted.vault
	[ "$status" -eq 0 ]
	[[ "$output" == *".local/token.txt"* ]]
}
