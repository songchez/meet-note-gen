import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from meet_note_gen.audio import TimeRange
from meet_note_gen.engines import EngineConfig
from meet_note_gen.jobs import create_job
from meet_note_gen.runner import CommandResult, run_command
from meet_note_gen.transcription import transcribe_job


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for smoke pipeline test")
class SmokePipelineTests(unittest.TestCase):
    def test_transcription_pipeline_creates_chunks_and_merged_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input.wav"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:duration=2",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    str(input_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            job = create_job(root / "jobs", input_path, TimeRange(0, 2), 1, ["qwen3"])
            config = EngineConfig("qwen3", root / "runner.exe", root / "model")
            config.executable.write_text("", encoding="utf-8")
            config.model_path.mkdir()

            def run(command, cwd):
                if command[0] == "ffmpeg":
                    return run_command(command, cwd)
                chunk_name = Path(command[command.index("-i") + 1]).stem
                return CommandResult(command, 0, f"text for {chunk_name}", "")

            output = transcribe_job(job, config, run=run)
            self.assertTrue((job.root / "chunks" / "chunk_001.wav").exists())
            self.assertTrue((job.root / "chunks" / "chunk_002.wav").exists())
            self.assertEqual(output.read_text(encoding="utf-8"), "text for chunk_001\n\ntext for chunk_002\n")


if __name__ == "__main__":
    unittest.main()
