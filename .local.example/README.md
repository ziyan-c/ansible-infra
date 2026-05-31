# Private State Example

Copy this directory to `.local/`, then replace every `REPLACE_ME` placeholder
with real private values.

```bash
cp -R .local.example .local
chmod 600 .local/vault_password
```

Expected private files:

- `inventory.yml`: host inventory and group membership.
- `group_vars/all.yml`: shared infrastructure variables and node topology.
- `role_vars/caddy/main.yml`: Caddy-specific private variables.
- `role_vars/certbot/main.yml`: Certbot DNS credentials and certificate paths.
- `role_vars/cloudflared/main.yml`: Cloudflared tunnel token and image pin.
- `role_vars/docker_setup/main.yml`: Docker daemon policy.
- `role_vars/system_init/main.yml`: host initialization, SSH, swap, and rclone
  config.
- `role_vars/caddy/cf-certs/server.crt` and
  `role_vars/caddy/cf-certs/server.key`: Cloudflare origin cert pair copied by
  the Caddy role.
- `role_vars/logto/main.yml`: Logto IAM private variables.
- `role_vars/sftpgo/main.yml`: SFTPGo file portal private variables,
  including its optional GDrive mount and locally generated strong secrets.
- `role_vars/mailcow/main.yml` and `role_vars/mailcow/mailcow.conf.j2`:
  Mailcow private variables and rendered config template.
- `role_vars/postgres/main.yml`: Postgres image, credentials, and data paths.
- `role_vars/proxy_control_plane/main.yml` and
  `role_vars/proxy_control_plane/app.env`: Proxy Control Plane private
  variables and env file.
- `role_vars/zammad/main.yml` and `role_vars/zammad/zammad.env.j2`: Zammad
  private variables and `.env` template rendered to the target host.
- `role_vars/vpn_wireguard/main.yml`: WireGuard mesh, road-warrior clients,
  spoke nodes, and preshared keys.
- `role_vars/xray/main.yml`: Xray Reality image, clients, and Reality keys.
- `role_vars/xray_under_caddy/main.yml`: Xray under Caddy domain, image, and
  clients.
- `vault_password`: Ansible Vault password file referenced by `ansible.cfg`.

Keep the real `.local/` directory out of git.
