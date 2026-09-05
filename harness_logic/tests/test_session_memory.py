import tempfile
import unittest
from pathlib import Path

from harness_logic import HarnessFacade


class SessionMemoryTests(unittest.TestCase):
    def test_session_turn_is_saved_and_writes_session_memory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            facade = HarnessFacade(Path(temp_dir))
            session = facade.create_character_session(
                character_id="lu_jiangxian",
                story_cutoff="evt-018",
                selected_model_id="llama-3.2-1b-instruct",
            )
            facade.set_selected_model("llama-3.2-1b-instruct")
            files = facade.model_store.get_selected_model_files()
            for path in files.artifact_files.values():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("demo", encoding="utf-8")

            updated, assistant_output, memory = facade.run_session_turn(session.session_id, "你怎么看玄谙？")

            self.assertEqual(2, len(updated.turns))
            self.assertIn("mode=character-chat", assistant_output)
            self.assertEqual("session_memory", memory.kind)
            self.assertEqual(session.session_id, memory.session_id)
            self.assertEqual("lu_jiangxian", memory.character_id)
            memories = facade.list_memories(session_id=session.session_id)
            self.assertEqual([memory.memory_id], [record.memory_id for record in memories])

    def test_explicit_character_memory_can_be_searched(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            facade = HarnessFacade(Path(temp_dir))
            memory = facade.add_memory(
                text="玩家曾帮助陆江仙保守洞华天秘密",
                kind="character_memory",
                character_id="lu_jiangxian",
                importance=0.8,
            )

            hits = facade.search_memories(character_id="lu_jiangxian", query="洞华天")

            self.assertEqual(memory.memory_id, hits[0].record.memory_id)
            self.assertEqual("character_memory", hits[0].record.kind)

    def test_invalid_story_cutoff_is_rejected_when_creating_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            facade = HarnessFacade(Path(temp_dir))

            with self.assertRaisesRegex(ValueError, "Unknown story cutoff"):
                facade.create_character_session(
                    character_id="lu_jiangxian",
                    story_cutoff="啥都不知道",
                    selected_model_id="llama-3.2-1b-instruct",
                )


if __name__ == "__main__":
    unittest.main()
