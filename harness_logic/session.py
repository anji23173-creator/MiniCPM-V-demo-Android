from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    content: str
    timestamp: str = field(default_factory=utc_now_iso)


@dataclass
class CharacterSession:
    session_id: str
    character_id: str
    character_pack_id: str
    story_cutoff: str | None
    selected_model_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    conversation_summary: str = ""
    dynamic_state: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


class JsonSessionStore:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.sessions_dir = root_dir / "sessions"

    def create(
        self,
        character_id: str,
        character_pack_id: str,
        story_cutoff: str | None,
        selected_model_id: str,
        conversation_summary: str = "",
        dynamic_state: dict[str, Any] | None = None,
    ) -> CharacterSession:
        session = CharacterSession(
            session_id=uuid.uuid4().hex,
            character_id=character_id,
            character_pack_id=character_pack_id,
            story_cutoff=story_cutoff,
            selected_model_id=selected_model_id,
            conversation_summary=conversation_summary,
            dynamic_state=dynamic_state or {},
        )
        self.save(session)
        return session

    def get(self, session_id: str) -> CharacterSession:
        path = self._path_for(session_id)
        if not path.is_file():
            raise KeyError(f"Unknown session id: {session_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        turns = [ConversationTurn(**turn) for turn in data.get("turns", [])]
        return CharacterSession(
            session_id=data["session_id"],
            character_id=data["character_id"],
            character_pack_id=data["character_pack_id"],
            story_cutoff=data.get("story_cutoff"),
            selected_model_id=data["selected_model_id"],
            turns=turns,
            conversation_summary=data.get("conversation_summary", ""),
            dynamic_state=data.get("dynamic_state", {}),
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
        )

    def save(self, session: CharacterSession) -> None:
        session.updated_at = utc_now_iso()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._path_for(session.session_id).write_text(
            json.dumps(_session_to_dict(session), indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    def append_turns(self, session_id: str, turns: list[ConversationTurn]) -> CharacterSession:
        session = self.get(session_id)
        session.turns.extend(turns)
        self.save(session)
        return session

    def set_summary(self, session_id: str, summary: str) -> CharacterSession:
        session = self.get(session_id)
        session.conversation_summary = summary
        self.save(session)
        return session

    def _path_for(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"


def _session_to_dict(session: CharacterSession) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "character_id": session.character_id,
        "character_pack_id": session.character_pack_id,
        "story_cutoff": session.story_cutoff,
        "selected_model_id": session.selected_model_id,
        "turns": [turn.__dict__ for turn in session.turns],
        "conversation_summary": session.conversation_summary,
        "dynamic_state": session.dynamic_state,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }
