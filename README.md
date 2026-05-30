# Ansible Infra

[简体中文](README.zh-CN.md)

Personal Ansible playbooks for bootstrapping VPS nodes, building a WireGuard
mesh, deploying gateway services, and running app stacks such as Caddy,
Postgres, Mailcow, Zammad, Xray, and Cloudflared.

## Layout

- `site.yml`: main playbook, ordered as base, gateway, then app deployment.
- `roles/base`: system initialization, Docker setup, and WireGuard mesh.
- `roles/gateway`: Certbot certificate distribution and Caddy reverse proxy.
- `roles/apps`: application stacks and backup jobs.
- `.local/`: private inventory, vault password, shared host variables,
  per-role private variables under `role_vars/`, and rendered client files.
  This path is intentionally git-ignored.
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

Before running the playbook, make sure `.local/` contains the private inventory,
shared variables in `group_vars/all.yml`, and per-role private files under
`.local/role_vars/<role>/`, including SSH keys, WireGuard keys, Cloudflare
tokens, database passwords, Rclone config, and app-specific env templates.

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
git tag -a v0.2 -m "v0.2"
git push origin v0.2
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

## WireGuard Homelab Spokes

VPS nodes remain a full mesh. NAT or roaming machines, such as a homelab box
without a stable public IP, should be modeled as `wg_spoke_nodes` and assigned
to exactly one public VPS hub:

```yaml
wg_spoke_nodes:
  homelab:
    hub: fr
    ip_suffix: 6
    pub: "HOMELAB_PUBLIC_KEY"
    priv: "HOMELAB_PRIVATE_KEY"
    persistent_keepalive: 25

wg_preshared_keys:
  spoke_pairs:
    homelab__fr: "HOMELAB_FR_PSK"
```

Ansible updates the VPS configs so non-hub nodes route `10.66.0.6/32` through
the selected hub, while the hub accepts the homelab peer without requiring a
public `Endpoint`. It also writes the manual homelab config to
`.local/wg-spokes/homelab/homelab_via_fr.conf`; copy that config onto the
homelab machine and start `wg-quick@wg0` there. The spoke config routes only
the WireGuard CIDR through the hub by default, not all public Internet traffic.
It also omits `DNS` by default so local LAN/domain resolution on the homelab
machine stays untouched; set `dns:` on the spoke only if you really want
`wg-quick` to override DNS.

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


## Proxy Control Plane Deployment

This repo can also deploy the Go `proxy-control-plane` service itself. The role
pulls a versioned GHCR image on the target host, writes `/opt/proxy-control-plane`
runtime files, runs SQL migrations, and starts the API with Docker Compose.

Example private variables:

```yaml
proxy_control_plane_enabled: true
proxy_control_plane_image: "ghcr.io/ziyan-c/proxy-control-plane:0.2"
proxy_control_plane_bind_host: "10.66.0.10"
proxy_control_plane_host_port: 9710
proxy_control_plane_env_file_src: "{{ private_state_dir }}/role_vars/proxy_control_plane/app.env"
```

Create `.local/role_vars/proxy_control_plane/app.env` as a symlink to the real
`../proxy-control-plane/.local/app.env` file. The role copies that private env file to
`/opt/proxy-control-plane/app.env` with `0600` permissions, and Docker Compose
loads it through `env_file`. Put every `PCP_*` runtime setting in that env file,
including `PCP_LISTEN_ADDR=0.0.0.0:9710`, runtime sync, traffic sync, and
maintenance retention. Do not symlink or copy the whole `proxy-control-plane`
`.local/` directory into Ansible; Compose only needs the single env file.

Private GHCR images can be pulled by setting `proxy_control_plane_ghcr_username`
and `proxy_control_plane_ghcr_token`. Public GHCR images do not need a login.

## Proxy Control Plane Node Sync

This repo can register deployed Xray nodes back into the Go
`proxy-control-plane` service after the app roles finish. The sync is optional
and disabled by default. When enabled, Ansible collects hosts from
`xray_under_caddy_nodes` and `xray_nodes`, builds the client-facing node payload, and
calls `POST /admin/nodes/sync`. It does not write PostgreSQL directly.

Run this play from a host that can reach the control-plane API over WireGuard.
In the example inventory, `proxy_control_plane_sync_nodes` is the same host as
`proxy_control_plane_nodes`, so sync does not depend on the local laptop being
connected to the private mesh.

Required private variables live in the relevant role vars files:

```yaml
# .local/role_vars/proxy_control_plane/main.yml
proxy_control_plane_node_sync_enabled: true
proxy_control_plane_api_url: "https://control-plane.example.com"
proxy_control_plane_admin_email: "admin@example.com"
proxy_control_plane_admin_password: "..."

# .local/role_vars/xray/main.yml
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
xray_under_caddy_public_host: xray-under-caddy.example.com
```

If `proxy_control_plane_node_enabled` is omitted, Ansible leaves the field out
of `/admin/nodes/sync` so the control plane can preserve the existing enabled
state. Set it explicitly when you want inventory to manage node availability.

Runtime API management is also optional and disabled by default. When enabled,
Xray Reality and Xray under Caddy expose a gRPC management API only on the
configured WireGuard address. Static clients default to an empty list; managed
users are added by `proxy-control-plane` through the runtime API. Both roles use port
`10085` by default; each node binds that port on its own WireGuard IP. The API
enables both `HandlerService` for user reconciliation and `StatsService` for
traffic collection. The roles also render `stats: {}` plus user uplink/downlink
policy so `proxy-control-plane` can aggregate VLESS traffic through Xray's stats
API.

```yaml
proxy_control_plane_runtime_api_enabled: true
proxy_control_plane_runtime_api_host: "10.66.0.1"
proxy_control_plane_runtime_api_tag: proxy-control-plane-api
proxy_control_plane_runtime_inbound_tag: proxy-control-plane-vless-in
proxy_control_plane_xray_runtime_api_port: 10085
proxy_control_plane_xray_under_caddy_runtime_api_port: 10085
```

Set `proxy_control_plane_runtime_api_host` per host when different nodes have
different WireGuard IPs. Ansible registers these API fields with the control
plane; user add/remove reconciliation is still owned by `proxy-control-plane`.

Subscription publishing can also be delegated to the control plane. Caddy proxies
the public subscription path, `/xray/sub/{token}`, only on the main
`base_domain` site, while the Xray under Caddy domain stays focused on proxy
traffic and static fallback files. The long-term source of truth is still
PostgreSQL; Caddy rewrites the public path back to the control-plane upstream
path `/sub/{token}` and only forwards managed subscription-token requests.

```yaml
proxy_control_plane_subscription_proxy_enabled: true
proxy_control_plane_subscription_proxy_upstream: "http://10.66.0.10:9710"
proxy_control_plane_subscription_public_path: /xray/sub
```

Import old public files into the control plane first, then keep the static files
in place until client migration is complete. The current control-plane API only
serves managed subscriptions through `/sub/{token}`; Caddy exposes the public
`/xray/sub/{token}` path and rewrites it back to `/sub/{token}` for the
upstream. Legacy static paths should continue to be handled by Caddy's file
server rather than proxied.

## Safety Notes

- Several roles intentionally manage root-level host state such as SSH,
  firewalld, swap, Docker, cron, and service files.
- `roles/base/system_init/defaults/main.yml` exposes switches for high-impact
  host changes:
  - `system_apt_upgrade_mode` (`update_only`, `update_upgrade`, or
    `update_distupgrade`)
  - `system_disable_ufw_apparmor`
  - `root_authorized_keys_exclusive`
- Secret-bearing rendered files should stay owner-readable only (`0600`) or
  executable only by root where scripts require it.
- `collect_all_files.py` skips `.local/` so debugging bundles do not include
  private inventory, tokens, or key material.
