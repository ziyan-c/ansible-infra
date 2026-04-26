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
