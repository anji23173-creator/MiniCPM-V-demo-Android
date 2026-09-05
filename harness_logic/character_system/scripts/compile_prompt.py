from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.prompt_compiler import PromptCompiler, RuntimeContext  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile one NPC turn into chat messages.")
    parser.add_argument("--npc", required=True, help="NPC id, e.g. lu_jiangxian")
    parser.add_argument("--input", required=True, help="Player input")
    parser.add_argument("--cutoff", help="Story event cutoff, e.g. evt-018")
    parser.add_argument("--max-chars", type=int, default=4500)
    parser.add_argument("--debug", action="store_true", help="Include local debug metadata")
    parser.add_argument("--output", type=Path, help="Write UTF-8 JSON to this path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    compiler = PromptCompiler(ROOT)
    compiled = compiler.build_npc_prompt(
        args.npc,
        args.input,
        RuntimeContext(story_cutoff=args.cutoff, max_chars=args.max_chars),
    )
    payload = {"messages": compiled.messages}
    if args.debug:
        payload["debug"] = compiled.debug
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.output.resolve()}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
