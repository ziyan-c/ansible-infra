#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

export ANSIBLE_LOCAL_TEMP="${ANSIBLE_LOCAL_TEMP:-/tmp/ansible-local}"
export ANSIBLE_REMOTE_TEMP="${ANSIBLE_REMOTE_TEMP:-/tmp/ansible-remote}"
export ANSIBLE_HOME="${ANSIBLE_HOME:-$PWD/.ansible}"
export ANSIBLE_VAULT_PASSWORD_FILE="${ANSIBLE_VAULT_PASSWORD_FILE:-$PWD/.local.example/vault_password}"
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

assert_contains() {
	local file="$1"
	local expected="$2"
	grep -F "$expected" "$file" >/dev/null
}

if command -v jq >/dev/null 2>&1; then
	while IFS= read -r config; do
		jq -e . "$config" >/dev/null
	done < <(find "$render_dir/json" -type f -name '*.json')

	jq -e '.api.tag == "proxy-control-plane-api"' \
		"$render_dir/json/xray-under-caddy-config.json" >/dev/null
	jq -e '.api.tag == "proxy-control-plane-api"' \
		"$render_dir/json/xray-config.json" >/dev/null
	jq -e '.policy.levels["0"].statsUserUplink == true and .policy.levels["0"].statsUserDownlink == true' \
		"$render_dir/json/xray-under-caddy-config.json" >/dev/null
	jq -e '.policy.levels["0"].statsUserUplink == true and .policy.levels["0"].statsUserDownlink == true' \
		"$render_dir/json/xray-config.json" >/dev/null
	jq -e '.routing.rules[0].outboundTag == "proxy-control-plane-api"' \
		"$render_dir/json/xray-under-caddy-config.json" >/dev/null
	jq -e '.routing.rules[0].outboundTag == "proxy-control-plane-api"' \
		"$render_dir/json/xray-config.json" >/dev/null
	jq -e '.inbounds[0].tag == "proxy-control-plane-vless-in"' \
		"$render_dir/json/xray-under-caddy-config.json" >/dev/null
	jq -e '.inbounds[0].tag == "proxy-control-plane-vless-in"' \
		"$render_dir/json/xray-config.json" >/dev/null
	jq -e '.inbounds[0].settings.clients == []' \
		"$render_dir/json/xray-under-caddy-config.json" >/dev/null
	jq -e '.inbounds[0].settings.clients == []' \
		"$render_dir/json/xray-config.json" >/dev/null
	jq -e '.inbounds[1].protocol == "dokodemo-door" and .inbounds[1].port == 10085' \
		"$render_dir/json/xray-under-caddy-config.json" >/dev/null
	jq -e '.inbounds[1].protocol == "dokodemo-door" and .inbounds[1].port == 10085' \
		"$render_dir/json/xray-config.json" >/dev/null
	jq -e '.inbounds[0].streamSettings.wsSettings.path == "/v2ray"' \
		"$render_dir/json/xray-under-caddy-config.json" >/dev/null
	jq -e '.inbounds[0].streamSettings.security == "reality"' \
		"$render_dir/json/xray-config.json" >/dev/null
	jq -e '.inbounds[0].streamSettings.realitySettings.dest == "www.example.com:443"' \
		"$render_dir/json/xray-config.json" >/dev/null
else
	echo "jq not found; skipped JSON template validation"
fi

assert_contains "$render_dir/caddy/vps-a.Caddyfile" "example.com {"
assert_contains "$render_dir/caddy/vps-a.Caddyfile" "xray-under-caddy.example.com {"
assert_contains "$render_dir/caddy/vps-a.Caddyfile" "handle /api/rag*"
assert_contains "$render_dir/caddy/vps-a.Caddyfile" "reverse_proxy neo-backend:8000"
assert_contains "$render_dir/caddy/vps-a.Caddyfile" "handle_path /sub/*"
assert_contains "$render_dir/caddy/vps-a.Caddyfile" "rewrite * /sub{uri}"
assert_contains "$render_dir/caddy/vps-a.Caddyfile" "reverse_proxy http://10.66.0.10:9710"
assert_contains "$render_dir/compose/neo_backend.yml" '"10.66.0.1:8000:8000"'
assert_contains "$render_dir/compose/neo_backend.yml" '"10.66.0.1:8080:8080"'
assert_contains "$render_dir/compose/proxy-control-plane.yml" \
	"ghcr.io/ziyan-c/proxy-control-plane:0.1.1"
assert_contains "$render_dir/compose/proxy-control-plane.yml" \
	'"127.0.0.1:9710:9710"'
assert_contains "$render_dir/caddy/vps-b.Caddyfile" "support.example.com {"
assert_contains "$render_dir/compose/zammad.yml" \
	'command: ["/bin/sh", "-lc", "sleep infinity"]'
assert_contains "$render_dir/compose/zammad.yml" \
	"./backup_config:/opt/zammad/contrib/backup/config:ro"
assert_contains "$render_dir/certbot/cloudflare.ini" \
	"dns_cloudflare_api_token = REPLACE_ME_CLOUDFLARE_DNS_API_TOKEN"
assert_contains "$render_dir/wireguard/wg0.conf" "Address = 10.66.0.1/24"
assert_contains "$render_dir/wireguard/wg0.conf" "Endpoint = vps-b.example.com:51820"
assert_contains "$render_dir/wireguard/wg0.conf" "AllowedIPs = 10.66.0.2/32"
assert_contains "$render_dir/wireguard/wg0.conf" \
	"PresharedKey = REPLACE_ME_WG_PSK_VPS_A_VPS_B"
assert_contains "$render_dir/wireguard/wg0.conf" \
	"PresharedKey = REPLACE_ME_WG_PSK_PHONE_VPS_A"
assert_contains "$render_dir/wireguard/client_phone_vps_a.conf" \
	"Endpoint = vps-a.example.com:51820"
assert_contains "$render_dir/wireguard/client_phone_vps_a.conf" \
	"PresharedKey = REPLACE_ME_WG_PSK_PHONE_VPS_A"
assert_contains "$render_dir/wireguard/client_phone_vps_a.conf" \
	"AllowedIPs = 0.0.0.0/0, ::/0"

if command -v docker >/dev/null 2>&1; then
	export RAILS_TRUSTED_PROXIES='["127.0.0.1","172.16.0.0/12","172.18.0.0/16"]'
	export ZAMMAD_FQDN="support.example.com"
	export ZAMMAD_HTTP_TYPE="https"
	mkdir -p "$render_dir/compose/app"
	printf 'FROM scratch\n' >"$render_dir/compose/app/Dockerfile"
	touch "$render_dir/compose/.env"
	touch "$render_dir/compose/app.env"

	while IFS= read -r compose_file; do
		docker compose -f "$compose_file" config >/dev/null
	done < <(find "$render_dir/compose" -type f -name '*.yml')
else
	echo "docker not found; skipped docker compose template validation"
fi
