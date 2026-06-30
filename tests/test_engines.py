import tempfile
import unittest
from pathlib import Path

from meet_note_gen.engines import EngineConfig, build_command, validate_engine


class EngineTests(unittest.TestCase):
    def test_missing_executable_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = EngineConfig("qwen3", root / "missing.exe", root / "model")
            status = validate_engine(config)
            self.assertFalse(status.ok)
            self.assertIn("executable missing", status.message)

    def test_whisper_command_contains_model_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "whisper-cli.exe"
            model = root / "ggml-large-v3-turbo-q5_0.bin"
            audio = root / "chunk_001.wav"
            out = root / "chunk_001"
            for path in (exe, model, audio):
                path.write_text("", encoding="utf-8")
            command = build_command(EngineConfig("whisper", exe, model), audio, out)
            self.assertEqual(command[:3], [str(exe), "-m", str(model)])
            self.assertIn("-l", command)
            self.assertIn("ko", command)


if __name__ == "__main__":
    unittest.main()
