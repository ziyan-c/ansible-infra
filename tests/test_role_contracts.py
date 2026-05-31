from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_role_file(path):
    return (REPO_ROOT / path).read_text(encoding="utf-8")


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
    system_role_vars = read_role_file(".local.example/role_vars/system_init/main.yml")

    assert "rclone_config_force_update: false" in defaults
    assert "rclone_config_force_update: false" in system_role_vars
    assert 'force: "{{ rclone_config_force_update | bool }}"' in tasks


def test_system_init_apt_upgrade_mode_separates_update_upgrade_and_dist_upgrade():
    defaults = read_role_file("roles/base/system_init/defaults/main.yml")
    tasks = read_role_file("roles/base/system_init/tasks/main.yml")
    system_role_vars = read_role_file(".local.example/role_vars/system_init/main.yml")

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
    vpn_role_vars = read_role_file(".local.example/role_vars/vpn_wireguard/main.yml")

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

    assert 'name: "Caddy Full Backup"' in caddy
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
    xray_role_vars = read_role_file(".local.example/role_vars/xray/main.yml")
    xray_under_caddy_role_vars = read_role_file(
        ".local.example/role_vars/xray_under_caddy/main.yml"
    )
    proxy_role_vars = read_role_file(".local.example/role_vars/proxy_control_plane/main.yml")
    inventory = read_role_file(".local.example/inventory.yml")

    assert "apps/proxy_control_plane_node_sync" in site
    assert "proxy_control_plane_sync_nodes" in site
    assert "ANSIBLE_PRIVATE_STATE_DIR" in site
    assert "/role_vars/proxy_control_plane/main.yml" in site
    assert "/role_vars/xray/main.yml" in site
    assert "/role_vars/xray_under_caddy/main.yml" in site
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
    proxy_role_vars = read_role_file(".local.example/role_vars/proxy_control_plane/main.yml")

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
    assert 'proxy_control_plane_env_file_src: "{{ private_state_dir }}/role_vars/proxy_control_plane/app.env"' in proxy_role_vars

def test_proxy_control_plane_runtime_api_is_wg_bound_and_registered():
    xray_config = read_role_file("roles/apps/xray/templates/config.json.j2")
    xray_under_caddy_config = read_role_file("roles/apps/xray_under_caddy/templates/config.json.j2")
    xray_compose = read_role_file("roles/apps/xray/templates/docker-compose.yml.j2")
    xray_under_caddy_compose = read_role_file("roles/apps/xray_under_caddy/templates/docker-compose.yml.j2")
    sync_tasks = read_role_file("roles/apps/proxy_control_plane_node_sync/tasks/main.yml")
    proxy_role_vars = read_role_file(".local.example/role_vars/proxy_control_plane/main.yml")

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
    proxy_role_vars = read_role_file(".local.example/role_vars/proxy_control_plane/main.yml")

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
    logto_role_vars = read_role_file(".local.example/role_vars/logto/main.yml")

    assert "apps/logto" in site
    assert "logto_nodes" in site
    assert "ANSIBLE_PRIVATE_STATE_DIR" in site
    assert "/role_vars/logto/main.yml" in site
    assert "/role_vars/postgres/main.yml" in site
    assert "/role_vars/vpn_wireguard/main.yml" in site
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
