from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .character_pack import CharacterPack, CharacterPackValidationResult, CharacterSpec
from .constants import DEFAULT_CHARACTER_EVIDENCE_ROOT, DEFAULT_CHARACTER_SYSTEM_ROOT


class CharacterRegistryError(ValueError):
    """Raised when character packs cannot be loaded or validated."""


class CharacterPackRegistry:
    def __init__(
        self,
        roots: Iterable[Path],
        evidence_root: Path | None = DEFAULT_CHARACTER_EVIDENCE_ROOT,
    ):
        self.roots = [Path(root).expanduser().resolve() for root in roots]
        self.evidence_root = evidence_root.expanduser().resolve() if evidence_root is not None else None
        self._packs = self._scan()

    @classmethod
    def builtin(
        cls,
        root: Path = DEFAULT_CHARACTER_SYSTEM_ROOT,
        pack_id: str = "builtin_character_system",
        display_name: str = "Built-in character system",
    ) -> "CharacterPackRegistry":
        registry = cls([], evidence_root=DEFAULT_CHARACTER_EVIDENCE_ROOT)
        registry._packs = [
            registry._load_pack(
                Path(root).expanduser().resolve(),
                pack_id_override=pack_id,
                display_name_override=display_name,
            )
        ]
        return registry

    @classmethod
    def default(cls) -> "CharacterPackRegistry":
        return cls.builtin()

    @property
    def packs(self) -> list[CharacterPack]:
        return list(self._packs)

    def available_characters(self) -> list[CharacterSpec]:
        characters: list[CharacterSpec] = []
        for pack in self._packs:
            characters.extend(pack.characters)
        return characters

    def find_character(self, character_id: str) -> CharacterSpec | None:
        for character in self.available_characters():
            if character.character_id == character_id:
                return character
        return None

    def resolve_pack_for_character(self, character_id: str) -> CharacterPack | None:
        for pack in self._packs:
            if any(character.character_id == character_id for character in pack.characters):
                return pack
        return None

    def validate_all(self) -> list[CharacterPackValidationResult]:
        return [self.validate_pack_root(pack.root, self.evidence_root) for pack in self._packs]

    @classmethod
    def validate_pack_root(
        cls,
        root: Path,
        evidence_root: Path | None = DEFAULT_CHARACTER_EVIDENCE_ROOT,
    ) -> CharacterPackValidationResult:
        root = Path(root).expanduser().resolve()
        evidence = evidence_root.expanduser().resolve() if evidence_root is not None else None
        errors: list[str] = []
        pack_id: str | None = None
        character_count = 0
        event_count = 0
        try:
            manifest = _load_manifest(root)
            pack_id = _pack_id(root, manifest, None)
            _require_pack_paths(root)
            character_paths = sorted((root / "characters").glob("*.json"))
            characters = [_load_json(path) for path in character_paths]
            events = _load_jsonl(root / "story" / "story_events.jsonl")
            character_count = len(characters)
            event_count = len(events)
            _validate_unique_character_ids(characters)
            _validate_character_summaries(characters)
            _validate_prompt_file(root)
            _validate_with_character_system_runtime(root, characters, events, evidence)
        except Exception as exc:  # noqa: BLE001 - validation must report all user-facing failures as data errors.
            errors.append(str(exc))
        return CharacterPackValidationResult(
            path=root,
            ok=not errors,
            pack_id=pack_id,
            character_count=character_count,
            event_count=event_count,
            errors=errors,
        )

    def _scan(self) -> list[CharacterPack]:
        packs: list[CharacterPack] = []
        for root in self.roots:
            for pack_root in _candidate_pack_roots(root):
                packs.append(self._load_pack(pack_root))
        _validate_unique_registry_characters(packs)
        return packs

    def _load_pack(
        self,
        root: Path,
        pack_id_override: str | None = None,
        display_name_override: str | None = None,
    ) -> CharacterPack:
        validation = self.validate_pack_root(root, self.evidence_root)
        if not validation.ok:
            raise CharacterRegistryError("; ".join(validation.errors))
        manifest = _load_manifest(root)
        pack_id = _pack_id(root, manifest, pack_id_override)
        display_name = display_name_override or str(manifest.get("display_name") or pack_id)
        schema_version = str(manifest.get("schema_version") or "1.0.0")
        character_specs = [
            _character_spec_from_json(path, pack_id, root)
            for path in sorted((root / "characters").glob("*.json"))
        ]
        return CharacterPack(
            pack_id=pack_id,
            display_name=display_name,
            root=root,
            schema_version=schema_version,
            characters=character_specs,
            characters_dir=root / "characters",
            story_events_path=root / "story" / "story_events.jsonl",
            prompts_dir=root / "prompts",
        )


def _candidate_pack_roots(root: Path) -> list[Path]:
    if _looks_like_character_pack(root):
        return [root]
    candidates = [
        path
        for path in sorted(root.iterdir())
        if path.is_dir() and _looks_like_character_pack(path)
    ]
    return candidates


def _looks_like_character_pack(root: Path) -> bool:
    return (root / "characters").is_dir() and (root / "story").is_dir() and (root / "prompts").is_dir()


def _require_pack_paths(root: Path) -> None:
    if not root.is_dir():
        raise CharacterRegistryError(f"character pack root does not exist: {root}")
    required = [
        root / "characters",
        root / "story" / "story_events.jsonl",
        root / "prompts" / "roleplay_system.prompt",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise CharacterRegistryError(f"missing required character pack paths: {missing}")


def _load_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / "pack.json"
    if not manifest_path.is_file():
        return {}
    value = _load_json(manifest_path)
    if not isinstance(value, dict):
        raise CharacterRegistryError(f"{manifest_path}: expected object")
    return value


def _pack_id(root: Path, manifest: dict[str, Any], override: str | None) -> str:
    value = override or manifest.get("pack_id") or root.name
    if not isinstance(value, str) or not value:
        raise CharacterRegistryError(f"{root}: invalid pack_id")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise CharacterRegistryError(f"{path}: expected JSON object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise CharacterRegistryError(f"{path}:{line_number}: expected JSON object")
            records.append(value)
    return records


def _character_spec_from_json(path: Path, pack_id: str, pack_root: Path) -> CharacterSpec:
    data = _load_json(path)
    identity = data.get("identity_core")
    knowledge = data.get("knowledge_scope")
    if not isinstance(identity, dict):
        raise CharacterRegistryError(f"{path}: missing identity_core")
    if not isinstance(knowledge, dict):
        raise CharacterRegistryError(f"{path}: missing knowledge_scope")
    character_id = data.get("npc_id")
    display_name = identity.get("name")
    aliases = identity.get("aliases", [])
    if not isinstance(character_id, str) or not character_id:
        raise CharacterRegistryError(f"{path}: invalid npc_id")
    if not isinstance(display_name, str) or not display_name:
        display_name = character_id
    if not isinstance(aliases, list):
        aliases = []
    return CharacterSpec(
        character_id=character_id,
        display_name=display_name,
        pack_id=pack_id,
        pack_root=pack_root,
        schema_version=str(data.get("schema_version") or "unknown"),
        story_cutoff=knowledge.get("story_cutoff") if isinstance(knowledge.get("story_cutoff"), str) else None,
        aliases=[str(alias) for alias in aliases],
    )


def _validate_unique_character_ids(characters: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for character in characters:
        character_id = character.get("npc_id")
        if not isinstance(character_id, str) or not character_id:
            raise CharacterRegistryError("character JSON missing valid npc_id")
        if character_id in seen:
            duplicates.add(character_id)
        seen.add(character_id)
    if duplicates:
        raise CharacterRegistryError(f"duplicate character ids: {sorted(duplicates)}")


def _validate_unique_registry_characters(packs: list[CharacterPack]) -> None:
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for pack in packs:
        for character in pack.characters:
            previous = seen.get(character.character_id)
            if previous is not None:
                duplicates.append(f"{character.character_id} in {previous} and {pack.pack_id}")
            seen[character.character_id] = pack.pack_id
    if duplicates:
        raise CharacterRegistryError(f"duplicate character ids across packs: {duplicates}")


def _validate_character_summaries(characters: list[dict[str, Any]]) -> None:
    if not characters:
        raise CharacterRegistryError("character pack must contain at least one character JSON")
    for character in characters:
        identity = character.get("identity_core")
        knowledge = character.get("knowledge_scope")
        if not isinstance(identity, dict) or not identity.get("name"):
            raise CharacterRegistryError(f"{character.get('npc_id', '<unknown>')}: missing identity_core.name")
        if not isinstance(knowledge, dict) or not knowledge.get("story_cutoff"):
            raise CharacterRegistryError(f"{character.get('npc_id', '<unknown>')}: missing knowledge_scope.story_cutoff")


def _validate_prompt_file(root: Path) -> None:
    prompt = root / "prompts" / "roleplay_system.prompt"
    if not prompt.read_text(encoding="utf-8").strip():
        raise CharacterRegistryError(f"{prompt}: prompt file is empty")


def _validate_with_character_system_runtime(
    root: Path,
    characters: list[dict[str, Any]],
    events: list[dict[str, Any]],
    evidence_root: Path | None,
) -> None:
    try:
        from .character_system.runtime.validation import (  # type: ignore[import-not-found]
            validate_cross_references,
            validate_events,
            validate_npc,
        )
    except ImportError:
        validate_cross_references = None
        validate_events = None
        validate_npc = None

    if validate_cross_references is None:
        return

    if evidence_root is not None and evidence_root.is_dir():
        for character in characters:
            validate_npc(character, evidence_root)
        validate_events(events, evidence_root)
    validate_cross_references(characters, events)
