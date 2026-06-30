import json
import tempfile
import unittest
from pathlib import Path

from meet_note_gen.audio import TimeRange
from meet_note_gen.jobs import Job, create_job


class JobTests(unittest.TestCase):
    def test_create_job_writes_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = create_job(Path(tmp), "meeting.mp3", TimeRange(0, 1200), 600, ["qwen3"])
            state = json.loads((job.root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["input_path"], "meeting.mp3")
            self.assertEqual(state["chunks"][0]["name"], "chunk_001")

    def test_pending_chunks_skip_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = create_job(Path(tmp), "meeting.mp3", TimeRange(0, 1200), 600, ["qwen3"])
            job.mark_done("qwen3", "chunk_001", "hello")
            loaded = Job.load(job.root)
            self.assertEqual(
                [chunk["name"] for chunk in loaded.pending_chunks("qwen3")],
                ["chunk_002"],
            )


if __name__ == "__main__":
    unittest.main()
