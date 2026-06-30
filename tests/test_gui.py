import unittest
from pathlib import Path

from meet_note_gen.gui import _display_path, _qt_import_error_message


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


if __name__ == "__main__":
    unittest.main()
