import tempfile
import unittest
from pathlib import Path

from meet_note_gen.audio import TimeRange, build_chunk_commands, split_evenly


class AudioTests(unittest.TestCase):
    def test_split_evenly_covers_duration_without_overlap(self):
        self.assertEqual(
            split_evenly(100.0, 3),
            [
                TimeRange(0.0, 33.333),
                TimeRange(33.333, 66.667),
                TimeRange(66.667, 100.0),
            ],
        )

    def test_invalid_range_rejected(self):
        with self.assertRaisesRegex(ValueError, "start must be before end"):
            TimeRange(10, 5).validate(100)

    def test_ffmpeg_chunk_command_uses_16k_mono(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            commands = build_chunk_commands("in.mp3", output_dir, TimeRange(0, 1200), 600)
            self.assertEqual(len(commands), 2)
            self.assertEqual(commands[0][:4], ["ffmpeg", "-y", "-ss", "0.000"])
            self.assertEqual(
                commands[0][-6:],
                ["-vn", "-ac", "1", "-ar", "16000", str(output_dir / "chunk_001.wav")],
            )


if __name__ == "__main__":
    unittest.main()
