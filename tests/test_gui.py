import unittest
from pathlib import Path

from meet_note_gen.engines import EngineStatus
from meet_note_gen.gui import (
    PRIMARY_ACTION_TEXT,
    _apply_installed_assets,
    _display_path,
    _engine_status_text,
    _model_action_labels,
    _model_status_text,
    _open_path_command,
    _qt_import_error_message,
)
from meet_note_gen.model_catalog import catalog_by_engine


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

    def test_engine_status_text_is_user_facing(self):
        self.assertEqual(_engine_status_text(EngineStatus(True, "Ready")), "준비됨")
        self.assertEqual(_engine_status_text(EngineStatus(False, "Choose runner file")), "Runner 파일 선택 필요")
        self.assertEqual(_engine_status_text(EngineStatus(False, "Choose Windows runner (.exe)")), "Windows 실행파일(.exe) 선택 필요")
        self.assertEqual(_engine_status_text(EngineStatus(False, "Choose model path")), "모델 선택 필요")

    def test_open_path_command_uses_platform_file_manager(self):
        self.assertEqual(_open_path_command("win32", "C:/out"), ["explorer", "C:/out"])
        self.assertEqual(_open_path_command("darwin", "/tmp/out"), ["open", "/tmp/out"])
        self.assertEqual(_open_path_command("linux", "/tmp/out"), ["xdg-open", "/tmp/out"])

    def test_apply_installed_assets_selects_ready_engine_paths(self):
        config = {"engines": {}}

        _apply_installed_assets(config, "sensevoice", "C:/models/sensevoice", "C:/engines/sherpa.exe")

        self.assertEqual(config["selected_engine_id"], "sensevoice")
        self.assertEqual(config["engines"]["sensevoice"]["model_path"], "C:/models/sensevoice")
        self.assertEqual(config["engines"]["sensevoice"]["executable"], "C:/engines/sherpa.exe")

    def test_auto_install_model_uses_one_action_button(self):
        sensevoice = catalog_by_engine()["sensevoice"]
        qwen3 = catalog_by_engine()["qwen3"]

        self.assertEqual(_model_action_labels(sensevoice, EngineStatus(False, "Choose runner file"), False), ("설치하고 사용",))
        self.assertEqual(_model_action_labels(sensevoice, EngineStatus(True, "Ready"), False), ("사용",))
        self.assertEqual(_model_action_labels(sensevoice, EngineStatus(True, "Ready"), True), ("재설치",))
        self.assertEqual(_model_action_labels(qwen3, EngineStatus(False, "Choose runner file"), False), ("사용", "모델 다운로드", "Runner 파일", "모델 폴더"))


if __name__ == "__main__":
    unittest.main()
