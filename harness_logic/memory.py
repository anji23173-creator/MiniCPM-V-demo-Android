from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .session import CharacterSession, utc_now_iso


MemoryKind = Literal[
    "session_memory",
    "summary_memory",
    "profile_memory",
    "character_memory",
    "world_memory",
]


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    scope: str
    kind: MemoryKind
    text: str
    importance: float
    confidence: float
    created_at: str
    updated_at: str
    owner_id: str | None = None
    character_id: str | None = None
    session_id: str | None = None
    expires_at: str | None = None
    source_turn_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievedMemory:
    record: MemoryRecord
    score: float


class JsonlMemoryStore:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.memory_dir = root_dir / "memory"
        self.memory_path = self.memory_dir / "memories.jsonl"

    def append(self, record: MemoryRecord) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        with self.memory_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_memory_to_dict(record), ensure_ascii=False, sort_keys=True) + "\n")

    def list_records(
        self,
        session_id: str | None = None,
        character_id: str | None = None,
        kind: str | None = None,
    ) -> list[MemoryRecord]:
        records = self._read_all(include_deleted=False)
        return [
            record
            for record in records
            if (session_id is None or record.session_id == session_id)
            and (character_id is None or record.character_id == character_id)
            and (kind is None or record.kind == kind)
        ]

    def search(
        self,
        query: str,
        session_id: str | None = None,
        character_id: str | None = None,
        limit: int = 5,
    ) -> list[RetrievedMemory]:
        query_terms = _terms(query)
        candidates = self.list_records(session_id=session_id, character_id=character_id)
        scored: list[RetrievedMemory] = []
        for record in candidates:
            text_terms = _terms(record.text)
            overlap = len(query_terms & text_terms)
            substring_bonus = 1 if query and query in record.text else 0
            score = overlap + substring_bonus + record.importance
            if score > 0:
                scored.append(RetrievedMemory(record=record, score=round(score, 5)))
        scored.sort(key=lambda item: (item.score, item.record.updated_at), reverse=True)
        return scored[:limit]

    def delete(self, memory_id: str) -> bool:
        records = self._read_all(include_deleted=True)
        found = any(record.memory_id == memory_id and record.metadata.get("deleted") is not True for record in records)
        if not found:
            return False
        deleted = MemoryRecord(
            memory_id=memory_id,
            scope="delete_marker",
            kind="session_memory",
            text="",
            importance=0,
            confidence=1,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
            metadata={"deleted": True},
        )
        self.append(deleted)
        return True

    def _read_all(self, include_deleted: bool) -> list[MemoryRecord]:
        if not self.memory_path.is_file():
            return []
        records_by_id: dict[str, MemoryRecord] = {}
        deleted_ids: set[str] = set()
        with self.memory_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = _memory_from_dict(json.loads(line))
                if record.metadata.get("deleted") is True:
                    deleted_ids.add(record.memory_id)
                    if include_deleted:
                        records_by_id[record.memory_id] = record
                    else:
                        records_by_id.pop(record.memory_id, None)
                    continue
                if record.memory_id not in deleted_ids:
                    records_by_id[record.memory_id] = record
        return list(records_by_id.values())


class MemoryManager:
    def __init__(self, store: JsonlMemoryStore):
        self.store = store

    def add_memory(
        self,
        text: str,
        kind: MemoryKind = "session_memory",
        scope: str = "session",
        character_id: str | None = None,
        session_id: str | None = None,
        importance: float = 0.5,
        confidence: float = 1.0,
        owner_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        if not text.strip():
            raise ValueError("memory text must not be empty")
        now = utc_now_iso()
        record = MemoryRecord(
            memory_id=uuid.uuid4().hex,
            scope=scope,
            kind=kind,
            text=text.strip(),
            importance=max(0.0, min(1.0, importance)),
            confidence=max(0.0, min(1.0, confidence)),
            created_at=now,
            updated_at=now,
            owner_id=owner_id,
            character_id=character_id,
            session_id=session_id,
            tags=tags or [],
            metadata=metadata or {},
        )
        self.store.append(record)
        return record

    def observe_turn(
        self,
        session: CharacterSession,
        user_input: str,
        assistant_output: str,
    ) -> MemoryRecord:
        return self.add_memory(
            text=f"玩家：{user_input.strip()}\n角色：{assistant_output.strip()}",
            kind="session_memory",
            scope="session",
            character_id=session.character_id,
            session_id=session.session_id,
            importance=0.4,
            confidence=1.0,
            metadata={"source": "session_chat"},
        )

    def list_records(
        self,
        session_id: str | None = None,
        character_id: str | None = None,
        kind: str | None = None,
    ) -> list[MemoryRecord]:
        return self.store.list_records(session_id=session_id, character_id=character_id, kind=kind)

    def search(
        self,
        query: str,
        session_id: str | None = None,
        character_id: str | None = None,
        limit: int = 5,
    ) -> list[RetrievedMemory]:
        return self.store.search(query, session_id=session_id, character_id=character_id, limit=limit)

    def delete(self, memory_id: str) -> bool:
        return self.store.delete(memory_id)


def _memory_to_dict(record: MemoryRecord) -> dict[str, Any]:
    return {
        "memory_id": record.memory_id,
        "scope": record.scope,
        "kind": record.kind,
        "text": record.text,
        "importance": record.importance,
        "confidence": record.confidence,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "owner_id": record.owner_id,
        "character_id": record.character_id,
        "session_id": record.session_id,
        "expires_at": record.expires_at,
        "source_turn_ids": record.source_turn_ids,
        "tags": record.tags,
        "metadata": record.metadata,
    }


def _memory_from_dict(data: dict[str, Any]) -> MemoryRecord:
    return MemoryRecord(
        memory_id=data["memory_id"],
        scope=data["scope"],
        kind=data["kind"],
        text=data.get("text", ""),
        importance=float(data.get("importance", 0)),
        confidence=float(data.get("confidence", 1)),
        created_at=data.get("created_at", utc_now_iso()),
        updated_at=data.get("updated_at", utc_now_iso()),
        owner_id=data.get("owner_id"),
        character_id=data.get("character_id"),
        session_id=data.get("session_id"),
        expires_at=data.get("expires_at"),
        source_turn_ids=list(data.get("source_turn_ids", [])),
        tags=list(data.get("tags", [])),
        metadata=dict(data.get("metadata", {})),
    )


def _terms(value: str) -> set[str]:
    normalized = value.lower()
    tokens = {token for token in normalized.replace("\n", " ").split(" ") if token}
    chinese_chars = {char for char in normalized if "\u4e00" <= char <= "\u9fff"}
    return tokens | chinese_chars
