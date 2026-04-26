import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from collect_all_files import merge_contents


class CollectAllFilesTest(unittest.TestCase):
    def test_default_skips_local_and_binary_like_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("public notes\n", encoding="utf-8")
            (root / "secret.vault").write_text("vault payload\n", encoding="utf-8")
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("git internals\n", encoding="utf-8")
            (root / ".local").mkdir()
            (root / ".local" / "token.txt").write_text("private token\n", encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                output_path = merge_contents("all_files.txt", project_root=root)

            output = output_path.read_text(encoding="utf-8")
            self.assertIn("FILE: README.md", output)
            self.assertIn("public notes", output)
            self.assertNotIn("private token", output)
            self.assertNotIn("vault payload", output)
            self.assertNotIn("git internals", output)

    def test_include_local_follows_local_symlink_when_requested(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink support is unavailable")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            private_state = base / "private-state"
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
            self.assertIn("FILE: public.txt", output)
            self.assertIn("FILE: .local/token.txt", output)
            self.assertIn("private token", output)


if __name__ == "__main__":
    unittest.main()
