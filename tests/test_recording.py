from datetime import datetime
import tempfile
import unittest
from pathlib import Path

from meet_note_gen.recording import next_recording_path


class RecordingTests(unittest.TestCase):
    def test_next_recording_path_uses_timestamped_m4a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = next_recording_path(Path(tmp), datetime(2026, 6, 30, 13, 45, 5))
            self.assertEqual(path, Path(tmp) / "recordings" / "recording-20260630-134505.m4a")

    def test_next_recording_path_avoids_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "recordings" / "recording-20260630-134505.m4a"
            existing.parent.mkdir()
            existing.write_text("", encoding="utf-8")
            path = next_recording_path(root, datetime(2026, 6, 30, 13, 45, 5))
            self.assertEqual(path, root / "recordings" / "recording-20260630-134505-02.m4a")


if __name__ == "__main__":
    unittest.main()
