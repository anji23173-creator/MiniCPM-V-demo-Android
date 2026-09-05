import tempfile
import unittest
from pathlib import Path

from harness_logic.download import LlamaDownloadManager
from harness_logic.store import LlamaModelStore


class DownloadPlanTests(unittest.TestCase):
    def test_hf_modelscope_plan_for_default_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LlamaModelStore(Path(tmp))
            plan = LlamaDownloadManager(store).build_download_plan()
        urls = [candidate.url for candidate in plan]
        self.assertTrue(any("huggingface.co/openbmb/MiniCPM-V-4-gguf" in url for url in urls))
        self.assertTrue(any("modelscope.cn/models/OpenBMB/MiniCPM-V-4-gguf" in url for url in urls))


if __name__ == "__main__":
    unittest.main()
