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
    assert "no_log: true" in tasks
    assert "neo-backend:" in compose
    assert "context: ./app" in compose
    assert "env_file:" in compose
    assert "go-proxy" not in compose
    assert "ssh-tunnel" not in compose
    assert "NEO_PROXY_PASSWORD={{ neo_proxy_password }}" in env_template
    assert "NEO_MANAGE_SSH_TUNNEL={{ 1 if neo_manage_ssh_tunnel | bool else 0 }}" in env_template


def test_neo_backend_query_password_is_not_forwarded_upstream():
    proxy = read_role_file("roles/apps/neo_backend/files/app/src/neo_backend/proxy.py")

    assert "def sanitized_query" in proxy
    assert 'key.lower() != "password"' in proxy
    assert "join_url(base_url, path, sanitized_query(request))" in proxy


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
