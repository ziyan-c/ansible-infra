# Tests

This repository starts with lightweight tests because most roles touch real VPS
state such as systemd, firewalld, Docker, cron, certificates, and root-owned
paths.

Run everything:

```bash
make test
```

The suite covers:

- Python unit tests for local helper scripts.
- Bash syntax checks for committed `.sh` files.
- Rendered Bash syntax checks for Ansible `.sh.j2` templates.
- `shellcheck` when it is installed locally.
- Ansible inventory loading, playbook syntax checks, and `ansible-lint`.
