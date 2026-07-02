import tempfile
import unittest
from pathlib import Path

from meet_note_gen.engines import ENGINE_HOME_PAGES, ENGINE_NAMES, EngineConfig, build_command, validate_engine


class EngineTests(unittest.TestCase):
    def test_missing_executable_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = EngineConfig("qwen3", root / "missing.exe", root / "model")
            status = validate_engine(config)
            self.assertFalse(status.ok)
            self.assertEqual(status.message, "Choose runner file")

    def test_empty_paths_are_invalid(self):
        status = validate_engine(EngineConfig("qwen3", Path(""), Path("")))
        self.assertFalse(status.ok)
        self.assertEqual(status.message, "Choose runner file")

    def test_missing_model_is_invalid_after_runner_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "qwen_asr.exe"
            exe.write_text("", encoding="utf-8")
            status = validate_engine(EngineConfig("qwen3", exe, Path("")))
            self.assertFalse(status.ok)
            self.assertEqual(status.message, "Choose model path")

    def test_non_windows_runner_file_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / "model.bin"
            runner.write_text("", encoding="utf-8")
            model = root / "model"
            model.mkdir()
            status = validate_engine(EngineConfig("qwen3", runner, model))
            self.assertFalse(status.ok)
            self.assertEqual(status.message, "Choose Windows runner (.exe)")

    def test_sensevoice_rejects_microphone_demo_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / "sherpa-onnx-non-streaming-asr-x64-v1.13.3.exe"
            runner.write_text("", encoding="utf-8")
            model = root / "model"
            model.mkdir()

            status = validate_engine(EngineConfig("sensevoice", runner, model))

            self.assertFalse(status.ok)
            self.assertEqual(status.message, "Choose sherpa offline runner")

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

    def test_sensevoice_command_uses_sherpa_offline_args(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / "sherpa-onnx-offline.exe"
            model = root / "sensevoice"
            audio = root / "chunk_001.wav"
            out = root / "chunk_001"
            model.mkdir()
            for path in (exe, model / "model.int8.onnx", model / "tokens.txt", audio):
                path.write_text("", encoding="utf-8")

            command = build_command(EngineConfig("sensevoice", exe, model), audio, out)

            self.assertEqual(command[0], str(exe))
            self.assertIn(f"--tokens={model / 'tokens.txt'}", command)
            self.assertIn(f"--sense-voice-model={model / 'model.int8.onnx'}", command)
            self.assertIn("--sense-voice-language=ko", command)
            self.assertEqual(command[-1], str(audio))

    def test_every_engine_has_install_page(self):
        self.assertEqual(set(ENGINE_HOME_PAGES), set(ENGINE_NAMES))


if __name__ == "__main__":
    unittest.main()
