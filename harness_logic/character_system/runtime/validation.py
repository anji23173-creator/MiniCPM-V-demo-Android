from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


EVIDENCE_RE = re.compile(r"^(145[3-8]\.txt):L([1-9]\d*)(?:-L([1-9]\d*))?$")
EVENT_RE = re.compile(r"^evt-\d{3}$")
SOURCE_TYPES = {"direct", "witnessed", "reported", "inferred"}


class DataValidationError(ValueError):
    """Raised when character-system data violates its contract."""


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise DataValidationError(f"{path}: expected a JSON object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DataValidationError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise DataValidationError(f"{path}:{line_number}: expected object")
            records.append(record)
    return records


def _require_keys(obj: dict[str, Any], keys: Iterable[str], context: str) -> None:
    missing = set(keys) - set(obj)
    if missing:
        raise DataValidationError(f"{context}: missing keys {sorted(missing)}")


def _require_list(value: Any, context: str, minimum: int = 0, maximum: int | None = None) -> list[Any]:
    if not isinstance(value, list):
        raise DataValidationError(f"{context}: expected array")
    if len(value) < minimum:
        raise DataValidationError(f"{context}: requires at least {minimum} entries")
    if maximum is not None and len(value) > maximum:
        raise DataValidationError(f"{context}: allows at most {maximum} entries")
    return value


def validate_evidence_ref(ref: str, novel_dir: Path) -> None:
    match = EVIDENCE_RE.fullmatch(ref)
    if not match:
        raise DataValidationError(f"invalid evidence reference: {ref}")
    filename, first, last = match.groups()
    path = novel_dir / filename
    if not path.is_file():
        raise DataValidationError(f"evidence file does not exist: {path}")
    with path.open("r", encoding="utf-8") as stream:
        line_count = sum(1 for _ in stream)
    first_line = int(first)
    last_line = int(last or first)
    if first_line > last_line or last_line > line_count:
        raise DataValidationError(
            f"evidence range {ref} exceeds {filename}'s {line_count} lines"
        )


def validate_npc(npc: dict[str, Any], novel_dir: Path) -> None:
    context = f"NPC {npc.get('npc_id', '<unknown>')}"
    _require_keys(
        npc,
        [
            "schema_version",
            "npc_id",
            "identity_core",
            "relationships",
            "knowledge_scope",
            "dynamic_state",
            "episodic_memory",
            "evidence_refs",
        ],
        context,
    )
    if npc["schema_version"] != "1.0.0":
        raise DataValidationError(f"{context}: unsupported schema_version")
    if not isinstance(npc["npc_id"], str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", npc["npc_id"]):
        raise DataValidationError(f"{context}: invalid npc_id")

    identity = npc["identity_core"]
    if not isinstance(identity, dict):
        raise DataValidationError(f"{context}.identity_core: expected object")
    identity_keys = [
        "name",
        "aliases",
        "worldview_position",
        "background",
        "core_motivations",
        "values",
        "psychological_traits",
        "speech_style",
        "behavior_rules",
        "hard_constraints",
    ]
    _require_keys(identity, identity_keys, f"{context}.identity_core")
    _require_list(identity["psychological_traits"], f"{context}.psychological_traits", 8, 12)
    _require_list(identity["speech_style"], f"{context}.speech_style", 2, 8)
    _require_list(identity["hard_constraints"], f"{context}.hard_constraints", 3, 12)

    evidence_map = npc["evidence_refs"]
    if not isinstance(evidence_map, dict) or not evidence_map:
        raise DataValidationError(f"{context}.evidence_refs: expected non-empty object")
    for index in range(len(identity["psychological_traits"])):
        evidence_key = f"identity_core.psychological_traits[{index}]"
        if evidence_key not in evidence_map:
            raise DataValidationError(f"{context}: missing evidence for {evidence_key}")
    for key, refs in evidence_map.items():
        _require_list(refs, f"{context}.evidence_refs.{key}", 1)
        for ref in refs:
            validate_evidence_ref(ref, novel_dir)

    relationships = _require_list(npc["relationships"], f"{context}.relationships")
    for index, relation in enumerate(relationships):
        rel_context = f"{context}.relationships[{index}]"
        _require_keys(
            relation,
            [
                "target_npc_id",
                "target_name",
                "relationship_type",
                "attitude",
                "basis",
                "evidence_refs",
            ],
            rel_context,
        )
        for ref in _require_list(relation["evidence_refs"], f"{rel_context}.evidence_refs", 1):
            validate_evidence_ref(ref, novel_dir)

    scope = npc["knowledge_scope"]
    _require_keys(scope, ["world_fact_refs", "unknown_topics", "story_cutoff"], f"{context}.knowledge_scope")
    if not EVENT_RE.fullmatch(scope["story_cutoff"]):
        raise DataValidationError(f"{context}: invalid story_cutoff")
    for event_id in _require_list(scope["world_fact_refs"], f"{context}.world_fact_refs"):
        if not EVENT_RE.fullmatch(event_id):
            raise DataValidationError(f"{context}: invalid event ref {event_id}")

    state = npc["dynamic_state"]
    _require_keys(
        state,
        ["scene", "emotion", "quest_state", "current_goal", "affinity"],
        f"{context}.dynamic_state",
    )
    emotion = state["emotion"]
    _require_keys(emotion, ["label", "trigger", "intensity", "decay_rule"], f"{context}.emotion")
    if not isinstance(emotion["intensity"], (int, float)) or not 0 <= emotion["intensity"] <= 1:
        raise DataValidationError(f"{context}: emotion intensity must be 0..1")
    if not isinstance(state["affinity"], int) or not -100 <= state["affinity"] <= 100:
        raise DataValidationError(f"{context}: affinity must be integer -100..100")

    for index, memory in enumerate(_require_list(npc["episodic_memory"], f"{context}.episodic_memory")):
        mem_context = f"{context}.episodic_memory[{index}]"
        _require_keys(
            memory,
            ["fact_ref", "valid_from", "valid_to", "source", "visibility", "confidence", "evidence_ref"],
            mem_context,
        )
        if memory["source"] not in SOURCE_TYPES:
            raise DataValidationError(f"{mem_context}: invalid source")
        if not 0 <= memory["confidence"] <= 1:
            raise DataValidationError(f"{mem_context}: confidence must be 0..1")
        validate_evidence_ref(memory["evidence_ref"], novel_dir)


def validate_events(events: list[dict[str, Any]], novel_dir: Path) -> None:
    ids: set[str] = set()
    indexes: set[int] = set()
    required = [
        "event_id",
        "time_index",
        "fact",
        "participants",
        "witnesses",
        "informed_characters",
        "available_after",
        "source_type",
        "importance",
        "confidence",
        "visibility",
        "keywords",
        "evidence_ref",
        "knowledge_by_character",
    ]
    for event in events:
        context = f"event {event.get('event_id', '<unknown>')}"
        _require_keys(event, required, context)
        event_id = event["event_id"]
        if not EVENT_RE.fullmatch(event_id) or event_id in ids:
            raise DataValidationError(f"{context}: invalid or duplicate event_id")
        ids.add(event_id)
        if not isinstance(event["time_index"], int) or event["time_index"] < 1 or event["time_index"] in indexes:
            raise DataValidationError(f"{context}: invalid or duplicate time_index")
        indexes.add(event["time_index"])
        if event["source_type"] not in SOURCE_TYPES | {"narration"}:
            raise DataValidationError(f"{context}: invalid source_type")
        if not 0 <= event["importance"] <= 1 or not 0 <= event["confidence"] <= 1:
            raise DataValidationError(f"{context}: importance/confidence must be 0..1")
        validate_evidence_ref(event["evidence_ref"], novel_dir)
        for npc_id, knowledge in event["knowledge_by_character"].items():
            _require_keys(knowledge, ["source", "available_after", "confidence"], f"{context}.{npc_id}")
            if knowledge["source"] not in SOURCE_TYPES:
                raise DataValidationError(f"{context}.{npc_id}: invalid source")
            if not EVENT_RE.fullmatch(knowledge["available_after"]):
                raise DataValidationError(f"{context}.{npc_id}: invalid available_after")

    for event in events:
        refs = [event["available_after"]]
        refs.extend(item["available_after"] for item in event["knowledge_by_character"].values())
        for ref in refs:
            if ref not in ids:
                raise DataValidationError(f"{event['event_id']}: unknown cutoff reference {ref}")


def validate_cross_references(npcs: list[dict[str, Any]], events: list[dict[str, Any]]) -> None:
    event_ids = {event["event_id"] for event in events}
    npc_ids = {npc["npc_id"] for npc in npcs}
    for npc in npcs:
        refs = set(npc["knowledge_scope"]["world_fact_refs"])
        refs.add(npc["knowledge_scope"]["story_cutoff"])
        refs.update(memory["fact_ref"] for memory in npc["episodic_memory"])
        refs.update(memory["valid_from"] for memory in npc["episodic_memory"])
        refs.update(
            memory["valid_to"]
            for memory in npc["episodic_memory"]
            if memory["valid_to"] is not None
        )
        missing = refs - event_ids
        if missing:
            raise DataValidationError(f"{npc['npc_id']}: unknown event refs {sorted(missing)}")
        for relation in npc["relationships"]:
            target = relation["target_npc_id"]
            if target is not None and target not in npc_ids:
                raise DataValidationError(f"{npc['npc_id']}: unknown target NPC {target}")

    for event in events:
        listed = (
            set(event["participants"])
            | set(event["witnesses"])
            | set(event["informed_characters"])
            | set(event["knowledge_by_character"])
        )
        unknown = {value for value in listed if value not in npc_ids and value != "public"}
        if unknown:
            raise DataValidationError(f"{event['event_id']}: unknown NPC ids {sorted(unknown)}")
