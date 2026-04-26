import os
import shutil
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def encrypt_workspace(tmp_path):
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    shutil.copy(REPO_ROOT / "encrypt_.local_folder.sh", tmp_path)

    fake_vault = fake_bin / "ansible-vault"
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
    return tmp_path, fake_bin


def run_encrypt_script(workdir, fake_bin):
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        ["./encrypt_.local_folder.sh"],
        cwd=workdir,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )


def test_fails_when_local_directory_is_missing(encrypt_workspace):
    workdir, fake_bin = encrypt_workspace

    result = run_encrypt_script(workdir, fake_bin)

    assert result.returncode == 1
    assert "找不到 .local" in result.stdout + result.stderr


def test_archives_local_content_and_removes_temporary_archive(encrypt_workspace):
    workdir, fake_bin = encrypt_workspace
    local_dir = workdir / ".local"
    local_dir.mkdir()
    (local_dir / "token.txt").write_text("secret-token\n", encoding="utf-8")

    result = run_encrypt_script(workdir, fake_bin)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (workdir / ".local_encrypted.vault").stat().st_size > 0
    assert not (workdir / ".local.tar.gz").exists()

    archive = subprocess.run(
        ["tar", "-tzf", ".local_encrypted.vault"],
        cwd=workdir,
        check=False,
        text=True,
        capture_output=True,
    )
    assert archive.returncode == 0, archive.stdout + archive.stderr
    assert ".local/token.txt" in archive.stdout
