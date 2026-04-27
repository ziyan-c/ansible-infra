import os
import re
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKUP_TIMESTAMP = r"\d{8}_\d{6}"


@pytest.fixture(scope="module")
def render_root(tmp_path_factory):
    render_dir = tmp_path_factory.mktemp("rendered-shell")
    env = os.environ.copy()
    env.update(
        {
            "ANSIBLE_HOME": str(REPO_ROOT / ".ansible"),
            "ANSIBLE_LOCAL_TEMP": "/tmp/ansible-local",
            "ANSIBLE_REMOTE_TEMP": "/tmp/ansible-remote",
            "ANSIBLE_COLLECTIONS_PATH": str(REPO_ROOT / ".ansible/collections"),
            "ANSIBLE_VAULT_PASSWORD_FILE": str(
                REPO_ROOT / ".local.example/vault_password"
            ),
            "TEST_RENDER_DIR": str(render_dir),
        }
    )
    subprocess.run(
        [
            "ansible-playbook",
            "-i",
            ".local.example/inventory.yml",
            "tests/render_shell_templates.yml",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return render_dir


class ScriptHarness:
    def __init__(self, workdir, render_root):
        self.workdir = workdir
        self.render_root = render_root
        self.fake_bin = workdir / "fake-bin"
        self.fake_bin.mkdir()
        self.log_dir = workdir / "logs"
        self.log_dir.mkdir()
        self.write_common_fakes()

    def write_executable(self, name, content):
        path = self.fake_bin / name
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def write_common_fakes(self):
        self.write_executable(
            "rclone",
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            echo "$*" >> "$TEST_LOG_DIR/rclone.log"
            case "${1:-}" in
              lsf)
                exit 0
                ;;
              copy|deletefile)
                exit 0
                ;;
              *)
                exit 0
                ;;
            esac
            """,
        )
        self.write_executable(
            "head",
            """\
            #!/usr/bin/env bash
            if [ "${1:-}" = "-n" ] && [[ "${2:-}" == -* ]]; then
              cat >/dev/null
              exit 0
            fi
            exec /usr/bin/head "$@"
            """,
        )
        self.write_executable(
            "find",
            """\
            #!/usr/bin/env bash
            args="$*"
            if [[ "$args" == *"-type d"* && "$args" == *"mailcow-*"* && "$args" == *"-printf"* ]]; then
              for candidate in "$1"/mailcow-*; do
                if [ -d "$candidate" ]; then
                  echo "1 $candidate"
                  exit 0
                fi
              done
              exit 0
            fi
            if [[ "$args" == *"-type f"* && "$args" == *"-name"* && "$args" == *"-printf"* ]]; then
              root="$1"
              pattern="*"
              while [ "$#" -gt 0 ]; do
                if [ "${1:-}" = "-name" ]; then
                  pattern="$2"
                  break
                fi
                shift
              done
              for candidate in "$root"/$pattern; do
                if [ -f "$candidate" ]; then
                  mtime="$(stat -c %Y "$candidate" 2>/dev/null || stat -f %m "$candidate")"
                  printf '%s %s\\n' "$mtime" "$candidate"
                fi
              done
              exit 0
            fi
            exec /usr/bin/find "$@"
            """,
        )

    def script_env(self, **overrides):
        env = os.environ.copy()
        script_path = f"{self.fake_bin}{os.pathsep}{env['PATH']}"
        env.update(
            {
                "ANSIBLE_INFRA_SCRIPT_PATH": script_path,
                "PATH": script_path,
                "TEST_LOG_DIR": str(self.log_dir),
            }
        )
        env.update({key: str(value) for key, value in overrides.items()})
        return env

    def run_script(self, script_name, *args, env=None):
        script = self.render_root / script_name
        return subprocess.run(
            [str(script), *args],
            cwd=self.workdir,
            env=env or self.script_env(),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )


@pytest.fixture
def script_harness(tmp_path, render_root):
    return ScriptHarness(tmp_path, render_root)


def assert_name_matches(path, pattern):
    assert re.fullmatch(pattern, path.name), path.name


def create_old_backup(path, age_index):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("old backup\n", encoding="utf-8")
    timestamp = 1_700_000_000 + age_index
    os.utime(path, (timestamp, timestamp))


def test_postgres_backup_success_creates_archives_and_uploads(script_harness):
    h = script_harness
    backup_dir = h.workdir / "postgres-backups"
    custom_dir = h.workdir / "custom-data"
    custom_dir.mkdir()
    (custom_dir / "asset.txt").write_text("custom asset\n", encoding="utf-8")
    h.write_executable(
        "docker",
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        echo "$*" >> "$TEST_LOG_DIR/docker.log"
        if [ "${1:-}" = "exec" ]; then
          printf 'CREATE DATABASE app;\\n'
          exit 0
        fi
        exit 0
        """,
    )

    result = h.run_script(
        "pg_backup_all.sh",
        env=h.script_env(
            POSTGRES_BACKUP_DIR=backup_dir,
            POSTGRES_CUSTOM_DATA_DIR=custom_dir,
        ),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    sql_archives = list(backup_dir.glob("pg_sql_*.sql.gz"))
    custom_archives = list(backup_dir.glob("pg_custom_data_*.tar.gz"))
    assert len(sql_archives) == 1
    assert len(custom_archives) == 1
    assert_name_matches(sql_archives[0], rf"pg_sql_{BACKUP_TIMESTAMP}\.sql\.gz")
    assert_name_matches(
        custom_archives[0],
        rf"pg_custom_data_{BACKUP_TIMESTAMP}\.tar\.gz",
    )
    assert "copy" in (h.log_dir / "rclone.log").read_text(encoding="utf-8")


def test_postgres_backup_failure_removes_partial_archive_and_skips_upload(
    script_harness,
):
    h = script_harness
    backup_dir = h.workdir / "postgres-backups"
    h.write_executable(
        "docker",
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        echo "$*" >> "$TEST_LOG_DIR/docker.log"
        if [ "${1:-}" = "exec" ]; then
          printf 'partial dump\\n'
          exit 42
        fi
        exit 0
        """,
    )

    result = h.run_script(
        "pg_backup_all.sh",
        env=h.script_env(POSTGRES_BACKUP_DIR=backup_dir),
    )

    assert result.returncode == 1
    assert list(backup_dir.glob("pg_sql_*.sql.gz")) == []
    assert not (h.log_dir / "rclone.log").exists()
    assert "SQL" in result.stdout + result.stderr


def test_postgres_backup_prunes_local_archives_to_keep_limit(script_harness):
    h = script_harness
    backup_dir = h.workdir / "postgres-backups"
    custom_dir = h.workdir / "custom-data"
    custom_dir.mkdir()
    (custom_dir / "asset.txt").write_text("custom asset\n", encoding="utf-8")
    h.write_executable(
        "docker",
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        echo "$*" >> "$TEST_LOG_DIR/docker.log"
        if [ "${1:-}" = "exec" ]; then
          printf 'CREATE DATABASE app;\\n'
          exit 0
        fi
        exit 0
        """,
    )

    for index in range(8):
        date_part = f"2020010{index + 1}"
        create_old_backup(backup_dir / f"pg_sql_{date_part}_000000.sql.gz", index)
        create_old_backup(
            backup_dir / f"pg_custom_data_{date_part}_000000.tar.gz",
            index,
        )

    result = h.run_script(
        "pg_backup_all.sh",
        env=h.script_env(
            POSTGRES_BACKUP_DIR=backup_dir,
            POSTGRES_CUSTOM_DATA_DIR=custom_dir,
        ),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    sql_archives = sorted(backup_dir.glob("pg_sql_*.sql.gz"))
    custom_archives = sorted(backup_dir.glob("pg_custom_data_*.tar.gz"))
    assert len(sql_archives) == 7
    assert len(custom_archives) == 7
    assert not (backup_dir / "pg_sql_20200101_000000.sql.gz").exists()
    assert not (backup_dir / "pg_sql_20200102_000000.sql.gz").exists()
    assert not (backup_dir / "pg_custom_data_20200101_000000.tar.gz").exists()
    assert not (backup_dir / "pg_custom_data_20200102_000000.tar.gz").exists()


def test_caddy_backup_success_excludes_its_own_script(script_harness):
    h = script_harness
    caddy_dir = h.workdir / "caddy"
    caddy_dir.mkdir()
    (caddy_dir / "Caddyfile").write_text("example.com\n", encoding="utf-8")
    (caddy_dir / "caddy_backup.sh").write_text("skip me\n", encoding="utf-8")
    backup_dir = h.workdir / "caddy-backups"

    result = h.run_script(
        "caddy_backup.sh",
        env=h.script_env(CADDY_TARGET_DIR=caddy_dir, CADDY_BACKUP_ROOT=backup_dir),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    archives = list(backup_dir.glob("caddy_backup_*.tar.gz"))
    assert len(archives) == 1
    assert_name_matches(archives[0], rf"caddy_backup_{BACKUP_TIMESTAMP}\.tar\.gz")
    listing = subprocess.run(
        ["tar", "-tzf", str(archives[0])],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert listing.returncode == 0, listing.stdout + listing.stderr
    assert "caddy/Caddyfile" in listing.stdout
    assert "caddy/caddy_backup.sh" not in listing.stdout


def test_caddy_backup_prunes_local_archives_to_keep_limit(script_harness):
    h = script_harness
    caddy_dir = h.workdir / "caddy"
    caddy_dir.mkdir()
    (caddy_dir / "Caddyfile").write_text("example.com\n", encoding="utf-8")
    backup_dir = h.workdir / "caddy-backups"

    for index in range(8):
        create_old_backup(
            backup_dir / f"caddy_backup_2020010{index + 1}_000000.tar.gz",
            index,
        )

    result = h.run_script(
        "caddy_backup.sh",
        env=h.script_env(CADDY_TARGET_DIR=caddy_dir, CADDY_BACKUP_ROOT=backup_dir),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    archives = sorted(backup_dir.glob("caddy_backup_*.tar.gz"))
    assert len(archives) == 7
    assert not (backup_dir / "caddy_backup_20200101_000000.tar.gz").exists()
    assert not (backup_dir / "caddy_backup_20200102_000000.tar.gz").exists()


def test_mailcow_backup_success_packages_latest_backup_directory(script_harness):
    h = script_harness
    mailcow_dir = h.workdir / "mailcow"
    helper_dir = mailcow_dir / "helper-scripts"
    helper_dir.mkdir(parents=True)
    helper = helper_dir / "backup_and_restore.sh"
    helper.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            mkdir -p "$BACKUP_LOCATION/mailcow-test"
            printf 'mailcow data\\n' > "$BACKUP_LOCATION/mailcow-test/data.txt"
            """
        ),
        encoding="utf-8",
    )
    helper.chmod(helper.stat().st_mode | stat.S_IXUSR)
    backup_dir = h.workdir / "mailcow-backups"
    official_backup_dir = h.workdir / "mailcow-backup-work"

    result = h.run_script(
        "mailcow_backup.sh",
        env=h.script_env(
            MAILCOW_DIR=mailcow_dir,
            MAILCOW_BACKUP_ROOT=backup_dir,
            MAILCOW_OFFICIAL_BACKUP_ROOT=official_backup_dir,
        ),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    archives = list(backup_dir.glob("mailcow_backup_*.tar.gz"))
    assert len(archives) == 1
    assert_name_matches(archives[0], rf"mailcow_backup_{BACKUP_TIMESTAMP}\.tar\.gz")
    assert archives[0].stat().st_mode & stat.S_IRWXO == 0
    assert not (official_backup_dir / "mailcow-test").exists()


def test_mailcow_backup_failure_stops_before_packaging_and_upload(script_harness):
    h = script_harness
    mailcow_dir = h.workdir / "mailcow"
    helper_dir = mailcow_dir / "helper-scripts"
    helper_dir.mkdir(parents=True)
    helper = helper_dir / "backup_and_restore.sh"
    helper.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            exit 44
            """
        ),
        encoding="utf-8",
    )
    helper.chmod(helper.stat().st_mode | stat.S_IXUSR)
    backup_dir = h.workdir / "mailcow-backups"
    official_backup_dir = h.workdir / "mailcow-backup-work"

    result = h.run_script(
        "mailcow_backup.sh",
        env=h.script_env(
            MAILCOW_DIR=mailcow_dir,
            MAILCOW_BACKUP_ROOT=backup_dir,
            MAILCOW_OFFICIAL_BACKUP_ROOT=official_backup_dir,
        ),
    )

    assert result.returncode == 1
    assert list(backup_dir.glob("mailcow_backup_*.tar.gz")) == []
    assert not (h.log_dir / "rclone.log").exists()


def test_mailcow_backup_prunes_local_archives_to_keep_limit(script_harness):
    h = script_harness
    mailcow_dir = h.workdir / "mailcow"
    helper_dir = mailcow_dir / "helper-scripts"
    helper_dir.mkdir(parents=True)
    helper = helper_dir / "backup_and_restore.sh"
    helper.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            mkdir -p "$BACKUP_LOCATION/mailcow-test"
            printf 'mailcow data\\n' > "$BACKUP_LOCATION/mailcow-test/data.txt"
            """
        ),
        encoding="utf-8",
    )
    helper.chmod(helper.stat().st_mode | stat.S_IXUSR)
    backup_dir = h.workdir / "mailcow-backups"
    official_backup_dir = h.workdir / "mailcow-backup-work"

    for index in range(8):
        create_old_backup(
            backup_dir / f"mailcow_backup_2020010{index + 1}_000000.tar.gz",
            index,
        )

    result = h.run_script(
        "mailcow_backup.sh",
        env=h.script_env(
            MAILCOW_DIR=mailcow_dir,
            MAILCOW_BACKUP_ROOT=backup_dir,
            MAILCOW_OFFICIAL_BACKUP_ROOT=official_backup_dir,
        ),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    archives = sorted(backup_dir.glob("mailcow_backup_*.tar.gz"))
    assert len(archives) == 7
    assert not (backup_dir / "mailcow_backup_20200101_000000.tar.gz").exists()
    assert not (backup_dir / "mailcow_backup_20200102_000000.tar.gz").exists()


def test_zammad_local_backup_runs_compose_backup_command(script_harness):
    h = script_harness
    zammad_dir = h.workdir / "zammad"
    zammad_dir.mkdir()
    h.write_executable(
        "docker",
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        echo "$*" >> "$TEST_LOG_DIR/docker.log"
        if [ "${1:-}" = "volume" ]; then
          exit 1
        fi
        exit 0
        """,
    )

    result = h.run_script(
        "zammad_sync.sh",
        "local",
        env=h.script_env(ZAMMAD_DIR=zammad_dir),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    docker_log = (h.log_dir / "docker.log").read_text(encoding="utf-8")
    assert "compose exec -T zammad-backup" in docker_log


def test_zammad_cloud_sync_uploads_volume_and_prunes_old_remote_files(
    script_harness,
):
    h = script_harness
    volume_path = h.workdir / "zammad-volume"
    volume_path.mkdir()
    h.write_executable(
        "docker",
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        echo "$*" >> "$TEST_LOG_DIR/docker.log"
        if [ "${1:-}" = "volume" ]; then
          printf '%s\\n' "$TEST_ZAMMAD_VOLUME"
          exit 0
        fi
        exit 0
        """,
    )
    h.write_executable(
        "head",
        """\
        #!/usr/bin/env bash
        if [ "${1:-}" = "-n" ] && [[ "${2:-}" == -* ]]; then
          trim="${2#-}"
          tmp="$(mktemp)"
          cat > "$tmp"
          total="$(wc -l < "$tmp" | tr -d ' ')"
          keep=$((total - trim))
          if [ "$keep" -gt 0 ]; then
            /usr/bin/sed -n "1,${keep}p" "$tmp"
          fi
          rm -f "$tmp"
          exit 0
        fi
        exec /usr/bin/head "$@"
        """,
    )
    h.write_executable(
        "rclone",
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        echo "$*" >> "$TEST_LOG_DIR/rclone.log"
        case "${1:-}" in
          lsf)
            index=1
            while [ "$index" -le 30 ]; do
              printf 'zammad-backup-%02d.tar.gz\\n' "$index"
              index=$((index + 1))
            done
            ;;
          copy|deletefile)
            exit 0
            ;;
        esac
        """,
    )

    result = h.run_script(
        "zammad_sync.sh",
        "cloud",
        env=h.script_env(TEST_ZAMMAD_VOLUME=volume_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    rclone_log = (h.log_dir / "rclone.log").read_text(encoding="utf-8")
    assert f"copy {volume_path} gdrive:AUTO_BACKUPS/zammad -v" in rclone_log
    assert (
        "deletefile gdrive:AUTO_BACKUPS/zammad/zammad-backup-01.tar.gz"
        in rclone_log
    )
    assert (
        "deletefile gdrive:AUTO_BACKUPS/zammad/zammad-backup-02.tar.gz"
        in rclone_log
    )
    assert "zammad-backup-03.tar.gz" not in rclone_log


def test_certbot_sync_pushes_to_each_edge_node(script_harness):
    h = script_harness
    h.write_executable(
        "ssh",
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        echo "$*" >> "$TEST_LOG_DIR/ssh.log"
        """,
    )
    h.write_executable(
        "rsync",
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        echo "$*" >> "$TEST_LOG_DIR/rsync.log"
        """,
    )

    result = h.run_script(
        "sync_certs.sh",
        env=h.script_env(
            CERTBOT_SOURCE_DIR=h.workdir / "certs",
            CERTBOT_DEST_DIR=h.workdir / "remote-certs",
            CERTBOT_KNOWN_HOSTS=h.workdir / "known_hosts",
        ),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    ssh_log = (h.log_dir / "ssh.log").read_text(encoding="utf-8")
    rsync_log = (h.log_dir / "rsync.log").read_text(encoding="utf-8")
    assert "root@vps-a.example.com" in ssh_log
    assert "root@vps-b.example.com" in ssh_log
    assert "root@vps-a.example.com" in rsync_log
    assert "root@vps-b.example.com" in rsync_log


def test_certbot_sync_stops_when_rsync_fails(script_harness):
    h = script_harness
    h.write_executable(
        "ssh",
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        echo "$*" >> "$TEST_LOG_DIR/ssh.log"
        """,
    )
    h.write_executable(
        "rsync",
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        echo "$*" >> "$TEST_LOG_DIR/rsync.log"
        exit 23
        """,
    )

    result = h.run_script(
        "sync_certs.sh",
        env=h.script_env(
            CERTBOT_SOURCE_DIR=h.workdir / "certs",
            CERTBOT_DEST_DIR=h.workdir / "remote-certs",
            CERTBOT_KNOWN_HOSTS=h.workdir / "known_hosts",
        ),
    )

    assert result.returncode == 23
    ssh_log = (h.log_dir / "ssh.log").read_text(encoding="utf-8")
    assert "root@vps-a.example.com" in ssh_log
    assert "docker restart" not in ssh_log
    assert "root@vps-b.example.com" not in ssh_log
