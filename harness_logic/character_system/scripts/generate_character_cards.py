from __future__ import annotations

import argparse
import json
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


NOVEL_FILES = [f"{number}.txt" for number in range(1453, 1459)]


def build_extraction_request(npc_names: list[str]) -> str:
    prompt = (ROOT / "prompts" / "character_extraction.prompt").read_text(encoding="utf-8")
    parts = [
        prompt,
        "",
        "指定角色：" + "、".join(npc_names),
        "",
        "【带稳定行号的小说原文】",
    ]
    for filename in NOVEL_FILES:
        path = ROOT.parent / filename
        lines = path.read_text(encoding="utf-8").splitlines()
        parts.append(f"\n### {filename}")
        parts.extend(f"{filename}:L{index} {line}" for index, line in enumerate(lines, 1))
    return "\n".join(parts)


def build_report() -> str:
    novel_dir = ROOT.parent
    events = load_jsonl(ROOT / "story" / "story_events.jsonl")
    npcs = [load_json(path) for path in sorted((ROOT / "characters").glob("*.json"))]
    for npc in npcs:
        validate_npc(npc, novel_dir)
    validate_events(events, novel_dir)
    validate_cross_references(npcs, events)

    lines = [
        "# 角色卡人工检查报告",
        "",
        f"- 已校验角色：{len(npcs)}",
        f"- 公共事件：{len(events)}",
        "- 证据范围：1453.txt–1458.txt（稳定行号）",
        "- 推断处理：事件 source_type/confidence 与角色获知方式分别记录",
        "",
    ]
    for npc in npcs:
        identity = npc["identity_core"]
        lines.extend(
            [
                f"## {identity['name']}（{npc['npc_id']}）",
                "",
                f"- 世界位置：{identity['worldview_position']}",
                f"- 默认截止点：{npc['knowledge_scope']['story_cutoff']}",
                f"- 心理特征数：{len(identity['psychological_traits'])}",
                f"- 关系数：{len(npc['relationships'])}",
                f"- 情节记忆数：{len(npc['episodic_memory'])}",
                "",
                "### 核心心理特征与证据",
                "",
            ]
        )
        for index, trait in enumerate(identity["psychological_traits"]):
            refs = "、".join(
                npc["evidence_refs"][f"identity_core.psychological_traits[{index}]"]
            )
            lines.append(f"- {trait}（{refs}）")
        lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare and verify the card-generation workflow.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="Build a line-numbered extraction request")
    prepare.add_argument("--npc", nargs="+", default=["陆江仙", "玄谙"])
    prepare.add_argument("--output", type=Path)
    report = subparsers.add_parser("report", help="Validate data and build the review report")
    report.add_argument("--output", type=Path)
    return parser.parse_args()


def emit(text: str, output: Path | None) -> None:
    if output is None:
        print(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")
    print(f"wrote {output.resolve()}")


def main() -> int:
    args = parse_args()
    if args.command == "prepare":
        emit(build_extraction_request(args.npc), args.output)
    else:
        emit(build_report(), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
