import sys
import tempfile
import unittest
from pathlib import Path

from meet_note_gen.runner import run_command


class RunnerTests(unittest.TestCase):
    def test_run_command_captures_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = run_command([sys.executable, "-c", "print('hello')"], Path(tmp))
            self.assertEqual(output.stdout.strip(), "hello")
            self.assertEqual(output.returncode, 0)

    def test_run_command_replaces_undecodable_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = run_command(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.buffer.write(b'\\xec'); sys.stderr.buffer.write(b'\\xec')",
                ],
                Path(tmp),
            )
            self.assertEqual(output.returncode, 0)
            self.assertTrue(output.stdout)
            self.assertTrue(output.stderr)


if __name__ == "__main__":
    unittest.main()
