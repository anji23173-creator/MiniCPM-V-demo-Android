import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from harness_logic.cli import build_arg_parser, main
from harness_logic.constants import DEFAULT_HARNESS_ROOT


class CliTests(unittest.TestCase):
    def test_list_command_prints_known_model(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["list"])
        self.assertEqual(0, code)
        self.assertIn("minicpm-v-4", out.getvalue())

    def test_default_root_is_project_data_dir(self):
        args = build_arg_parser().parse_args(["status"])
        self.assertEqual(DEFAULT_HARNESS_ROOT, args.root)

    def test_character_list_prints_known_character(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["character-list"])
        self.assertEqual(0, code)
        self.assertIn("lu_jiangxian", out.getvalue())

    def test_character_pack_validate_builtin(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["character-pack", "validate"])
        self.assertEqual(0, code)
        self.assertIn("OK: pack_id=character_system", out.getvalue())

    def test_character_prompt_prints_messages_without_debug_by_default(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(
                [
                    "character-prompt",
                    "--character",
                    "lu_jiangxian",
                    "--input",
                    "玄谙究竟是什么？",
                    "--cutoff",
                    "evt-010",
                ]
            )
        value = out.getvalue()
        self.assertEqual(0, code)
        self.assertIn('"messages"', value)
        self.assertNotIn('"debug"', value)

    def test_character_chat_runs_through_mock_backend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(
                    [
                        "--root",
                        str(Path(temp_dir)),
                        "character-chat",
                        "--backend",
                        "mock",
                        "--model",
                        "llama-3.2-1b-instruct",
                        "--character",
                        "xuan_an",
                        "--input",
                        "你为什么停止拼合七枚鉴身碎片？",
                        "--cutoff",
                        "evt-018",
                        "--touch-demo-files",
                    ]
                )
            self.assertEqual(0, code)
            self.assertIn("mode=character-chat", out.getvalue())

    def test_session_new_and_memory_add_cli(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_out = io.StringIO()
            with redirect_stdout(session_out):
                code = main(
                    [
                        "--root",
                        str(Path(temp_dir)),
                        "session-new",
                        "--character",
                        "lu_jiangxian",
                        "--cutoff",
                        "evt-018",
                        "--model",
                        "llama-3.2-1b-instruct",
                    ]
                )
            self.assertEqual(0, code)
            session_id = json.loads(session_out.getvalue())["session_id"]

            memory_out = io.StringIO()
            with redirect_stdout(memory_out):
                code = main(
                    [
                        "--root",
                        str(Path(temp_dir)),
                        "memory-add",
                        "--session",
                        session_id,
                        "--character",
                        "lu_jiangxian",
                        "--text",
                        "玩家记得玄谙",
                    ]
                )
            self.assertEqual(0, code)
            self.assertEqual(session_id, json.loads(memory_out.getvalue())["session_id"])


if __name__ == "__main__":
    unittest.main()
