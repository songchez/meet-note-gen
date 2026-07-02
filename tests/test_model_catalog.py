import unittest

from meet_note_gen.model_catalog import catalog_by_engine, catalog_entries, default_engine_id


class ModelCatalogTests(unittest.TestCase):
    def test_catalog_has_recommended_models_with_download_links(self):
        entries = catalog_entries()
        self.assertGreaterEqual(len(entries), 3)
        self.assertEqual(entries[0].engine_id, "sensevoice")
        self.assertTrue(entries[0].recommended)
        for entry in entries:
            self.assertTrue(entry.name)
            self.assertTrue(entry.summary)
            self.assertTrue(entry.download_url.startswith("https://"))
            self.assertTrue(entry.hf_repo_id)
            self.assertTrue(entry.local_dir)
            self.assertTrue(entry.runner_label)
            self.assertTrue(entry.model_label)

    def test_catalog_can_be_looked_up_by_engine(self):
        catalog = catalog_by_engine()
        self.assertIn("qwen3", catalog)
        self.assertEqual(catalog["qwen3"].name, "Qwen3-ASR 0.6B")

    def test_default_engine_is_first_recommended_auto_install_choice(self):
        self.assertEqual(default_engine_id(), "sensevoice")

    def test_default_engine_can_auto_install_windows_runner(self):
        entry = catalog_by_engine()[default_engine_id()]
        self.assertEqual(entry.runner_repo, "k2-fsa/sherpa-onnx")
        self.assertEqual(entry.runner_asset_pattern, "sherpa-onnx-v*-win-x64-shared-MD-Release-no-tts.tar.bz2")
        self.assertEqual(entry.runner_executable, "bin/sherpa-onnx-offline.exe")


if __name__ == "__main__":
    unittest.main()
