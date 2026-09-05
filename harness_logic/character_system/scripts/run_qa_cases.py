from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.prompt_compiler import PromptCompiler, RuntimeContext  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile prompts for the existing novel_test/qa.json questions."
    )
    parser.add_argument("--npc", required=True, choices=["lu_jiangxian", "xuan_an"])
    parser.add_argument("--cutoff", default="evt-018")
    parser.add_argument("--max-chars", type=int, default=4500)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = json.loads((ROOT.parent / "qa.json").read_text(encoding="utf-8"))
    compiler = PromptCompiler(ROOT)
    output = []
    for case in cases[: args.limit]:
        compiled = compiler.build_npc_prompt(
            args.npc,
            case["question"],
            RuntimeContext(story_cutoff=args.cutoff, max_chars=args.max_chars),
        )
        output.append(
            {
                "id": case["id"],
                "question": case["question"],
                "reference_answer_for_human_review": case["answer"],
                "messages": compiled.messages,
                "authorized_event_ids": [
                    item["event_id"]
                    for item in compiled.debug["retrieval_decisions"]
                    if item["allowed"]
                ],
                "denied_events": [
                    {"event_id": item["event_id"], "reason": item["reason"]}
                    for item in compiled.debug["retrieval_decisions"]
                    if not item["allowed"]
                ],
            }
        )
    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.output.resolve()}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
