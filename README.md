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
- `.local_encrypted.vault`: encrypted snapshot of `.local` for recovery.

## Bootstrap

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

Keep `.local/` out of git. Do not paste rendered files from `.local/` into issue
threads, logs, or generated context dumps.

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
