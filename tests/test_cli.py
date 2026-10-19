import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chess_pieces_3d.cli import load_profile, main, watch


class CliTests(unittest.TestCase):
    def test_load_reexecutes_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.py"
            path.write_text(
                "from chess_pieces_3d import Profile\nprofile = Profile()\nprofile.line(x=1)\n"
            )
            self.assertEqual(load_profile(path).end, (1, 0))
            path.write_text(
                "from chess_pieces_3d import Profile\nprofile = Profile()\nprofile.line(x=2)\n"
            )
            self.assertEqual(load_profile(path).end, (2, 0))

    def test_missing_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.py"
            path.write_text("profile = 3\n")
            with self.assertRaisesRegex(ValueError, "must define"):
                load_profile(path)

    def test_watch_recovers_after_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.py"
            prefix = "from chess_pieces_3d import Profile\nprofile = Profile()\n"
            path.write_text(prefix + "profile.line(x=1)\n")
            contents = iter([prefix + "profile.line(x=)\n", prefix + "profile.line(x=3)\n"])

            def change_file(_: float) -> None:
                try:
                    source = next(contents)
                except StopIteration:
                    raise KeyboardInterrupt from None
                path.write_text(source)
                stat = path.stat()
                os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

            output, errors = io.StringIO(), io.StringIO()
            with (
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(errors),
                patch("chess_pieces_3d.cli.sleep", side_effect=change_file),
                self.assertRaises(KeyboardInterrupt),
            ):
                watch(path)
            self.assertIn("(1, 0)", output.getvalue())
            self.assertIn("(3, 0)", output.getvalue())
            self.assertEqual(output.getvalue().count("Type"), 2)
            self.assertIn("no current report", errors.getvalue())
            self.assertIn("SyntaxError", errors.getvalue())

    def test_main_exits_nonzero_on_failure(self) -> None:
        output, errors = io.StringIO(), io.StringIO()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(sys, "argv", ["profile-report", str(Path(directory) / "missing.py")]),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
            self.assertRaises(SystemExit) as raised,
        ):
            main()
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("FileNotFoundError", errors.getvalue())

    def test_geometry_import_does_not_load_cadquery(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import chess_pieces_3d, sys; assert 'cadquery' not in sys.modules",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
