import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


class EncryptLocalFolderTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.workdir = Path(tempfile.mkdtemp())
        self.fake_bin = self.workdir / "fake-bin"
        self.fake_bin.mkdir()
        shutil.copy(self.repo_root / "encrypt_.local_folder.sh", self.workdir)

        fake_vault = self.fake_bin / "ansible-vault"
        fake_vault.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail

                if [ "$1" != "encrypt" ]; then
                    echo "unsupported ansible-vault command: $1" >&2
                    exit 2
                fi

                input="$2"
                shift 2
                output=""

                while [ "$#" -gt 0 ]; do
                    case "$1" in
                        --output)
                            output="$2"
                            shift 2
                            ;;
                        *)
                            shift
                            ;;
                    esac
                done

                if [ -z "$output" ]; then
                    echo "missing --output" >&2
                    exit 2
                fi

                cp "$input" "$output"
                """
            ),
            encoding="utf-8",
        )
        fake_vault.chmod(fake_vault.stat().st_mode | stat.S_IXUSR)

    def tearDown(self):
        shutil.rmtree(self.workdir)

    def run_script(self):
        env = os.environ.copy()
        env["PATH"] = f"{self.fake_bin}{os.pathsep}{env['PATH']}"
        return subprocess.run(
            ["./encrypt_.local_folder.sh"],
            cwd=self.workdir,
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )

    def test_fails_when_local_directory_is_missing(self):
        result = self.run_script()

        self.assertEqual(result.returncode, 1)
        self.assertIn("找不到 .local", result.stdout + result.stderr)

    def test_archives_local_content_and_removes_temporary_archive(self):
        local_dir = self.workdir / ".local"
        local_dir.mkdir()
        (local_dir / "token.txt").write_text("secret-token\n", encoding="utf-8")

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.workdir / ".local_encrypted.vault").stat().st_size > 0)
        self.assertFalse((self.workdir / ".local.tar.gz").exists())

        archive = subprocess.run(
            ["tar", "-tzf", ".local_encrypted.vault"],
            cwd=self.workdir,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(archive.returncode, 0, archive.stdout + archive.stderr)
        self.assertIn(".local/token.txt", archive.stdout)


if __name__ == "__main__":
    unittest.main()
