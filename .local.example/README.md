# Private State Example

Copy this directory to `.local/`, then replace every `REPLACE_ME` placeholder
with real private values.

```bash
cp -R .local.example .local
chmod 600 .local/vault_password
```

Expected private files:

- `inventory.yml`: host inventory and group membership.
- `group_vars/all.yml`: shared private variables consumed by the roles.
- `mailcow.conf.j2`: Mailcow config template rendered to the target host.
- `zammad.env.j2`: Zammad `.env` template rendered to the target host.
- `cf-certs/server.crt` and `cf-certs/server.key`: Cloudflare origin cert pair
  copied by the Caddy role.
- `vault_password`: Ansible Vault password file referenced by `ansible.cfg`.

Keep the real `.local/` directory out of git.
