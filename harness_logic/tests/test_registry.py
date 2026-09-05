import unittest

from harness_logic import HarnessCapability, HarnessModelRegistry


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


if __name__ == "__main__":
    unittest.main()
