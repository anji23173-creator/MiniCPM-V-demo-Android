from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .knowledge_filter import event_index
from .retrieval import RetrievedEvent


@dataclass(frozen=True)
class RetrievedMemory:
    memory: dict[str, Any]
    event: dict[str, Any]
    score: float


def retrieve_episodic_memories(
    npc: dict[str, Any],
    authorized: list[RetrievedEvent],
    events: list[dict[str, Any]],
    story_cutoff: str,
    limit: int = 3,
) -> list[RetrievedMemory]:
    indexes = event_index(events)
    cutoff = indexes[story_cutoff]
    event_by_id = {item["event_id"]: item for item in events}
    score_by_id = {item.event["event_id"]: item.score for item in authorized}
    results: list[RetrievedMemory] = []
    for memory in npc["episodic_memory"]:
        event_id = memory["fact_ref"]
        if event_id not in score_by_id or event_id not in event_by_id:
            continue
        if indexes[memory["valid_from"]] > cutoff:
            continue
        if memory["valid_to"] is not None and indexes[memory["valid_to"]] < cutoff:
            continue
        if npc["npc_id"] not in memory["visibility"] and "public" not in memory["visibility"]:
            continue
        results.append(
            RetrievedMemory(
                memory,
                event_by_id[event_id],
                score_by_id[event_id] * float(memory["confidence"]),
            )
        )
    return sorted(results, key=lambda item: item.score, reverse=True)[:limit]
