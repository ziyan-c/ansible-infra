# Tests

This repository starts with lightweight tests because most roles touch real VPS
state such as systemd, firewalld, Docker, cron, certificates, and root-owned
paths.

Run everything:

```bash
make test
```

Run the extended suite, including Molecule:

```bash
make test-all
```

The suite covers:

- Python unit tests for local helper scripts.
- Python behavior tests for Bash helper scripts.
- Python behavior tests for rendered backup and certificate sync scripts.
- Bash syntax checks for committed `.sh` files.
- Rendered Bash syntax checks for Ansible `.sh.j2` templates.
- YAML formatting checks with `yamllint`.
- Shell formatting checks with `shfmt` for committed `.sh` files.
- Rendered JSON template checks with `jq`.
- Rendered Docker Compose template checks with `docker compose config`.
- Inventory and variable-contract checks for play groups, deploy nodes, and
  WireGuard node mappings.
- `shellcheck` when it is installed locally.
- Ansible inventory loading, playbook syntax checks, and `ansible-lint`.
- A repository-wide Molecule template scenario plus role-level Molecule
  scenarios for V2ray, Xray, Cloudflared, and Neo Backend in `make test-all`.
