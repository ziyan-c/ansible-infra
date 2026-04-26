# Testing Workflow

This project should use a layered test flow. Most roles manage real VPS state,
so the default suite stays local and static. Container-backed Molecule scenarios
can be added later for the few roles that are worth the extra setup cost.

## Current Local Tools

Checked on this machine:

- Python: `python3` 3.14.4
- Pytest: `pytest` 9.0.3 is available as a command; `python3 -m pytest` is not
  available until pytest is installed into that interpreter.
- Ansible: `ansible-playbook` core 2.20.4
- Ansible Lint: `ansible-lint` 26.4.0
- Ansible Test: `ansible-test` 2.20.4
- Molecule: 26.4.0 with docker, containers, podman, vagrant, and cloud drivers
- Docker CLI/server: 29.4.0 / 29.4.0
- Docker Compose: v5.1.2
- ShellCheck: 0.11.0
- Bats: 1.13.0
- jq: 1.7.1
- hadolint: 2.14.0
- yamllint: 1.38.0
- yq: 4.53.2
- shfmt: 3.13.1

Not currently available in `PATH`:

- `podman`
- `colima`

Docker Desktop is selected as the active Docker context (`desktop-linux`) and
the daemon is running. In Codex's sandbox, Docker socket access requires an
approval step, but it should work from your normal terminal.

## Environment Rule

Use project-local Ansible temp/cache paths during tests:

```bash
export ANSIBLE_HOME="$PWD/.ansible"
export ANSIBLE_LOCAL_TEMP=/tmp/ansible-local
export ANSIBLE_REMOTE_TEMP=/tmp/ansible-remote
```

The `Makefile` and test scripts already set these values. This avoids failures
from tools trying to write to `~/.ansible`.

## Default Gate

Run this before committing:

```bash
make test
```

It runs:

- Python helper tests with standard-library `unittest`
- Bash syntax checks for committed `.sh` scripts
- Rendered Bash template checks for `.sh.j2` templates
- Bats behavior tests for local Bash helpers
- YAML formatting checks with `yamllint`
- Shell formatting checks with `shfmt` for committed `.sh` files
- Rendered JSON template checks with `jq`
- Rendered Docker Compose template checks with `docker compose config`
- Inventory and variable-contract checks for play groups, deploy nodes, and
  WireGuard node mappings
- Ansible inventory loading
- Ansible playbook syntax check
- `ansible-lint`

Run the extended suite, including Molecule:

```bash
make test-all
```

## Targeted Commands

Python helper tests:

```bash
make test-python
```

Pytest runner, useful when you want pytest output or fixtures:

```bash
make test-pytest
```

Bash scripts and rendered Bash templates:

```bash
make test-bash
```

Rendered config templates:

```bash
make test-templates
```

Format checks:

```bash
make test-format
```

Bats behavior tests:

```bash
make test-bats
```

Ansible static checks:

```bash
make test-ansible
```

Molecule scenario:

```bash
make test-molecule
```

Quick syntax-only Ansible check:

```bash
make syntax
```

Inventory parse check:

```bash
make inventory
```

Lint only:

```bash
make lint
```

## Molecule Strategy

Molecule is available through `make test-molecule` and included in
`make test-all`, but not in the faster `make test` gate. These roles touch
root-owned files, systemd, firewalld, Docker, cron, certificates, and host
networking, so full role convergence should be added one narrow role at a time.

The first scenario covers `roles/apps/v2ray` in template-only mode. It converges
the role against localhost, skips runtime Docker operations, validates
idempotence, checks the rendered JSON with `jq`, and checks the rendered compose
file with `docker compose config`.

Use this same pattern for narrow roles where container behavior is realistic:

- `roles/base/docker_setup`
- `roles/apps/v2ray`
- `roles/apps/xray`
- selected Docker Compose app roles after their templates are stable

Before running Molecule Docker scenarios:

```bash
docker ps
molecule --version
```

`docker ps` must succeed. If it fails with a missing Docker socket, start Docker
Desktop first.

A Molecule scenario should live under the role being tested, for example:

```text
roles/apps/xray/molecule/default/
  molecule.yml
  converge.yml
  verify.yml
```

Then run:

```bash
cd roles/apps/xray
ANSIBLE_HOME="$PWD/.ansible" molecule test -s default
```

## What To Add Next

The next useful tests are more Molecule scenarios for one narrow role at a time.
Start with roles whose behavior is mostly file/template oriented, then add
container convergence only when the role can realistically run in Docker.

Add Bats tests only for Bash scripts with real branching logic. Static `bash -n`
plus ShellCheck is enough for most rendered backup scripts.

`shfmt` is intentionally limited to committed `.sh` files. Rendered `.sh.j2`
templates still get `bash -n` and ShellCheck checks, but generated formatting is
not enforced because Jinja syntax and shfmt rewrites can fight each other.
