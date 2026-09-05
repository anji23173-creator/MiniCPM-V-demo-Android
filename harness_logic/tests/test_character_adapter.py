import unittest

from harness_logic import CharacterPromptAdapter, CharacterTurnRequest


class CharacterAdapterTests(unittest.TestCase):
    def test_compile_character_turn_returns_system_and_user_messages(self):
        adapter = CharacterPromptAdapter()

        turn = adapter.compile_turn(
            CharacterTurnRequest(
                character_id="lu_jiangxian",
                user_input="玄谙究竟是什么？",
                story_cutoff="evt-010",
            )
        )

        self.assertEqual("lu_jiangxian", turn.character_id)
        self.assertEqual(["system", "user"], [message["role"] for message in turn.messages])
        self.assertIn("陆江仙", turn.messages[0]["content"])
        self.assertEqual("玄谙究竟是什么？", turn.messages[1]["content"])
        self.assertIn("retrieval_decisions", turn.debug)
        self.assertNotIn("retrieval_decisions", str(turn.messages))


if __name__ == "__main__":
    unittest.main()
