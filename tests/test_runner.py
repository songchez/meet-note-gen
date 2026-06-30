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


if __name__ == "__main__":
    unittest.main()
