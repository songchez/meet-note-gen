import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

from meet_note_gen.audio import TimeRange
from meet_note_gen.zip_export import build_split_zip_plan, create_zip_archive


class ZipExportTests(unittest.TestCase):
    def test_build_split_zip_plan_uses_twenty_minute_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_split_zip_plan(
                Path("meeting.mp3"),
                Path(tmp),
                TimeRange(0, 2500),
                now=datetime(2026, 7, 2, 13, 30, 0),
            )

            self.assertEqual(plan.zip_path.name, "meeting-20min-chunks-20260702-133000.zip")
            self.assertEqual(len(plan.commands), 3)
            self.assertEqual(plan.commands[0][3:6], ["0.000", "-t", "1200.000"])
            self.assertEqual(plan.commands[1][3:6], ["1200.000", "-t", "1200.000"])
            self.assertEqual(plan.commands[2][3:6], ["2400.000", "-t", "100.000"])
            self.assertEqual([path.name for path in plan.chunk_paths], ["chunk_001.wav", "chunk_002.wav", "chunk_003.wav"])

    def test_create_zip_archive_adds_chunk_files_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chunk_1 = root / "chunk_001.wav"
            chunk_2 = root / "chunk_002.wav"
            chunk_1.write_bytes(b"one")
            chunk_2.write_bytes(b"two")
            zip_path = root / "chunks.zip"

            create_zip_archive(zip_path, [chunk_1, chunk_2])

            with zipfile.ZipFile(zip_path) as archive:
                self.assertEqual(archive.namelist(), ["chunk_001.wav", "chunk_002.wav"])
                self.assertEqual(archive.read("chunk_001.wav"), b"one")


if __name__ == "__main__":
    unittest.main()
