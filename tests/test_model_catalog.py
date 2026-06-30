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


if __name__ == "__main__":
    unittest.main()
