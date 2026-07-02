import tempfile
import tarfile
import unittest
from io import BytesIO
from pathlib import Path

from meet_note_gen.model_catalog import catalog_by_engine
from meet_note_gen.model_downloader import download_model, install_engine_assets, select_runner_asset


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

    def test_select_runner_asset_prefers_windows_offline_package(self):
        entry = catalog_by_engine()["sensevoice"]
        release = {
            "assets": [
                {"name": "sherpa-onnx-non-streaming-asr-x86-v1.13.3.exe", "browser_download_url": "https://example/x86.exe"},
                {"name": "sherpa-onnx-non-streaming-asr-x64-v1.13.3.exe", "browser_download_url": "https://example/x64.exe"},
                {
                    "name": "sherpa-onnx-v1.13.3-win-x64-shared-MD-Release-no-tts.tar.bz2",
                    "browser_download_url": "https://example/offline.tar.bz2",
                },
            ]
        }

        asset = select_runner_asset(release, entry.runner_asset_pattern)

        self.assertEqual(asset["name"], "sherpa-onnx-v1.13.3-win-x64-shared-MD-Release-no-tts.tar.bz2")
        self.assertEqual(asset["browser_download_url"], "https://example/offline.tar.bz2")

    def test_install_engine_assets_downloads_model_and_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = catalog_by_engine()["sensevoice"]
            snapshot_calls = []
            fetched_repos = []
            downloaded = []

            def snapshot_download(**kwargs):
                snapshot_calls.append(kwargs)
                return str(Path(kwargs["local_dir"]))

            def release_fetcher(repo):
                fetched_repos.append(repo)
                return {
                    "assets": [
                        {
                            "name": "sherpa-onnx-v1.13.3-win-x64-shared-MD-Release-no-tts.tar.bz2",
                            "browser_download_url": "https://example/runner.tar.bz2",
                        }
                    ]
                }

            def file_downloader(url, target):
                downloaded.append((url, target))
                with tarfile.open(target, "w:bz2") as archive:
                    data = b"MZ"
                    info = tarfile.TarInfo("sherpa/bin/sherpa-onnx-offline.exe")
                    info.size = len(data)
                    archive.addfile(info, BytesIO(data))

            assets = install_engine_assets(
                Path(tmp),
                entry,
                snapshot_download=snapshot_download,
                release_fetcher=release_fetcher,
                file_downloader=file_downloader,
            )

            self.assertEqual(assets.model_path, Path(tmp) / "models" / "sensevoice-small-int8")
            self.assertEqual(assets.runner_path, Path(tmp) / "engines" / "sensevoice" / "sherpa" / "bin" / "sherpa-onnx-offline.exe")
            self.assertTrue(assets.runner_path.exists())
            self.assertEqual(snapshot_calls[0]["repo_id"], entry.hf_repo_id)
            self.assertEqual(fetched_repos, ["k2-fsa/sherpa-onnx"])
            self.assertEqual(downloaded[0][0], "https://example/runner.tar.bz2")


if __name__ == "__main__":
    unittest.main()
