import tempfile
import unittest
from pathlib import Path

from harness_logic.store import LlamaModelStore


class StoreTests(unittest.TestCase):
    def test_select_model_and_artifact_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LlamaModelStore(Path(tmp))
            store.set_selected_model("llama-3.2-1b-instruct")
            files = store.get_selected_model_files()
            self.assertEqual("llama-3.2-1b-instruct", files.model.id)
            self.assertEqual(["llm"], list(files.artifact_files))
            self.assertFalse(store.is_selected_model_downloaded())

    def test_touching_required_artifact_makes_text_model_downloaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LlamaModelStore(Path(tmp))
            store.set_selected_model("llama-3.2-1b-instruct")
            files = store.get_selected_model_files()
            llm_path = files.artifact_files["llm"]
            llm_path.parent.mkdir(parents=True)
            llm_path.write_text("demo", encoding="utf-8")
            self.assertTrue(store.is_selected_model_downloaded())


if __name__ == "__main__":
    unittest.main()
