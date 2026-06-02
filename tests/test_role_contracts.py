from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_role_file(path):
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def assert_site_uses_recursive_role_vars(site):
    assert "pre_tasks: &load_role_vars" in site
    assert "pre_tasks: *load_role_vars" in site
    assert "ansible.builtin.include_vars" in site
    assert 'dir: "{{ ansible_local_role_vars_dir }}"' in site
    assert "ignore_unknown_extensions: true" in site
    assert "- always" in site


def test_ssh_restart_handler_uses_explicit_service_detection():
    handler = read_role_file("roles/base/system_init/handlers/main.yml")

    assert "ansible.builtin.service_facts" in handler
    assert "ssh.service" in handler
    assert "sshd.service" in handler
    assert "ignore_errors" not in handler


def test_certbot_sync_only_treats_confirmed_missing_edge_certs_as_missing():
    tasks = read_role_file("roles/gateway/certbot/tasks/main.yml")

    sync_task = tasks.split(
        "- name: 立即执行一次证书同步 (仅当主节点刚申请，或边缘节点确实丢失时触发)",
        maxsplit=1,
    )[1]

    assert "selectattr('stat.exists', 'defined')" in sync_task
    assert "selectattr('stat.exists', 'equalto', false)" in sync_task
    assert "rejectattr('stat.exists', 'defined')" not in sync_task
    assert "ignore_unreachable: true" in tasks


def test_logto_retention_uses_postgres_delegate_and_cron_file():
    tasks = read_role_file("roles/apps/logto/tasks/main.yml")
    defaults = read_role_file("roles/apps/logto/defaults/main.yml")
    script = read_role_file("roles/apps/logto/templates/logto_retention_cleanup.sh.j2")

    assert "logto_retention_enabled: true" in defaults
    assert 'logto_retention_project_dir: "{{ logto_project_dir }}/retention"' in defaults
    assert 'logto_retention_cron_minute: "55"' in defaults
    assert "logto_sentinel_activity_retention_days: 30" in defaults
    assert "delegate_to: \"{{ logto_postgres_delegate_host }}\"" in tasks
    assert "run_once: true" in tasks
    assert "cron_file: \"{{ logto_retention_cron_file }}\"" in tasks
    assert "public.passcodes" in script
    assert ":passcode_days" in script
    assert "public.application_secrets" not in script
    assert "public.personal_access_tokens" not in script


def test_rclone_config_update_requires_explicit_force_flag():
    defaults = read_role_file("roles/base/system_init/defaults/main.yml")
    tasks = read_role_file("roles/base/system_init/tasks/main.yml")
    system_role_vars = read_role_file(".local.example/role_vars/base/system_init/main.yml")

    assert "rclone_config_force_update: false" in defaults
    assert "rclone_config_force_update: false" in system_role_vars
    assert 'force: "{{ rclone_config_force_update | bool }}"' in tasks


def test_sftpgo_gdrive_mount_is_role_scoped_and_systemd_managed():
    system_defaults = read_role_file("roles/base/system_init/defaults/main.yml")
    system_tasks = read_role_file("roles/base/system_init/tasks/main.yml")
    defaults = read_role_file("roles/apps/sftpgo/defaults/main.yml")
    tasks = read_role_file("roles/apps/sftpgo/tasks/main.yml")
    service = read_role_file("roles/apps/sftpgo/templates/rclone-gdrive.service.j2")
    system_role_vars = read_role_file(".local.example/role_vars/base/system_init/main.yml")
    sftpgo_role_vars = read_role_file(".local.example/role_vars/apps/sftpgo/main.yml")

    assert "rclone_gdrive_mount_enabled" not in system_defaults
    assert "rclone_gdrive_mount_enabled" not in system_role_vars
    assert "rclone-gdrive.service.j2" not in system_tasks
    assert "sftpgo_gdrive_mount_enabled: true" in defaults
    assert "sftpgo_gdrive_mount_enabled: true" in sftpgo_role_vars
    assert "sftpgo_gdrive_mount_point: /mnt/gdrive" in defaults
    assert 'sftpgo_gdrive_mount_remote: "gdrive:"' in defaults
    assert "sftpgo_gdrive_storage_subdir: SFTPGO-STORAGE" in defaults
    assert 'sftpgo_storage_dir: "{{ sftpgo_gdrive_mount_point }}/{{ sftpgo_gdrive_storage_subdir }}"' in defaults
    assert "sftpgo_gdrive_mount_service_name: rclone-gdrive" in defaults
    assert "安装 SFTPGo GDrive mount 依赖" in tasks
    assert "- fuse3" in tasks
    assert "检查 Rclone 配置是否存在" in tasks
    assert "/root/.config/rclone/rclone.conf" in tasks
    assert "允许 SFTPGo GDrive mount 被容器用户读取" in tasks
    assert "user_allow_other" in tasks
    assert "rclone mkdir {{ sftpgo_gdrive_storage_remote }}" in tasks
    assert "下发 SFTPGo GDrive mount systemd unit" in tasks
    assert "确认 SFTPGo GDrive 已挂载" in tasks
    assert "findmnt -rn {{ sftpgo_gdrive_mount_point }}" in tasks
    assert "创建 SFTPGo GDrive 主存储目录" in tasks
    assert "mkdir -p {{ sftpgo_storage_dir }} {{ sftpgo_storage_dir }}/data {{ sftpgo_storage_dir }}/backups" in tasks
    assert "移除旧的 SFTPGo GDrive mount 文件日志轮转" in tasks
    assert "sftpgo_gdrive_mount_log_file" not in defaults
    assert "sftpgo_gdrive_mount_logrotate_keep" not in defaults
    assert "when: sftpgo_gdrive_mount_enabled | bool" in tasks
    assert "rclone mount {{ sftpgo_gdrive_mount_remote }} {{ sftpgo_gdrive_mount_point }}" in service
    assert "--log-file" not in service
    assert "StandardOutput=journal" in service
    assert "StandardError=journal" in service
    assert "--vfs-cache-mode=writes" in defaults
    assert "--poll-interval=1m" in defaults
    assert "--uid={{ sftpgo_owner_uid }}" in defaults
    assert "--gid={{ sftpgo_owner_gid }}" in defaults
    assert "--umask=002" in defaults
    assert "--drive-skip-gdocs" in defaults


def test_system_init_apt_upgrade_mode_separates_update_upgrade_and_dist_upgrade():
    defaults = read_role_file("roles/base/system_init/defaults/main.yml")
    tasks = read_role_file("roles/base/system_init/tasks/main.yml")
    system_role_vars = read_role_file(".local.example/role_vars/base/system_init/main.yml")

    assert "system_apt_upgrade_mode:" in defaults
    assert "update_only" in defaults
    assert "update_upgrade" in defaults
    assert "update_distupgrade" in defaults

    assert "system_apt_upgrade_mode: update_upgrade" in system_role_vars

    assert "更新 APT 缓存" in tasks
    assert "普通升级系统包 (apt upgrade)" in tasks
    assert "大升级系统包 (apt dist-upgrade)" in tasks
    assert "upgrade: yes" in tasks
    assert "upgrade: dist" in tasks
    assert "system_apt_upgrade_mode == 'update_upgrade'" in tasks
    assert "system_apt_upgrade_mode == 'update_distupgrade'" in tasks


def test_wireguard_supports_single_hub_spoke_nodes():
    tasks = read_role_file("roles/base/vpn_wireguard/tasks/main.yml")
    server_template = read_role_file("roles/base/vpn_wireguard/templates/wg0.conf.j2")
    spoke_template = read_role_file("roles/base/vpn_wireguard/templates/spoke_config.conf.j2")
    vpn_role_vars = read_role_file(".local.example/role_vars/base/vpn_wireguard/main.yml")

    assert "wg_spoke_nodes" in tasks
    assert "item.value.hub in wg_servers" in tasks
    assert "spoke_config.conf.j2" in tasks
    assert "wg-spokes" in tasks
    assert "wg_spoke_nodes | default({})" in server_template
    assert "peer_allowed_ips.values" in server_template
    assert "# Spoke: {{ name }} via this hub" in server_template
    assert "Endpoint = {{ hub.endpoint }}:{{ wg_port }}" in spoke_template
    assert "AllowedIPs = {{ item.value.allowed_ips | default(wg_network_cidr) }}" in spoke_template
    assert "wg_spoke_nodes:" in vpn_role_vars
    assert "homelab:" in vpn_role_vars
    assert "spoke_pairs:" in vpn_role_vars


def test_wg_restricted_builds_second_hub_spoke_network_with_hub_firewall():
    site = read_role_file("site.yml")
    tasks = read_role_file("roles/base/wg_restricted/tasks/main.yml")
    defaults = read_role_file("roles/base/wg_restricted/defaults/main.yml")
    hub_template = read_role_file("roles/base/wg_restricted/templates/wg-restricted.conf.j2")
    node_template = read_role_file("roles/base/wg_restricted/templates/restricted_node_config.conf.j2")
    firewall = read_role_file("roles/base/wg_restricted/templates/wg-restricted-firewall.sh.j2")
    wg0_template = read_role_file("roles/base/vpn_wireguard/templates/wg0.conf.j2")
    role_vars = read_role_file(".local.example/role_vars/base/wg_restricted/main.yml")

    assert "base/wg_restricted" in site
    assert_site_uses_recursive_role_vars(site)
    assert "wg-restricted" in site
    assert "wg_restricted_enabled: false" in defaults
    assert 'wg_restricted_network_cidr: "10.13.14.0/24"' in defaults
    assert "wg_restricted_interface: wg-restricted" in defaults
    assert "wg_restricted_hub_ip_suffix: 1" in defaults
    assert "wg_restricted_nodes: {}" in defaults

    assert "inventory_hostname == wg_restricted_hub_host" in tasks
    assert "wg_restricted_nodes | dict2items" in tasks
    assert "wg-restricted-firewall.sh.j2" in tasks
    assert "wg-quick@{{ wg_restricted_interface }}" in tasks
    assert "ansible.posix.firewalld" in tasks
    assert "trusted" not in tasks
    assert "wg-restricted/{{ item.key }}" in tasks
    assert "restricted_node_config.conf.j2" in tasks

    assert "ListenPort = {{ wg_restricted_port }}" in hub_template
    assert "PostUp = {{ wg_restricted_firewall_script_path }} up" in hub_template
    assert "AllowedIPs = {{ wg_restricted_network_prefix }}.{{ node.ip_suffix }}/32" in hub_template
    assert "Endpoint = {{ hub.endpoint }}:{{ wg_restricted_port }}" in node_template
    assert "AllowedIPs = {{ wg_network_cidr }}, {{ wg_restricted_network_prefix }}.{{ wg_restricted_hub_ip_suffix }}/32" in node_template

    assert "-i \"$TRUSTED_IF\" -o \"$WG_IF\" -j ACCEPT" in firewall
    assert "-i \"$WG_IF\" -o \"$TRUSTED_IF\"" in firewall
    assert "--ctstate ESTABLISHED,RELATED -j ACCEPT" in firewall
    assert '-i "$WG_IF" -p tcp' in firewall
    assert '-o "$WG_IF" -p tcp' in firewall
    assert "-j REJECT --reject-with tcp-reset" in firewall
    assert "-j REJECT --reject-with icmp-admin-prohibited" in firewall
    assert "INPUT 1 -j \"$INPUT_CHAIN\"" in firewall

    assert "wg_restricted_network_cidr" in wg0_template
    assert "wg_restricted_hub_name == name" in wg0_template
    assert "peer_allowed_ips.values + [wg_restricted_cidr]" in wg0_template
    assert "wg_restricted_firewall_postup" in wg0_template
    assert "test ! -x ' ~ wg_restricted_firewall_hook" in wg0_template

    assert "wg_restricted_enabled: false" in role_vars
    assert 'wg_restricted_network_cidr: "10.66.14.0/24"' in role_vars
    assert "restricted_a:" in role_vars
    assert "restricted_a__vps_a" in role_vars


def test_zammad_storage_status_uses_machine_readable_sentinels():
    tasks = read_role_file("roles/apps/zammad/tasks/main.yml")

    assert "__ANSIBLE_ZAMMAD_STORAGE_PROVIDER__=File" in tasks
    assert "__ANSIBLE_ZAMMAD_DB_STORE__=present" in tasks
    assert "stdout_lines | default([]) | first" not in tasks


def test_zammad_compose_convergence_excludes_one_shot_init_service():
    tasks = read_role_file("roles/apps/zammad/tasks/main.yml")

    compose_task = tasks.split("- name: 启动 Zammad 容器栈", maxsplit=1)[1].split(
        "# ==========================================",
        maxsplit=1,
    )[0]

    assert "services:" in compose_task
    assert "zammad-railsserver" in compose_task
    assert "zammad-init" not in compose_task


def test_zammad_init_runs_separately_when_database_needs_it():
    tasks = read_role_file("roles/apps/zammad/tasks/main.yml")

    assert "to_regclass('public.settings')" in tasks
    assert "then 'absent' else 'present' end" in tasks
    assert "'present' not in (zammad_db_schema.stdout_lines | default([]))" in tasks
    assert "docker compose run --rm -T zammad-init" in tasks
    assert "zammad_compose_template.changed" in tasks
    assert "zammad_env_template.changed" in tasks


def test_backup_cron_schedules_are_declared_and_staggered():
    postgres = read_role_file("roles/apps/postgres/tasks/main.yml")
    postgres_defaults = read_role_file("roles/apps/postgres/defaults/main.yml")
    mailcow = read_role_file("roles/apps/mailcow/tasks/main.yml")
    mailcow_defaults = read_role_file("roles/apps/mailcow/defaults/main.yml")
    caddy = read_role_file("roles/gateway/caddy/tasks/main.yml")
    caddy_defaults = read_role_file("roles/gateway/caddy/defaults/main.yml")
    zammad = read_role_file("roles/apps/zammad/tasks/main.yml")
    zammad_defaults = read_role_file("roles/apps/zammad/defaults/main.yml")

    assert 'name: "Postgres Full Instance Backup"' in postgres
    assert 'postgres_backup_cron_hour: "3,15"' in postgres_defaults
    assert "cron_file: \"{{ postgres_backup_cron_file }}\"" in postgres
    assert "user: root" in postgres
    assert "postgres_backup_script_path: /opt/postgres/pg_backup_all.sh" in postgres_defaults
    assert "/etc/logrotate.d/pg_backup" in postgres

    assert 'name: "Mailcow Full Backup"' in mailcow
    assert 'mailcow_backup_cron_hour: "4,16"' in mailcow_defaults
    assert "cron_file: \"{{ mailcow_backup_cron_file }}\"" in mailcow
    assert "state: absent" in mailcow
    assert "user: root" in mailcow
    assert "mailcow_backup_script_path: /opt/mailcow-dockerized/mailcow_backup.sh" in mailcow_defaults
    assert "/etc/logrotate.d/mailcow_backup" in mailcow

    assert 'name: "Caddy Site Backup"' in caddy
    assert 'name: "Caddy Full Backup"' in caddy
    assert "CADDY_BACKUP_SUBDIR" in read_role_file(
        "roles/gateway/caddy/templates/caddy_backup.sh.j2"
    )
    assert 'caddy_backup_cron_hour: "5,17"' in caddy_defaults
    assert "cron_file: \"{{ caddy_backup_cron_file }}\"" in caddy
    assert "user: root" in caddy
    assert "caddy_backup_script_path: /opt/caddy/caddy_backup.sh" in caddy_defaults
    assert "/etc/logrotate.d/caddy_backup" in caddy

    assert 'name: "Zammad Local Backup"' in zammad
    assert 'zammad_backup_local_cron_hour: "6"' in zammad_defaults
    assert 'name: "Zammad Cloud Sync"' in zammad
    assert 'zammad_backup_cloud_cron_hour: "18"' in zammad_defaults
    assert "cron_file: \"{{ zammad_backup_cron_file }}\"" in zammad
    assert "user: root" in zammad
    assert "zammad_sync_script_path: /opt/zammad/zammad_sync.sh" in zammad_defaults
    assert "/etc/logrotate.d/zammad_sync" in zammad
    assert "src: zammad_backup_config.j2" in zammad
    assert "dest: /opt/zammad/backup_config" in zammad

def test_proxy_control_plane_node_sync_registers_xray_under_caddy_and_xray_by_api():
    site = read_role_file("site.yml")
    tasks = read_role_file("roles/apps/proxy_control_plane_node_sync/tasks/main.yml")
    defaults = read_role_file("roles/apps/proxy_control_plane_node_sync/defaults/main.yml")
    xray_role_vars = read_role_file(".local.example/role_vars/apps/xray/main.yml")
    xray_under_caddy_role_vars = read_role_file(
        ".local.example/role_vars/apps/xray_under_caddy/main.yml"
    )
    proxy_role_vars = read_role_file(".local.example/role_vars/apps/proxy_control_plane/main.yml")
    inventory = read_role_file(".local.example/inventory.yml")

    assert "apps/proxy_control_plane_node_sync" in site
    assert "proxy_control_plane_sync_nodes" in site
    assert_site_uses_recursive_role_vars(site)
    assert "proxy_control_plane_sync_nodes" in inventory
    assert "proxy_control_plane_node_sync_enabled: false" in defaults
    assert 'proxy_control_plane_api_url: "http://127.0.0.1:9710"' in defaults
    assert "proxy_control_plane_node_sync_enabled: false" in proxy_role_vars
    assert "xray_public_key" in xray_role_vars
    assert "xray_under_caddy_domain" in xray_under_caddy_role_vars
    assert "校验 Xray under Caddy 订阅域名" in tasks
    assert "/admin/login" in tasks
    assert "/admin/nodes/sync" in tasks
    assert "runtime: xray" in tasks
    assert "xray_under_caddy_nodes" in tasks
    assert "proxy_control_plane_node_enabled | default(true)" not in tasks
    assert "combine({'enabled':" in tasks
    assert "no_log: true" in tasks

def test_proxy_control_plane_role_deploys_ghcr_image_and_migrates_before_start():
    site = read_role_file("site.yml")
    tasks = read_role_file("roles/apps/proxy_control_plane/tasks/main.yml")
    defaults = read_role_file("roles/apps/proxy_control_plane/defaults/main.yml")
    compose = read_role_file("roles/apps/proxy_control_plane/templates/docker-compose.yml.j2")
    inventory = read_role_file(".local.example/inventory.yml")
    proxy_role_vars = read_role_file(".local.example/role_vars/apps/proxy_control_plane/main.yml")

    assert "apps/proxy_control_plane" in site
    assert "proxy_control_plane_nodes" in site
    assert "proxy_control_plane_nodes" in inventory
    assert 'proxy_control_plane_image: "ghcr.io/ziyan-c/proxy-control-plane:0.2"' in defaults
    assert "proxy_control_plane_enabled: false" in defaults
    assert "docker compose pull api" in tasks
    assert "docker compose run --rm api" in tasks
    assert "db migrate --no-local-config" in tasks
    assert "pull: always" in tasks
    assert "proxy_control_plane_env_file_src" in defaults
    assert "复制 Proxy Control Plane 环境变量文件" in tasks
    assert "no_log: true" in tasks
    assert "env_file:" in compose
    assert "./app.env" in compose
    assert "PCP_DATABASE_URL" not in compose
    assert "PCP_ADMIN_PASSWORD" not in compose
    assert "PCP_SECRET_KEY" not in compose
    assert "PCP_DATABASE_ENCRYPTION_KEY" not in compose
    assert "PCP_LISTEN_ADDR" not in compose
    assert "PCP_RUNTIME_SYNC_ENABLED" not in compose
    assert "proxy_control_plane_enabled: false" in proxy_role_vars
    assert 'proxy_control_plane_env_file_src: "{{ ansible_local_role_vars_dir }}/apps/proxy_control_plane/app.env"' in proxy_role_vars

def test_proxy_control_plane_runtime_api_is_wg_bound_and_registered():
    xray_config = read_role_file("roles/apps/xray/templates/config.json.j2")
    xray_under_caddy_config = read_role_file("roles/apps/xray_under_caddy/templates/config.json.j2")
    xray_compose = read_role_file("roles/apps/xray/templates/docker-compose.yml.j2")
    xray_under_caddy_compose = read_role_file("roles/apps/xray_under_caddy/templates/docker-compose.yml.j2")
    sync_tasks = read_role_file("roles/apps/proxy_control_plane_node_sync/tasks/main.yml")
    proxy_role_vars = read_role_file(".local.example/role_vars/apps/proxy_control_plane/main.yml")

    assert "proxy_control_plane_runtime_api_tag" in xray_config
    assert "proxy_control_plane_runtime_api_tag" in xray_under_caddy_config
    assert "proxy_control_plane_runtime_inbound_tag" in xray_config
    assert "proxy_control_plane_runtime_inbound_tag" in xray_under_caddy_config
    assert "dokodemo-door" in xray_config
    assert "dokodemo-door" in xray_under_caddy_config
    assert "proxy_control_plane_runtime_api_host" in xray_compose
    assert "proxy_control_plane_runtime_api_host" in xray_under_caddy_compose
    assert "runtime_api_enabled" in sync_tasks
    assert "runtime_api_host" in sync_tasks
    assert "runtime_api_port" in sync_tasks
    assert "runtime_inbound_tag" in sync_tasks
    assert "proxy_control_plane_runtime_api_tag: proxy-control-plane-api" in proxy_role_vars
    assert "proxy_control_plane_runtime_inbound_tag: proxy-control-plane-vless-in" in proxy_role_vars
    assert "proxy_control_plane_xray_runtime_api_port: 10085" in proxy_role_vars
    assert "proxy_control_plane_xray_under_caddy_runtime_api_port: 10085" in proxy_role_vars
    assert '"clients": {{ xray_static_clients | default([]) | to_json }}' in xray_config
    assert '"clients": {{ xray_under_caddy_static_clients | default([]) | to_json }}' in xray_under_caddy_config

def test_proxy_control_plane_subscription_proxy_is_optional_caddy_route():
    caddy_defaults = read_role_file("roles/gateway/caddy/defaults/main.yml")
    caddy_template = read_role_file("roles/gateway/caddy/templates/Caddyfile.j2")
    proxy_role_vars = read_role_file(".local.example/role_vars/apps/proxy_control_plane/main.yml")

    assert "proxy_control_plane_subscription_proxy_enabled: false" in caddy_defaults
    assert "proxy_control_plane_subscription_proxy_enabled: false" in proxy_role_vars
    assert "proxy_control_plane_subscription_public_path: /xray/sub" in caddy_defaults
    assert "proxy_control_plane_subscription_public_path: /xray/sub" in proxy_role_vars
    assert "proxy_control_plane_subscription_proxy_upstream" in caddy_template
    assert caddy_template.count("{{ proxy_control_plane_subscription_routes() }}") == 1
    assert "handle_path {{ proxy_control_plane_subscription_public_path" in caddy_template
    assert "rewrite * /sub{uri}" in caddy_template
    assert "legacy-sub" not in caddy_template
    assert "proxy_control_plane_subscription_legacy_paths" not in caddy_template

def test_logto_role_is_wg_bound_and_caddy_only_proxies_core():
    site = read_role_file("site.yml")
    tasks = read_role_file("roles/apps/logto/tasks/main.yml")
    defaults = read_role_file("roles/apps/logto/defaults/main.yml")
    compose = read_role_file("roles/apps/logto/templates/docker-compose.yml.j2")
    env_template = read_role_file("roles/apps/logto/templates/app.env.j2")
    caddy_template = read_role_file("roles/gateway/caddy/templates/Caddyfile.j2")
    caddy_defaults = read_role_file("roles/gateway/caddy/defaults/main.yml")
    inventory = read_role_file(".local.example/inventory.yml")
    logto_role_vars = read_role_file(".local.example/role_vars/apps/logto/main.yml")

    assert "apps/logto" in site
    assert "logto_nodes" in site
    assert_site_uses_recursive_role_vars(site)
    assert "logto_nodes" in inventory
    assert 'logto_image: "ghcr.io/logto-io/logto:1.40.1"' in defaults
    assert "logto_enabled: false" in defaults
    assert "logto_admin_proxy_enabled: false" in caddy_defaults
    assert "logto_admin_allowed_remote_ips" in caddy_defaults
    assert "logto_postgres_delegate_host" in defaults
    assert "logto_enabled: false" in logto_role_vars
    assert "logto_admin_domain" in logto_role_vars
    assert "logto_admin_proxy_enabled" in logto_role_vars
    assert "logto_admin_allowed_remote_ips" in logto_role_vars
    assert "logto_db_password" in logto_role_vars
    assert "wg_network_prefix" in logto_role_vars
    assert "deploy_node_postgres" in logto_role_vars
    logto_db_host_block = logto_role_vars.split("logto_db_host:", 1)[1].split(
        "logto_db_port:",
        1,
    )[0]
    assert "logto_bind_host" not in logto_db_host_block
    assert "logto_postgres_delegate_host" in logto_role_vars
    assert "logto_secret_vault_kek" in logto_role_vars
    assert "SECRET_VAULT_KEK" in env_template
    assert "DB_URL=postgres://" in env_template
    assert "urlencode" in env_template
    assert "TRUST_PROXY_HEADER" in env_template
    assert '"{{ logto_bind_host }}:{{ logto_core_port | int }}:{{ logto_core_port | int }}"' in compose
    assert '"{{ logto_bind_host }}:{{ logto_admin_port | int }}:{{ logto_admin_port | int }}"' in compose
    assert "docker compose run --rm -T logto cli connector add -- --official" in tasks
    assert "docker compose run --rm -T logto cli db seed -- --swe" in tasks
    assert "docker compose run --rm -T -e CI=true logto alteration deploy latest" in tasks
    assert 'delegate_to: "{{ logto_postgres_delegate_host }}"' in tasks
    assert 'ALTER ROLE :"logto_user" CREATEROLE;' in tasks
    assert "logto_proxy_upstream" not in caddy_template
    assert "ADMIN_ENDPOINT" not in caddy_template
    logto_caddy_block = caddy_template.split("{{ logto_domain }} {", 1)[1].split(
        "{% if (logto_admin_proxy_enabled",
        1,
    )[0]
    assert "header_up X-Real-IP {http.request.header.CF-Connecting-IP}" in logto_caddy_block
    assert (
        "header_up X-Forwarded-For {http.request.header.CF-Connecting-IP}"
        in logto_caddy_block
    )
    assert "header_up Host {host}" not in logto_caddy_block
    assert "{{ logto_admin_domain }} {" in caddy_template
    assert "@logto_admin_denied {" in caddy_template
    assert "not remote_ip" in caddy_template
    assert "abort @logto_admin_denied" in caddy_template
    assert "reverse_proxy http://{{ logto_bind_host }}:{{ logto_admin_port | int }}" in caddy_template


def test_sftpgo_role_is_wg_bound_and_separates_public_and_admin_bindings():
    site = read_role_file("site.yml")
    tasks = read_role_file("roles/apps/sftpgo/tasks/main.yml")
    defaults = read_role_file("roles/apps/sftpgo/defaults/main.yml")
    compose = read_role_file("roles/apps/sftpgo/templates/docker-compose.yml.j2")
    env_template = read_role_file("roles/apps/sftpgo/templates/app.env.j2")
    backup_script = read_role_file("roles/apps/sftpgo/templates/sftpgo_backup.sh.j2")
    retention_script = read_role_file("roles/apps/sftpgo/templates/sftpgo_retention_cleanup.sh.j2")
    caddy_template = read_role_file("roles/gateway/caddy/templates/Caddyfile.j2")
    caddy_defaults = read_role_file("roles/gateway/caddy/defaults/main.yml")
    inventory = read_role_file(".local.example/inventory.yml")
    sftpgo_role_vars = read_role_file(".local.example/role_vars/apps/sftpgo/main.yml")

    assert "apps/sftpgo" in site
    assert "sftpgo_nodes" in site
    assert_site_uses_recursive_role_vars(site)
    assert "sftpgo_nodes" in inventory

    assert 'sftpgo_image: "drakkan/sftpgo:v2.7.3"' in defaults
    assert "sftpgo_enabled: false" in defaults
    assert "sftpgo_admin_proxy_enabled: false" in caddy_defaults
    assert "sftpgo_admin_allowed_remote_ips" in caddy_defaults
    assert "sftpgo_postgres_delegate_host" in defaults
    assert "sftpgo_retention_enabled: true" in defaults
    assert 'sftpgo_retention_project_dir: "{{ sftpgo_project_dir }}/retention"' in defaults
    assert "sftpgo_defender_event_retention_days: 90" in defaults
    assert "sftpgo_shared_session_retention_days: 7" in defaults
    assert "sftpgo_active_transfer_stale_hours: 24" in defaults
    assert "sftpgo_backup_cron_file: sftpgo_backup" in defaults
    assert "sftpgo_enabled: false" in sftpgo_role_vars
    assert 'sftpgo_storage_dir: "{{ sftpgo_gdrive_mount_point }}/{{ sftpgo_gdrive_storage_subdir }}"' in sftpgo_role_vars
    assert "sftpgo_db_password" in sftpgo_role_vars
    assert "sftpgo_signing_passphrase" in sftpgo_role_vars
    assert "sftpgo_oidc_enabled: false" in sftpgo_role_vars
    assert "sftpgo_retention_enabled: true" in sftpgo_role_vars
    assert "deploy_node_sftpgo" in sftpgo_role_vars
    assert "deploy_node_postgres" in sftpgo_role_vars

    assert "docker compose run --rm -T sftpgo sftpgo initprovider" in tasks
    assert 'delegate_to: "{{ sftpgo_postgres_delegate_host }}"' in tasks
    assert "下发 SFTPGo retention 清理脚本到 SFTPGo 节点" in tasks
    assert "下发 SFTPGo retention 清理脚本到 Postgres 节点" in tasks
    assert "SFTPGo retention cleanup" in tasks
    assert "cron_file: \"{{ sftpgo_retention_cron_file }}\"" in tasks
    assert "/etc/logrotate.d/sftpgo_retention_cleanup" in tasks
    assert "run_once: true" in tasks
    assert "cron_file: \"{{ sftpgo_backup_cron_file }}\"" in tasks
    assert "user: root" in tasks
    assert "/etc/logrotate.d/sftpgo_backup" in tasks

    assert "env_file:" in compose
    assert "./app.env" in compose
    assert '"{{ sftpgo_bind_host }}:{{ sftpgo_public_http_port | int }}:{{ sftpgo_public_http_port | int }}"' in compose
    assert '"{{ sftpgo_bind_host }}:{{ sftpgo_admin_http_port | int }}:{{ sftpgo_admin_http_port | int }}"' in compose
    assert "{{ sftpgo_storage_dir }}:/srv/sftpgo" in compose
    assert "{{ sftpgo_config_dir }}:/var/lib/sftpgo" in compose

    assert "SFTPGO_DATA_PROVIDER__DRIVER=postgresql" in env_template
    assert "SFTPGO_DATA_PROVIDER__PASSWORD={{ sftpgo_db_password }}" in env_template
    assert "SFTPGO_HTTPD__SIGNING_PASSPHRASE" in env_template
    assert "SFTPGO_HTTPD__BINDINGS__0__OIDC__CONFIG_URL" in env_template
    assert "SFTPGO_HTTPD__BINDINGS__0__ENABLE_WEB_ADMIN=false" in env_template
    assert "SFTPGO_HTTPD__BINDINGS__0__ENABLE_WEB_CLIENT=true" in env_template
    assert "SFTPGO_HTTPD__BINDINGS__0__DISABLED_LOGIN_METHODS={{ sftpgo_public_disabled_login_methods | int }}" in env_template
    assert "SFTPGO_HTTPD__BINDINGS__1__ENABLE_WEB_ADMIN=true" in env_template
    assert "SFTPGO_HTTPD__BINDINGS__1__ENABLE_WEB_CLIENT=false" in env_template
    assert "SFTPGO_HTTPD__BINDINGS__1__DISABLED_LOGIN_METHODS={{ sftpgo_admin_disabled_login_methods | int }}" in env_template

    assert "sftpgo_backup_" in backup_script
    assert "rclone copy" in backup_script
    assert "{{ sftpgo_storage_dir }}" in backup_script
    assert "{{ sftpgo_config_dir }}" in backup_script

    assert "public.defender_events" in retention_script
    assert "public.defender_hosts" in retention_script
    assert "public.shared_sessions" in retention_script
    assert "public.active_transfers" in retention_script
    assert "public.nodes" in retention_script
    assert "VACUUM ANALYZE" in retention_script
    assert "public.users" not in retention_script
    assert "public.shares" not in retention_script
    assert "public.api_keys" not in retention_script

    assert "{{ sftpgo_domain }} {" in caddy_template
    assert "@sftpgo_admin_paths {" not in caddy_template
    assert "abort @sftpgo_admin_paths" not in caddy_template
    assert "{{ sftpgo_admin_domain }} {" in caddy_template
    assert "@sftpgo_admin_denied {" in caddy_template
    assert "not remote_ip {{ sftpgo_admin_allowed_remote_ips" in caddy_template
    assert "abort @sftpgo_admin_denied" in caddy_template
    assert "reverse_proxy http://{{ sftpgo_bind_host }}:{{ sftpgo_public_http_port | int }}" in caddy_template
    assert "reverse_proxy http://{{ sftpgo_bind_host }}:{{ sftpgo_admin_http_port | int }}" in caddy_template
    assert "sftpgo_admin_uses_certbot_tls" in read_role_file("roles/gateway/caddy/templates/docker-compose.yml.j2")
