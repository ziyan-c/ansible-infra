#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")" || exit 1

export ANSIBLE_LOCAL_TEMP="${ANSIBLE_LOCAL_TEMP:-/tmp/ansible-local}"
export ANSIBLE_REMOTE_TEMP="${ANSIBLE_REMOTE_TEMP:-/tmp/ansible-remote}"
mkdir -p "$ANSIBLE_LOCAL_TEMP" "$ANSIBLE_REMOTE_TEMP"

echo "📦 正在打包并加密 .local 文件夹..."

LOCAL_DIR=".local"
ARCHIVE=".local.tar.gz"
OUTPUT=".local_encrypted.vault"
TMP_OUTPUT="${OUTPUT}.tmp.$$"
LIST_FILE="$(mktemp)"

cleanup() {
    rm -f "$ARCHIVE" "$LIST_FILE" "$TMP_OUTPUT"
}
trap cleanup EXIT

if [ ! -d "$LOCAL_DIR" ]; then
    echo "❌ 找不到 .local 目录或符号链接目标不存在"
    exit 1
fi

LOCAL_REAL_PATH="$(cd "$LOCAL_DIR" && pwd -P)"
echo "🔒 实际打包目录: $LOCAL_REAL_PATH"

# -h 会跟随 .local 符号链接，归档内仍保留 .local 这个目录名。
tar -czhf "$ARCHIVE" "$LOCAL_DIR"

tar -tzf "$ARCHIVE" > "$LIST_FILE"
if ! grep -q '^\.local/.' "$LIST_FILE"; then
    echo "❌ 打包内容异常：归档里没有 .local 下的实际文件"
    exit 1
fi

# 2. 明确用 ansible-vault 加密刚刚生成的 tar 包（解决管道符 | 报错的问题）
ansible-vault encrypt "$ARCHIVE" \
    --output "$TMP_OUTPUT"

mv "$TMP_OUTPUT" "$OUTPUT"

echo "✅ 加密完成！已在根目录生成 .local_encrypted.vault"
