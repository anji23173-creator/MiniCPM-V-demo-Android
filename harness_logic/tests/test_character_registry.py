import unittest

from harness_logic import CharacterPackRegistry
from harness_logic.constants import DEFAULT_CHARACTER_SYSTEM_ROOT


class CharacterRegistryTests(unittest.TestCase):
    def test_builtin_registry_lists_known_characters(self):
        registry = CharacterPackRegistry.default()
        characters = registry.available_characters()
        ids = [character.character_id for character in characters]

        self.assertIn("lu_jiangxian", ids)
        self.assertIn("xuan_an", ids)
        self.assertEqual("陆江仙", registry.find_character("lu_jiangxian").display_name)

    def test_builtin_character_pack_validates(self):
        result = CharacterPackRegistry.validate_pack_root(DEFAULT_CHARACTER_SYSTEM_ROOT)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(2, result.character_count)
        self.assertEqual(20, result.event_count)


if __name__ == "__main__":
    unittest.main()
