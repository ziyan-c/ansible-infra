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


def test_rclone_config_update_requires_explicit_force_flag():
    defaults = read_role_file("roles/base/system_init/defaults/main.yml")
    tasks = read_role_file("roles/base/system_init/tasks/main.yml")
    example_vars = read_role_file(".local.example/group_vars/all.yml")

    assert "rclone_config_force_update: false" in defaults
    assert "rclone_config_force_update: false" in example_vars
    assert 'force: "{{ rclone_config_force_update | bool }}"' in tasks


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


def test_neo_backend_role_deploys_bundled_single_container_app():
    tasks = read_role_file("roles/apps/neo_backend/tasks/main.yml")
    compose = read_role_file("roles/apps/neo_backend/templates/docker-compose.yml.j2")
    env_template = read_role_file("roles/apps/neo_backend/templates/neo-backend.env.j2")

    assert "src: app/" in tasks
    assert "src: neo-backend.env.j2" in tasks
    assert "neo_backend_app_source.changed or neo_backend_compose_template.changed" in tasks
    assert "neo_backend_publish_wireguard" in tasks
    assert "no_log: true" in tasks
    assert "neo-backend:" in compose
    assert "context: ./app" in compose
    assert "env_file:" in compose
    assert "ports:" in compose
    assert "{{ neo_wg_bind_ip }}:{{ neo_rag_proxy_port }}:{{ neo_rag_proxy_port }}" in compose
    assert "go-proxy" not in compose
    assert "ssh-tunnel" not in compose
    assert "NEO_PROXY_PASSWORD={{ neo_proxy_password }}" in env_template
    assert "NEO_MANAGE_SSH_TUNNEL={{ 1 if neo_manage_ssh_tunnel | bool else 0 }}" in env_template


def test_neo_backend_query_password_is_not_forwarded_upstream():
    proxy = read_role_file("roles/apps/neo_backend/files/app/src/neo_backend/proxy.py")

    assert "def sanitized_query" in proxy
    assert 'key.lower() != "password"' in proxy
    assert "join_url(base_url, path, sanitized_query(request))" in proxy


def test_neo_backend_proxy_preserves_upstream_streaming():
    proxy = read_role_file("roles/apps/neo_backend/files/app/src/neo_backend/proxy.py")

    assert "client.send(upstream_request, stream=True)" in proxy
    assert "StreamingResponse(" in proxy
    assert "upstream.aiter_bytes()" in proxy
    assert "BackgroundTask(upstream.aclose)" in proxy


def test_neo_backend_auth_check_requires_proxy_auth_before_catch_all():
    app = read_role_file("roles/apps/neo_backend/files/app/src/neo_backend/app.py")

    auth_check = app.index('@app.get("/auth/check")')
    catch_all = app.index('@app.api_route("/{path:path}"')

    assert "Depends(auth_dependency)" in app[auth_check:catch_all]
    assert '"authenticated": True' in app[auth_check:catch_all]
    assert auth_check < catch_all


def test_backup_cron_schedules_are_declared_and_staggered():
    postgres = read_role_file("roles/apps/postgres/tasks/main.yml")
    mailcow = read_role_file("roles/apps/mailcow/tasks/main.yml")
    caddy = read_role_file("roles/gateway/caddy/tasks/main.yml")
    zammad = read_role_file("roles/apps/zammad/tasks/main.yml")

    assert 'name: "Postgres Full Instance Backup"' in postgres
    assert 'hour: "3,15"' in postgres
    assert "/opt/postgres/pg_backup_all.sh" in postgres
    assert "/etc/logrotate.d/pg_backup" in postgres

    assert 'name: "Mailcow Full Backup"' in mailcow
    assert 'hour: "4,16"' in mailcow
    assert "/opt/mailcow-dockerized/mailcow_backup.sh" in mailcow
    assert "/etc/logrotate.d/mailcow_backup" in mailcow

    assert 'name: "Caddy Full Backup"' in caddy
    assert 'hour: "5,17"' in caddy
    assert "/opt/caddy/caddy_backup.sh" in caddy
    assert "/etc/logrotate.d/caddy_backup" in caddy

    assert 'name: "Zammad Local Backup"' in zammad
    assert 'hour: "6"' in zammad
    assert 'name: "Zammad Cloud Sync"' in zammad
    assert 'hour: "18"' in zammad
    assert "/etc/logrotate.d/zammad_sync" in zammad
    assert "src: zammad_backup_config.j2" in zammad
    assert "dest: /opt/zammad/backup_config" in zammad

def test_proxy_control_plane_node_sync_registers_xray_under_caddy_and_xray_by_api():
    site = read_role_file("site.yml")
    tasks = read_role_file("roles/apps/proxy_control_plane_node_sync/tasks/main.yml")
    defaults = read_role_file("roles/apps/proxy_control_plane_node_sync/defaults/main.yml")
    example_vars = read_role_file(".local.example/group_vars/all.yml")
    inventory = read_role_file(".local.example/inventory.yml")

    assert "apps/proxy_control_plane_node_sync" in site
    assert "proxy_control_plane_sync_nodes" in site
    assert "proxy_control_plane_sync_nodes" in inventory
    assert "proxy_control_plane_node_sync_enabled: false" in defaults
    assert 'proxy_control_plane_api_url: "http://127.0.0.1:9710"' in defaults
    assert "proxy_control_plane_node_sync_enabled: false" in example_vars
    assert "xray_public_key" in example_vars
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
    example_vars = read_role_file(".local.example/group_vars/all.yml")

    assert "apps/proxy_control_plane" in site
    assert "proxy_control_plane_nodes" in site
    assert "proxy_control_plane_nodes" in inventory
    assert 'proxy_control_plane_image: "ghcr.io/ziyan-c/proxy-control-plane:0.1.1"' in defaults
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
    assert "proxy_control_plane_enabled: false" in example_vars

def test_proxy_control_plane_runtime_api_is_wg_bound_and_registered():
    xray_config = read_role_file("roles/apps/xray/templates/config.json.j2")
    xray_under_caddy_config = read_role_file("roles/apps/xray_under_caddy/templates/config.json.j2")
    xray_compose = read_role_file("roles/apps/xray/templates/docker-compose.yml.j2")
    xray_under_caddy_compose = read_role_file("roles/apps/xray_under_caddy/templates/docker-compose.yml.j2")
    sync_tasks = read_role_file("roles/apps/proxy_control_plane_node_sync/tasks/main.yml")
    example_vars = read_role_file(".local.example/group_vars/all.yml")

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
    assert "proxy_control_plane_runtime_api_tag: proxy-control-plane-api" in example_vars
    assert "proxy_control_plane_runtime_inbound_tag: proxy-control-plane-vless-in" in example_vars
    assert "proxy_control_plane_xray_runtime_api_port: 10085" in example_vars
    assert "proxy_control_plane_xray_under_caddy_runtime_api_port: 10085" in example_vars
    assert '"clients": {{ xray_static_clients | default([]) | to_json }}' in xray_config
    assert '"clients": {{ xray_under_caddy_static_clients | default([]) | to_json }}' in xray_under_caddy_config

def test_proxy_control_plane_subscription_proxy_is_optional_caddy_route():
    caddy_defaults = read_role_file("roles/gateway/caddy/defaults/main.yml")
    caddy_template = read_role_file("roles/gateway/caddy/templates/Caddyfile.j2")
    example_vars = read_role_file(".local.example/group_vars/all.yml")

    assert "proxy_control_plane_subscription_proxy_enabled: false" in caddy_defaults
    assert "proxy_control_plane_subscription_proxy_enabled: false" in example_vars
    assert "proxy_control_plane_subscription_proxy_upstream" in caddy_template
    assert "handle_path {{ proxy_control_plane_subscription_public_path" in caddy_template
    assert "rewrite * /sub{uri}" in caddy_template
    assert "legacy-sub" not in caddy_template
    assert "proxy_control_plane_subscription_legacy_paths" not in caddy_template
