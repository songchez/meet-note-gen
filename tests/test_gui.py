import unittest
from pathlib import Path

from meet_note_gen.gui import _display_path


class GuiTests(unittest.TestCase):
    def test_display_path_hides_empty_path(self):
        self.assertEqual(_display_path(""), ("", ""))
        self.assertEqual(_display_path("."), ("", ""))

    def test_display_path_shortens_long_path_but_keeps_tooltip(self):
        path = Path("/very/long/folder/name/for/models/whisper/ggml-large-v3-turbo-q5_0.bin")
        label, tooltip = _display_path(path)
        self.assertEqual(label, "…/whisper/ggml-large-v3-turbo-q5_0.bin")
        self.assertEqual(tooltip, str(path))


if __name__ == "__main__":
    unittest.main()
