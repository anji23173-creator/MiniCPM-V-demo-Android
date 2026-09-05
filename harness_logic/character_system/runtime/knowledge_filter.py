from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .retrieval import RetrievedEvent


META_TOPICS = (
    "作者",
    "创作意图",
    "文学评论",
    "读者",
    "这篇小说",
    "本章",
    "章节",
    "角色卡",
    "系统提示",
    "prompt",
)


@dataclass(frozen=True)
class FilterDecision:
    event_id: str
    allowed: bool
    reason: str
    score: float


def event_index(events: list[dict[str, Any]]) -> dict[str, int]:
    return {event["event_id"]: int(event["time_index"]) for event in events}


def filter_by_knowledge_boundary(
    candidates: list[RetrievedEvent],
    npc: dict[str, Any],
    story_cutoff: str,
    events: list[dict[str, Any]],
    query: str,
) -> tuple[list[RetrievedEvent], list[FilterDecision]]:
    indexes = event_index(events)
    if story_cutoff not in indexes:
        raise ValueError(f"unknown story cutoff: {story_cutoff}")
    cutoff_index = indexes[story_cutoff]
    npc_id = npc["npc_id"]
    whitelist = set(npc["knowledge_scope"]["world_fact_refs"])
    decisions: list[FilterDecision] = []
    allowed: list[RetrievedEvent] = []

    if any(topic.lower() in query.lower() for topic in META_TOPICS):
        for candidate in candidates:
            decisions.append(
                FilterDecision(
                    candidate.event["event_id"],
                    False,
                    "meta_or_author_topic",
                    candidate.score,
                )
            )
        return [], decisions

    for candidate in candidates:
        event = candidate.event
        event_id = event["event_id"]
        reason = "authorized"
        is_allowed = True
        if event_id not in whitelist:
            is_allowed, reason = False, "not_in_npc_knowledge_scope"
        elif int(event["time_index"]) > cutoff_index:
            is_allowed, reason = False, "future_event"
        elif npc_id not in event["knowledge_by_character"]:
            is_allowed, reason = False, "no_knowledge_source"
        elif (
            event["knowledge_by_character"][npc_id]["available_after"] not in indexes
            or indexes[event["knowledge_by_character"][npc_id]["available_after"]] > cutoff_index
        ):
            is_allowed, reason = False, "not_yet_learned"
        elif npc_id not in event["visibility"] and "public" not in event["visibility"]:
            is_allowed, reason = False, "visibility_denied"
        decisions.append(FilterDecision(event_id, is_allowed, reason, candidate.score))
        if is_allowed:
            allowed.append(candidate)
    return allowed, decisions
