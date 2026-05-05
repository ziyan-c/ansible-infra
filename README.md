# Ansible Infra

Personal Ansible playbooks for bootstrapping VPS nodes, building a WireGuard
mesh, deploying gateway services, and running app stacks such as Caddy,
Postgres, Mailcow, Zammad, V2Ray/Xray, and Cloudflared.

## Layout

- `site.yml`: main playbook, ordered as base, gateway, then app deployment.
- `roles/base`: system initialization, Docker setup, and WireGuard mesh.
- `roles/gateway`: Certbot certificate distribution and Caddy reverse proxy.
- `roles/apps`: application stacks and backup jobs.
- `.local/`: private inventory, vault password, host variables, certificates,
  and rendered client files. This path is intentionally git-ignored.
- `.local.example/`: committed skeleton showing the expected private-state
  shape without real secrets.
- `.local_encrypted.vault`: encrypted snapshot of `.local` for recovery.

## Bootstrap

Create private state from the example skeleton:

```bash
cp -R .local.example .local
chmod 600 .local/vault_password
```

Then replace every `REPLACE_ME` placeholder under `.local/` with real values.

Install the required Ansible collections:

```bash
ansible-galaxy collection install -r collections/requirements.yml
```

The default inventory and vault password are configured in `ansible.cfg`:

```ini
inventory = .local/inventory.yml
vault_password_file = .local/vault_password
```

Before running the playbook, make sure `.local/` contains the private inventory
and all variables referenced by the roles, including SSH keys, WireGuard keys,
Cloudflare tokens, database passwords, Rclone config, and app-specific env
templates.

## Common Commands

Check syntax without touching hosts:

```bash
ansible-playbook site.yml --syntax-check
```

Run the lightweight lint profile:

```bash
python3 -m pip install -r requirements-dev.txt
ansible-lint site.yml
```

The current lint profile starts at `min` in `.ansible-lint` so it can be adopted
without turning the existing personal-infra style into a wall of noise.

Run the local test suite:

```bash
make test
```

This checks Python helpers, committed Bash scripts, rendered Bash templates,
rendered JSON and Docker Compose templates, inventory contracts, formatting,
Ansible inventory loading, playbook syntax, and `ansible-lint`.

Run the extended suite, including Molecule:

```bash
make test-all
```

## Releases

GitHub Actions creates a release automatically whenever a tag is pushed. The
release job first runs `make test`, then publishes a source archive generated
from the tagged tree plus `SHA256SUMS`.

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

Tags containing `-alpha`, `-beta`, `-rc`, or `-pre` are marked as pre-releases.

Run everything:

```bash
ansible-playbook site.yml
```

Run one layer or service:

```bash
ansible-playbook site.yml --tags base
ansible-playbook site.yml --tags wireguard
ansible-playbook site.yml --tags caddy
ansible-playbook site.yml --tags postgres
ansible-playbook site.yml --tags zammad
```

## Private State Backup

Create or refresh the encrypted private-state bundle:

```bash
./encrypt_.local_folder.sh
```

`.local_encrypted.vault` is intended to be committed as encrypted ciphertext.
Keep `.local/` and `.local/vault_password` out of git; use a strong unique
vault password such as one generated with `openssl rand -base64 32`. Do not
paste rendered files from `.local/` into issue threads, logs, or generated
context dumps.


## Proxy Control Plane Node Sync

This repo can register deployed Xray and V2Ray nodes back into the Go
`proxy-control-plane` service after the app roles finish. The sync is optional
and disabled by default. When enabled, Ansible collects hosts from
`xray_nodes` and `v2ray_nodes`, builds the client-facing node payload, and calls
`POST /admin/nodes/sync`. It does not write PostgreSQL directly.

Required private variables in `.local/group_vars/all.yml`:

```yaml
proxy_control_plane_node_sync_enabled: true
proxy_control_plane_api_url: "https://control-plane.example.com"
proxy_control_plane_admin_email: "admin@example.com"
proxy_control_plane_admin_password: "..."
xray_public_key: "..."
```

You may use `proxy_control_plane_access_token` instead of the admin email and
password if you already have a valid bearer token. For Xray Reality,
`xray_private_key` remains the server-side value used by the Xray config, while
`xray_public_key` is the client-facing value sent to the control plane for
subscription generation.

Per-host overrides are supported in inventory or host vars:

```yaml
proxy_control_plane_node_name: xray-fr-1
proxy_control_plane_region: fr
proxy_control_plane_node_enabled: true
xray_public_host: node.example.com
v2ray_public_host: v2ray.example.com
```

Runtime API management is also optional and disabled by default. When enabled,
Xray and V2Ray keep their existing static users, but expose a gRPC management
API only on the configured WireGuard address. Xray uses port `10085` by default
and V2Ray uses `10086` so both roles can run on the same host.

```yaml
proxy_control_plane_runtime_api_enabled: true
proxy_control_plane_runtime_api_host: "10.66.0.1"
proxy_control_plane_runtime_api_tag: proxy-control-plane-api
proxy_control_plane_runtime_inbound_tag: proxy-control-plane-vless-in
proxy_control_plane_xray_runtime_api_port: 10085
proxy_control_plane_v2ray_runtime_api_port: 10086
```

Set `proxy_control_plane_runtime_api_host` per host when different nodes have
different WireGuard IPs. Ansible registers these API fields with the control
plane; user add/remove reconciliation is still owned by `proxy-control-plane`.

## Safety Notes

- Several roles intentionally manage root-level host state such as SSH,
  firewalld, swap, Docker, cron, and service files.
- `roles/base/system_init/defaults/main.yml` exposes switches for high-impact
  host changes:
  - `system_dist_upgrade_enabled`
  - `system_disable_ufw_apparmor`
  - `root_authorized_keys_exclusive`
- Secret-bearing rendered files should stay owner-readable only (`0600`) or
  executable only by root where scripts require it.
- `collect_all_files.py` skips `.local/` so debugging bundles do not include
  private inventory, tokens, or key material.
