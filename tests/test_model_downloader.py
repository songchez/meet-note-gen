import tempfile
import unittest
from pathlib import Path

from meet_note_gen.model_catalog import catalog_by_engine
from meet_note_gen.model_downloader import download_model


class ModelDownloaderTests(unittest.TestCase):
    def test_download_snapshot_model_to_engine_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            entry = catalog_by_engine()["qwen3"]

            def snapshot_download(**kwargs):
                calls.append(kwargs)
                return str(Path(kwargs["local_dir"]))

            path = download_model(Path(tmp), entry, snapshot_download=snapshot_download)

            self.assertEqual(path, Path(tmp) / "models" / "qwen3-asr-0.6b")
            self.assertEqual(calls[0]["repo_id"], "Qwen/Qwen3-ASR-0.6B")

    def test_download_single_whisper_model_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            entry = catalog_by_engine()["whisper"]

            def hf_hub_download(**kwargs):
                calls.append(kwargs)
                return str(Path(kwargs["local_dir"]) / kwargs["filename"])

            path = download_model(Path(tmp), entry, hf_hub_download=hf_hub_download)

            self.assertEqual(path.name, "ggml-large-v3-turbo-q5_0.bin")
            self.assertEqual(calls[0]["repo_id"], "ggerganov/whisper.cpp")
            self.assertEqual(calls[0]["filename"], "ggml-large-v3-turbo-q5_0.bin")


if __name__ == "__main__":
    unittest.main()
