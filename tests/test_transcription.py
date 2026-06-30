import json
import tempfile
import unittest
from pathlib import Path

from meet_note_gen.audio import TimeRange
from meet_note_gen.engines import EngineConfig
from meet_note_gen.jobs import create_job
from meet_note_gen.runner import CommandResult
from meet_note_gen.transcription import merge_transcript, transcribe_job


class TranscriptionTests(unittest.TestCase):
    def test_transcribe_job_marks_stdout_chunks_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = create_job(root, "meeting.mp3", TimeRange(0, 1200), 600, ["qwen3"])
            config = EngineConfig("qwen3", root / "runner.exe", root / "model")
            config.executable.write_text("", encoding="utf-8")
            config.model_path.mkdir()

            def run(command, cwd):
                return CommandResult(command, 0, "hello", "")

            transcribe_job(job, config, run=run, prepare_chunks=False)
            loaded = job.load(job.root)
            self.assertEqual(loaded.pending_chunks("qwen3"), [])
            self.assertEqual((job.root / "results" / "qwen3" / "chunk_001.txt").read_text(), "hello")

    def test_transcribe_job_reads_engine_written_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = create_job(root, "meeting.mp3", TimeRange(0, 600), 600, ["whisper"])
            config = EngineConfig("whisper", root / "whisper.exe", root / "model.bin")
            config.executable.write_text("", encoding="utf-8")
            config.model_path.write_text("", encoding="utf-8")

            def run(command, cwd):
                output_stem = Path(command[-1])
                output_stem.with_suffix(".txt").write_text("from file", encoding="utf-8")
                return CommandResult(command, 0, "", "")

            transcribe_job(job, config, run=run, prepare_chunks=False)
            self.assertEqual((job.root / "results" / "whisper" / "chunk_001.txt").read_text(), "from file")

    def test_merge_transcript_writes_ordered_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = create_job(root, "meeting.mp3", TimeRange(0, 1200), 600, ["qwen3"])
            job.mark_done("qwen3", "chunk_002", "second")
            job.mark_done("qwen3", "chunk_001", "first")
            output = merge_transcript(job, "qwen3")
            self.assertEqual(output.read_text(encoding="utf-8"), "first\n\nsecond\n")
            data = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual([chunk["text"] for chunk in data["chunks"]], ["first", "second"])

    def test_transcribe_job_can_stop_before_next_chunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = create_job(root, "meeting.mp3", TimeRange(0, 1200), 600, ["qwen3"])
            config = EngineConfig("qwen3", root / "runner.exe", root / "model")
            config.executable.write_text("", encoding="utf-8")
            config.model_path.mkdir()

            with self.assertRaisesRegex(RuntimeError, "Job stopped"):
                transcribe_job(job, config, run=lambda command, cwd: CommandResult(command, 0, "", ""), prepare_chunks=False, should_stop=lambda: True)


if __name__ == "__main__":
    unittest.main()
