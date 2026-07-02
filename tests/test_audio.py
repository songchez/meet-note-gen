import tempfile
import unittest
from pathlib import Path

from meet_note_gen.audio import (
    TimeRange,
    build_chunk_commands,
    build_export_segment_commands,
    build_ffprobe_duration_command,
    build_waveform_image_command,
    parse_duration,
    selected_range,
    split_evenly,
)


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

    def test_waveform_image_command_outputs_png_preview(self):
        command = build_waveform_image_command("in.mp3", "waveform.png", 1200, 180)
        self.assertEqual(command[:4], ["ffmpeg", "-y", "-i", "in.mp3"])
        self.assertTrue(any("showwavespic=s=1200x180" in part for part in command))
        self.assertEqual(command[-3:], ["-frames:v", "1", "waveform.png"])

    def test_export_segment_commands_split_selected_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands = build_export_segment_commands("in.mp3", Path(tmp), TimeRange(60, 180), 3)
            self.assertEqual(len(commands), 3)
            self.assertEqual(commands[0][0:6], ["ffmpeg", "-y", "-ss", "60.000", "-t", "40.000"])
            self.assertEqual(commands[-1][-1], str(Path(tmp) / "segment_003.wav"))

    def test_export_segment_commands_allow_single_trimmed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands = build_export_segment_commands("in.mp3", Path(tmp), TimeRange(60, 180), 1)
            self.assertEqual(len(commands), 1)
            self.assertEqual(commands[0][0:6], ["ffmpeg", "-y", "-ss", "60.000", "-t", "120.000"])
            self.assertEqual(commands[0][-1], str(Path(tmp) / "segment_001.wav"))

    def test_ffprobe_duration_command_is_machine_readable(self):
        self.assertEqual(
            build_ffprobe_duration_command("in.mp3"),
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                "in.mp3",
            ],
        )

    def test_parse_duration_rejects_bad_ffprobe_output(self):
        self.assertEqual(parse_duration("123.456\n"), 123.456)
        with self.assertRaisesRegex(ValueError, "Could not read audio duration"):
            parse_duration("N/A")

    def test_selected_range_applies_cut_last(self):
        self.assertEqual(selected_range(600, 60, 0, 120), TimeRange(60, 480))
        self.assertEqual(selected_range(600, 60, 300, 0), TimeRange(60, 300))

    def test_selected_range_clamps_small_ui_rounding_past_duration(self):
        self.assertEqual(selected_range(123.456, 0, 123.5, 0), TimeRange(0, 123.456))
        with self.assertRaisesRegex(ValueError, "end must be within audio duration"):
            selected_range(123.456, 0, 130, 0)


if __name__ == "__main__":
    unittest.main()
