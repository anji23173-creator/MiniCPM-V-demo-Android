from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.validation import (  # noqa: E402
    load_json,
    load_jsonl,
    validate_cross_references,
    validate_events,
    validate_npc,
)


def main() -> int:
    novel_dir = ROOT.parent
    npc_paths = sorted((ROOT / "characters").glob("*.json"))
    npcs = [load_json(path) for path in npc_paths]
    events = load_jsonl(ROOT / "story" / "story_events.jsonl")
    for npc in npcs:
        validate_npc(npc, novel_dir)
    validate_events(events, novel_dir)
    validate_cross_references(npcs, events)
    print(f"OK: {len(npcs)} NPC cards, {len(events)} shared events, all references valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
