import unittest
from pathlib import Path

from meet_note_gen.gui import (
    PRIMARY_ACTION_TEXT,
    _display_path,
    _model_status_text,
    _open_path_command,
    _qt_import_error_message,
)


class GuiTests(unittest.TestCase):
    def test_display_path_hides_empty_path(self):
        self.assertEqual(_display_path(""), ("", ""))
        self.assertEqual(_display_path("."), ("", ""))

    def test_display_path_shortens_long_path_but_keeps_tooltip(self):
        path = Path("/very/long/folder/name/for/models/whisper/ggml-large-v3-turbo-q5_0.bin")
        label, tooltip = _display_path(path)
        self.assertEqual(label, "…/whisper/ggml-large-v3-turbo-q5_0.bin")
        self.assertEqual(tooltip, str(path))

    def test_qt_import_error_message_includes_runtime_error(self):
        message = _qt_import_error_message(ImportError("libEGL.so.1 missing"))
        self.assertIn("PySide6/Qt runtime is not available", message)
        self.assertIn("libEGL.so.1 missing", message)

    def test_primary_action_text_is_user_facing(self):
        self.assertEqual(PRIMARY_ACTION_TEXT, "스크립트 추출")

    def test_model_status_text_guides_missing_setup(self):
        self.assertEqual(_model_status_text("Qwen3-ASR 0.6B", True), "모델: Qwen3-ASR 0.6B 준비됨")
        self.assertEqual(_model_status_text("Qwen3-ASR 0.6B", False), "모델 설정 필요")

    def test_open_path_command_uses_platform_file_manager(self):
        self.assertEqual(_open_path_command("win32", "C:/out"), ["explorer", "C:/out"])
        self.assertEqual(_open_path_command("darwin", "/tmp/out"), ["open", "/tmp/out"])
        self.assertEqual(_open_path_command("linux", "/tmp/out"), ["xdg-open", "/tmp/out"])


if __name__ == "__main__":
    unittest.main()
