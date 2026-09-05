from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CharacterSpec:
    character_id: str
    display_name: str
    pack_id: str
    pack_root: Path
    schema_version: str
    story_cutoff: str | None = None
    aliases: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CharacterPack:
    pack_id: str
    display_name: str
    root: Path
    schema_version: str
    characters: list[CharacterSpec]
    characters_dir: Path
    story_events_path: Path
    prompts_dir: Path


@dataclass(frozen=True)
class CharacterPackValidationResult:
    path: Path
    ok: bool
    pack_id: str | None
    character_count: int
    event_count: int
    errors: list[str] = field(default_factory=list)
