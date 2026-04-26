import contextlib
import io
import os

import pytest

from collect_all_files import merge_contents


def test_default_skips_local_and_binary_like_files(tmp_path):
    root = tmp_path
    (root / "README.md").write_text("public notes\n", encoding="utf-8")
    (root / "secret.vault").write_text("vault payload\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("git internals\n", encoding="utf-8")
    (root / ".local").mkdir()
    (root / ".local" / "token.txt").write_text("private token\n", encoding="utf-8")

    with contextlib.redirect_stdout(io.StringIO()):
        output_path = merge_contents("all_files.txt", project_root=root)

    output = output_path.read_text(encoding="utf-8")
    assert "FILE: README.md" in output
    assert "public notes" in output
    assert "private token" not in output
    assert "vault payload" not in output
    assert "git internals" not in output


def test_include_local_follows_local_symlink_when_requested(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlink support is unavailable")

    root = tmp_path / "repo"
    private_state = tmp_path / "private-state"
    root.mkdir()
    private_state.mkdir()
    (root / "public.txt").write_text("public\n", encoding="utf-8")
    (private_state / "token.txt").write_text("private token\n", encoding="utf-8")
    (root / ".local").symlink_to(private_state, target_is_directory=True)

    with contextlib.redirect_stdout(io.StringIO()):
        output_path = merge_contents(
            "all_files.txt",
            include_local=True,
            project_root=root,
        )

    output = output_path.read_text(encoding="utf-8")
    assert "FILE: public.txt" in output
    assert "FILE: .local/token.txt" in output
    assert "private token" in output
