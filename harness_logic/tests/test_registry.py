import unittest

from harness_logic import HarnessCapability, HarnessDownloadSourceType, HarnessModelRegistry


class RegistryTests(unittest.TestCase):
    def test_available_specs_are_generated(self):
        specs = HarnessModelRegistry.available_specs()
        self.assertGreaterEqual(len(specs), 6)
        self.assertEqual("minicpm-v-4", specs[0].id)

    def test_v46_capabilities_and_artifacts(self):
        spec = HarnessModelRegistry.find_spec("minicpm-v-4_6-instruct")
        self.assertIsNotNone(spec)
        self.assertIn(HarnessCapability.TEXT, spec.capabilities)
        self.assertIn(HarnessCapability.VISION, spec.capabilities)
        self.assertIn(HarnessCapability.VIDEO, spec.capabilities)
        self.assertEqual(["llm", "vision_projector"], [artifact.id for artifact in spec.artifacts])

    def test_minicpm5_2b_modelscope_source(self):
        spec = HarnessModelRegistry.find_spec("minicpm5-2b")
        self.assertIsNotNone(spec)
        self.assertEqual("MiniCPM5-2B-Q4_K_M.gguf", spec.artifacts[0].file_name)
        self.assertEqual(1, len(spec.download_sources))
        source = spec.download_sources[0]
        self.assertEqual(HarnessDownloadSourceType.MODELSCOPE, source.type)
        self.assertEqual("OpenBMB/MiniCPM5-2B-gguf", source.repo)
        self.assertEqual("master", source.branch)
        self.assertFalse(HarnessModelRegistry.find_legacy_model("minicpm5-2b").enable_thinking)


if __name__ == "__main__":
    unittest.main()
