from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .knowledge_filter import filter_by_knowledge_boundary
from .memory_retriever import RetrievedMemory, retrieve_episodic_memories
from .retrieval import KeywordRetriever, RetrievedEvent, StoryRetriever
from .validation import load_json, load_jsonl, validate_events, validate_npc


SOURCE_LABELS = {
    "direct": "亲历",
    "witnessed": "目击",
    "reported": "听说",
    "inferred": "推断",
}


@dataclass(frozen=True)
class RuntimeContext:
    story_cutoff: str | None = None
    dynamic_state: dict[str, Any] | None = None
    max_chars: int = 4500
    top_k: int = 8
    conversation_summary: str = ""


@dataclass
class CompiledPrompt:
    messages: list[dict[str, str]]
    debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"messages": self.messages, "debug": self.debug}


class PromptCompiler:
    def __init__(
        self,
        root: Path | str,
        retriever: StoryRetriever | None = None,
        validate_on_load: bool = True,
    ) -> None:
        self.root = Path(root).resolve()
        self.novel_dir = self.root.parent
        self.retriever = retriever or KeywordRetriever()
        self.events = load_jsonl(self.root / "story" / "story_events.jsonl")
        self.events_by_id = {event["event_id"]: event for event in self.events}
        self.template = (self.root / "prompts" / "roleplay_system.prompt").read_text(
            encoding="utf-8"
        )
        self._npc_cache: dict[str, dict[str, Any]] = {}
        if validate_on_load:
            validate_events(self.events, self.novel_dir)

    def load_npc(self, npc_id: str) -> dict[str, Any]:
        if npc_id not in self._npc_cache:
            path = self.root / "characters" / f"{npc_id}.json"
            if not path.is_file():
                raise KeyError(f"unknown NPC: {npc_id}")
            npc = load_json(path)
            validate_npc(npc, self.novel_dir)
            self._npc_cache[npc_id] = npc
        return self._npc_cache[npc_id]

    def build_npc_prompt(
        self, npc_id: str, user_input: str, runtime_context: RuntimeContext | None = None
    ) -> CompiledPrompt:
        if not user_input.strip():
            raise ValueError("user_input must not be empty")
        context = runtime_context or RuntimeContext()
        if context.max_chars < 400:
            raise ValueError("max_chars must be at least 400")
        npc = self.load_npc(npc_id)
        cutoff = context.story_cutoff or npc["knowledge_scope"]["story_cutoff"]
        if cutoff not in self.events_by_id:
            raise ValueError(f"unknown story cutoff: {cutoff}")

        candidates = self.retriever.retrieve(user_input, self.events, limit=max(context.top_k * 2, 12))
        authorized, decisions = filter_by_knowledge_boundary(
            candidates, npc, cutoff, self.events, user_input
        )
        authorized = authorized[: context.top_k]
        memories = retrieve_episodic_memories(
            npc, authorized, self.events, cutoff, limit=3
        )
        memory_ids = {memory.event["event_id"] for memory in memories}
        fact_candidates = [item for item in authorized if item.event["event_id"] not in memory_ids]
        relationships = self._select_relationships(npc, user_input)
        dynamic_state = self._merge_state(npc["dynamic_state"], context.dynamic_state)

        mandatory = {
            "global_summary": self._compile_global_summary(npc, cutoff),
            "core_personality": self._compile_core_personality(npc),
            "story_cutoff": self._format_cutoff(cutoff),
            "dynamic_state": self._compile_dynamic_state(dynamic_state),
            "relevant_relationships": "本轮未检索到必须注入的人物关系。",
            "authorized_story_facts": "本轮没有可授权且相关的剧情事实；不要用常识补全。",
            "retrieved_memories": "本轮没有相关的个人经历；未知时按角色方式表达不确定。",
            "conversation_summary": context.conversation_summary.strip() or "无。",
        }
        content = self._render(mandatory)
        optional_items: list[tuple[str, str, str, float]] = []
        for relation in relationships:
            text = (
                f"- {relation['target_name']}｜{relation['relationship_type']}｜"
                f"{relation['attitude']}"
            )
            optional_items.append(("relevant_relationships", relation["target_name"], text, 2.0))
        for item in fact_candidates:
            optional_items.append(
                (
                    "authorized_story_facts",
                    item.event["event_id"],
                    self._format_fact(item, npc_id),
                    item.score + float(item.event["importance"]),
                )
            )
        for memory in memories:
            optional_items.append(
                (
                    "retrieved_memories",
                    memory.event["event_id"],
                    self._format_memory(memory),
                    memory.score + 0.5,
                )
            )
        optional_items.sort(key=lambda item: item[3], reverse=True)

        selected: list[dict[str, Any]] = []
        dropped: list[dict[str, Any]] = []
        section_lines: dict[str, list[str]] = {
            "relevant_relationships": [],
            "authorized_story_facts": [],
            "retrieved_memories": [],
        }
        for section, item_id, text, priority in optional_items:
            proposed_lines = {key: list(value) for key, value in section_lines.items()}
            proposed_lines[section].append(text)
            values = dict(mandatory)
            for key, lines in proposed_lines.items():
                if lines:
                    values[key] = "\n".join(lines)
            proposed = self._render(values)
            if len(proposed) <= context.max_chars:
                section_lines = proposed_lines
                content = proposed
                selected.append({"kind": section, "id": item_id, "priority": round(priority, 5)})
            else:
                dropped.append({"kind": section, "id": item_id, "reason": "character_budget"})

        mandatory_size = len(self._render(mandatory))
        debug = {
            "npc_id": npc_id,
            "story_cutoff": cutoff,
            "max_chars": context.max_chars,
            "prompt_chars": len(content),
            "mandatory_chars": mandatory_size,
            "budget_exceeded_by_mandatory": mandatory_size > context.max_chars,
            "selected_items": selected,
            "dropped_items": dropped,
            "retrieval_decisions": [
                {
                    "event_id": decision.event_id,
                    "allowed": decision.allowed,
                    "reason": decision.reason,
                    "score": decision.score,
                }
                for decision in decisions
            ],
        }
        return CompiledPrompt(
            messages=[
                {"role": "system", "content": content},
                {"role": "user", "content": user_input},
            ],
            debug=debug,
        )

    def _render(self, values: dict[str, str]) -> str:
        rendered = self.template
        for key, value in values.items():
            rendered = rendered.replace("{{" + key + "}}", value)
        if "{{" in rendered or "}}" in rendered:
            raise ValueError("shared prompt contains an unresolved placeholder")
        return rendered.strip()

    def _compile_global_summary(self, npc: dict[str, Any], cutoff: str) -> str:
        identity = npc["identity_core"]
        return "\n".join(
            [
                f"身份：我是{identity['name']}（别名：{'、'.join(identity['aliases']) or '无'}）。",
                f"世界位置：{identity['worldview_position']}",
                "主要背景：" + "；".join(identity["background"]),
                "核心动机：" + "；".join(identity["core_motivations"]),
                f"当前剧情阶段：{self._format_cutoff(cutoff)}",
            ]
        )

    def _compile_core_personality(self, npc: dict[str, Any]) -> str:
        identity = npc["identity_core"]
        return "\n".join(
            [
                "价值观：" + "；".join(identity["values"]),
                "心理与行为：" + "；".join(identity["psychological_traits"]),
                "表达规律：" + "；".join(identity["speech_style"]),
                "稳定行为：" + "；".join(identity["behavior_rules"]),
                "绝对约束：" + "；".join(identity["hard_constraints"]),
            ]
        )

    def _compile_dynamic_state(self, state: dict[str, Any]) -> str:
        emotion = state["emotion"]
        return "\n".join(
            [
                f"地点：{state['scene']}",
                f"任务：{state['quest_state']}",
                f"当前目标：{state['current_goal']}",
                (
                    f"情绪：{emotion['label']}（强度 {emotion['intensity']:.2f}）；"
                    f"触发：{emotion['trigger']}；变化：{emotion['decay_rule']}"
                ),
                f"对玩家亲近度：{state['affinity']}",
            ]
        )

    def _format_cutoff(self, cutoff: str) -> str:
        event = self.events_by_id[cutoff]
        return f"{cutoff}（叙事序号 {event['time_index']}）"

    def _format_fact(self, item: RetrievedEvent, npc_id: str) -> str:
        event = item.event
        source = SOURCE_LABELS[event["knowledge_by_character"][npc_id]["source"]]
        certainty = "可能/推断：" if float(event["confidence"]) < 0.9 else ""
        return f"- {certainty}{event['fact']}〔{source}，可信度 {event['confidence']:.2f}〕"

    def _format_memory(self, item: RetrievedMemory) -> str:
        source = SOURCE_LABELS[item.memory["source"]]
        certainty = "我推断：" if item.memory["source"] == "inferred" else ""
        return (
            f"- {certainty}{item.event['fact']}"
            f"〔{source}，记忆可信度 {item.memory['confidence']:.2f}〕"
        )

    def _select_relationships(self, npc: dict[str, Any], query: str) -> list[dict[str, Any]]:
        selected = []
        for relation in npc["relationships"]:
            if relation["target_name"] in query:
                selected.append(relation)
        if not selected and any(term in query for term in ("关系", "怎么看", "他", "祂", "他们")):
            selected = npc["relationships"][:2]
        return selected

    @staticmethod
    def _merge_state(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
        merged = json.loads(json.dumps(base, ensure_ascii=False))
        if not override:
            return merged
        for key, value in override.items():
            if key == "emotion" and isinstance(value, dict):
                merged["emotion"].update(value)
            elif key in merged:
                merged[key] = value
        return merged
