import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


class RenderedBackupScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[1]
        cls.render_root = Path(tempfile.mkdtemp())
        env = os.environ.copy()
        env.update(
            {
                "ANSIBLE_HOME": str(cls.repo_root / ".ansible"),
                "ANSIBLE_LOCAL_TEMP": "/tmp/ansible-local",
                "ANSIBLE_REMOTE_TEMP": "/tmp/ansible-remote",
                "ANSIBLE_COLLECTIONS_PATH": str(cls.repo_root / ".ansible/collections"),
                "TEST_RENDER_DIR": str(cls.render_root),
            }
        )
        subprocess.run(
            [
                "ansible-playbook",
                "-i",
                ".local.example/inventory.yml",
                "tests/render_shell_templates.yml",
            ],
            cwd=cls.repo_root,
            env=env,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.render_root)

    def setUp(self):
        self.workdir = Path(tempfile.mkdtemp())
        self.fake_bin = self.workdir / "fake-bin"
        self.fake_bin.mkdir()
        self.log_dir = self.workdir / "logs"
        self.log_dir.mkdir()
        self.write_common_fakes()

    def tearDown(self):
        shutil.rmtree(self.workdir)

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
            if [[ "$args" == *"-printf"* ]]; then
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

    def test_postgres_backup_success_creates_archives_and_uploads(self):
        backup_dir = self.workdir / "postgres-backups"
        custom_dir = self.workdir / "custom-data"
        custom_dir.mkdir()
        (custom_dir / "asset.txt").write_text("custom asset\n", encoding="utf-8")
        self.write_executable(
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

        result = self.run_script(
            "pg_backup_all.sh",
            env=self.script_env(
                POSTGRES_BACKUP_DIR=backup_dir,
                POSTGRES_CUSTOM_DATA_DIR=custom_dir,
            ),
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(list(backup_dir.glob("pg_sql_*.sql.gz"))), 1)
        self.assertEqual(len(list(backup_dir.glob("pg_custom_data_*.tar.gz"))), 1)
        self.assertIn("copy", (self.log_dir / "rclone.log").read_text(encoding="utf-8"))

    def test_caddy_backup_success_excludes_its_own_script(self):
        caddy_dir = self.workdir / "caddy"
        caddy_dir.mkdir()
        (caddy_dir / "Caddyfile").write_text("example.com\n", encoding="utf-8")
        (caddy_dir / "caddy_backup.sh").write_text("skip me\n", encoding="utf-8")
        backup_dir = self.workdir / "caddy-backups"

        result = self.run_script(
            "caddy_backup.sh",
            env=self.script_env(CADDY_TARGET_DIR=caddy_dir, CADDY_BACKUP_ROOT=backup_dir),
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        archives = list(backup_dir.glob("caddy_backup_*.tar.gz"))
        self.assertEqual(len(archives), 1)
        listing = subprocess.run(
            ["tar", "-tzf", str(archives[0])],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(listing.returncode, 0, listing.stdout + listing.stderr)
        self.assertIn("caddy/Caddyfile", listing.stdout)
        self.assertNotIn("caddy/caddy_backup.sh", listing.stdout)

    def test_mailcow_backup_success_packages_latest_backup_directory(self):
        mailcow_dir = self.workdir / "mailcow"
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
        backup_dir = self.workdir / "mailcow-backups"

        result = self.run_script(
            "mailcow_backup.sh",
            env=self.script_env(MAILCOW_DIR=mailcow_dir, MAILCOW_BACKUP_ROOT=backup_dir),
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        archives = list(backup_dir.glob("mailcow_backup_*.tar.gz"))
        self.assertEqual(len(archives), 1)
        self.assertFalse((backup_dir / "mailcow-test").exists())

    def test_zammad_local_backup_runs_compose_backup_command(self):
        zammad_dir = self.workdir / "zammad"
        zammad_dir.mkdir()
        self.write_executable(
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

        result = self.run_script(
            "zammad_sync.sh",
            "local",
            env=self.script_env(ZAMMAD_DIR=zammad_dir),
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        docker_log = (self.log_dir / "docker.log").read_text(encoding="utf-8")
        self.assertIn("compose exec -T zammad-backup", docker_log)

    def test_certbot_sync_pushes_to_each_edge_node(self):
        self.write_executable(
            "ssh",
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            echo "$*" >> "$TEST_LOG_DIR/ssh.log"
            """,
        )
        self.write_executable(
            "rsync",
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            echo "$*" >> "$TEST_LOG_DIR/rsync.log"
            """,
        )

        result = self.run_script(
            "sync_certs.sh",
            env=self.script_env(
                CERTBOT_SOURCE_DIR=self.workdir / "certs",
                CERTBOT_DEST_DIR=self.workdir / "remote-certs",
                CERTBOT_KNOWN_HOSTS=self.workdir / "known_hosts",
            ),
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        ssh_log = (self.log_dir / "ssh.log").read_text(encoding="utf-8")
        rsync_log = (self.log_dir / "rsync.log").read_text(encoding="utf-8")
        self.assertIn("root@vps-a.example.com", ssh_log)
        self.assertIn("root@vps-b.example.com", ssh_log)
        self.assertIn("root@vps-a.example.com", rsync_log)
        self.assertIn("root@vps-b.example.com", rsync_log)


if __name__ == "__main__":
    unittest.main()
