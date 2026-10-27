from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

THREE_BODY_SOURCE = ROOT.parent / "three_body_2.txt"
THREE_BODY_ROOT = ROOT / "generated" / "three_body_2"


def _read_novel(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError(f"无法识别小说编码：{path}")


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _summary(text: str, limit: int = 260) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact if len(compact) <= limit else compact[:limit].rstrip() + "……"


def _segment(text: str, source_id: str, document_id: str, target_chars: int) -> list[dict[str, object]]:
    lines = text.splitlines()
    scenes: list[dict[str, object]] = []
    start = 0
    while start < len(lines):
        while start < len(lines) and not lines[start].strip():
            start += 1
        if start >= len(lines):
            break
        end = start
        size = 0
        while end < len(lines):
            size += len(lines[end]) + 1
            end += 1
            if size >= target_chars:
                break
        body = "\n".join(lines[start:end]).strip()
        if body:
            scene_index = len(scenes) + 1
            scenes.append({
                "scene_id": f"scene-{scene_index:04d}",
                "document_id": document_id,
                "source_id": source_id,
                "scene_index": scene_index,
                "line_start": start + 1,
                "line_end": end,
                "sequence_start": start + 1,
                "sequence_end": end,
                "segmentation_method": "paragraph_target_chars",
                "text": body,
            })
        start = end
    return scenes


def _create_sqlite(
    path: Path,
    document: dict[str, object],
    scenes: list[dict[str, object]],
    entities: list[dict[str, object]],
    aliases: list[dict[str, object]],
    mentions: list[dict[str, object]],
    events: list[dict[str, object]],
    claims: list[dict[str, object]],
    evidence: list[dict[str, object]],
    knowledge_edges: list[dict[str, object]],
    relations: list[dict[str, object]],
    snapshots: list[dict[str, object]],
    cutoffs: dict[str, dict[str, int]],
) -> None:
    temp = path.with_suffix(".tmp.sqlite3")
    if temp.exists():
        temp.unlink()
    connection = sqlite3.connect(temp)
    try:
        connection.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE cutoffs(event_id TEXT PRIMARY KEY, story_order INTEGER NOT NULL, sequence INTEGER NOT NULL);
        CREATE TABLE documents(document_id TEXT PRIMARY KEY, source_id TEXT UNIQUE NOT NULL, origin TEXT NOT NULL, source_tier TEXT NOT NULL, sha256 TEXT NOT NULL, line_count INTEGER NOT NULL, char_count INTEGER NOT NULL);
        CREATE TABLE scenes(scene_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, source_id TEXT NOT NULL, scene_index INTEGER NOT NULL, line_start INTEGER NOT NULL, line_end INTEGER NOT NULL, sequence_start INTEGER NOT NULL, sequence_end INTEGER NOT NULL, text TEXT NOT NULL);
        CREATE TABLE entities(entity_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, canonical_name TEXT NOT NULL, identity_kind TEXT NOT NULL, resolution_status TEXT NOT NULL, description TEXT NOT NULL);
        CREATE TABLE aliases(alias_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, alias TEXT NOT NULL, alias_type TEXT NOT NULL, confidence REAL NOT NULL);
        CREATE TABLE entity_mentions(mention_id TEXT PRIMARY KEY, scene_id TEXT NOT NULL, surface TEXT NOT NULL, entity_id TEXT, line INTEGER NOT NULL, resolution_status TEXT NOT NULL, resolution_method TEXT NOT NULL, confidence REAL NOT NULL);
        CREATE TABLE utterances(utterance_id TEXT PRIMARY KEY, scene_id TEXT NOT NULL, speaker_id TEXT, speaker_resolution_method TEXT NOT NULL, line_start INTEGER NOT NULL, line_end INTEGER NOT NULL, text TEXT NOT NULL, confidence REAL NOT NULL);
        CREATE TABLE events(event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, summary TEXT NOT NULL, story_order INTEGER, narrative_sequence INTEGER NOT NULL, participants_json TEXT NOT NULL, witnesses_json TEXT NOT NULL, informed_json TEXT NOT NULL, source_tier TEXT NOT NULL, verification_status TEXT NOT NULL);
        CREATE TABLE claims(claim_id TEXT PRIMARY KEY, claim_scope TEXT NOT NULL, subject_ids_json TEXT NOT NULL, predicate TEXT NOT NULL, object_text TEXT NOT NULL, statement TEXT NOT NULL, event_id TEXT, modality TEXT NOT NULL, polarity TEXT NOT NULL, valid_from_sequence INTEGER NOT NULL, valid_to_sequence INTEGER, importance REAL NOT NULL, confidence REAL NOT NULL, keywords_json TEXT NOT NULL, source_tier TEXT NOT NULL, canon_status TEXT NOT NULL, verification_status TEXT NOT NULL);
        CREATE TABLE evidence(evidence_id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, source_id TEXT NOT NULL, line_start INTEGER NOT NULL, line_end INTEGER NOT NULL, quote TEXT NOT NULL, sha256 TEXT NOT NULL, verification_method TEXT NOT NULL, verification_status TEXT NOT NULL);
        CREATE TABLE knowledge_edges(knowledge_edge_id TEXT PRIMARY KEY, character_id TEXT NOT NULL, claim_id TEXT NOT NULL, acquisition_method TEXT NOT NULL, acquired_at_event TEXT, acquired_story_order INTEGER, acquired_sequence INTEGER NOT NULL, confidence REAL NOT NULL, belief_status TEXT NOT NULL);
        CREATE TABLE relations(relation_id TEXT PRIMARY KEY, source_entity_id TEXT NOT NULL, target_entity_id TEXT NOT NULL, relation_type TEXT NOT NULL, description TEXT NOT NULL, valid_from_sequence INTEGER NOT NULL, valid_to_sequence INTEGER, confidence REAL NOT NULL, source_tier TEXT NOT NULL, canon_status TEXT NOT NULL, evidence_refs_json TEXT NOT NULL);
        CREATE TABLE snapshots(snapshot_id TEXT PRIMARY KEY, character_id TEXT NOT NULL, story_cutoff TEXT NOT NULL, cutoff_sequence INTEGER NOT NULL, claim_ids_json TEXT NOT NULL, claim_count INTEGER NOT NULL);
        CREATE INDEX idx_claims_event ON claims(event_id);
        CREATE INDEX idx_claims_status ON claims(canon_status, source_tier);
        CREATE INDEX idx_knowledge_character_sequence ON knowledge_edges(character_id, acquired_sequence);
        CREATE INDEX idx_knowledge_claim ON knowledge_edges(claim_id);
        CREATE INDEX idx_evidence_claim ON evidence(claim_id);
        CREATE INDEX idx_rel_source ON relations(source_entity_id);
        CREATE VIRTUAL TABLE claims_fts USING fts5(claim_id UNINDEXED, statement, keywords, tokenize='trigram');
        """)
        connection.executemany("INSERT INTO metadata VALUES (?, ?)", [("schema_version", "2.0.0"), ("knowledge_base_version", "v2"), ("fts_tokenizer", "trigram")])
        connection.executemany("INSERT INTO cutoffs VALUES (?, ?, ?)", [(key, value["story_order"], value["sequence"]) for key, value in cutoffs.items()])
        connection.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?)", (document["document_id"], document["source_id"], document["origin"], document["source_tier"], document["sha256"], document["line_count"], document["char_count"]))
        connection.executemany("INSERT INTO scenes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [(s["scene_id"], s["document_id"], s["source_id"], s["scene_index"], s["line_start"], s["line_end"], s["sequence_start"], s["sequence_end"], s["text"]) for s in scenes])
        connection.executemany("INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?)", [(e["entity_id"], e["entity_type"], e["canonical_name"], e["identity_kind"], e["resolution_status"], e["description"]) for e in entities])
        connection.executemany("INSERT INTO aliases VALUES (?, ?, ?, ?, ?)", [(a["alias_id"], a["entity_id"], a["alias"], a["alias_type"], a["confidence"]) for a in aliases])
        connection.executemany("INSERT INTO entity_mentions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [(m["mention_id"], m["scene_id"], m["surface"], m["entity_id"], m["line"], m["resolution_status"], m["resolution_method"], m["confidence"]) for m in mentions])
        connection.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [(e["event_id"], e["event_type"], e["summary"], e["story_order"], e["narrative_sequence"], json.dumps(e["participants"], ensure_ascii=False), "[]", "[]", e["source_tier"], e["verification_status"]) for e in events])
        connection.executemany("INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [(c["claim_id"], c["claim_scope"], json.dumps(c["subject_ids"], ensure_ascii=False), c["predicate"], c["object_text"], c["statement"], c["event_id"], c["modality"], c["polarity"], c["valid_from_sequence"], None, c["importance"], c["confidence"], json.dumps(c["keywords"], ensure_ascii=False), c["source_tier"], c["canon_status"], c["verification_status"]) for c in claims])
        connection.executemany("INSERT INTO claims_fts VALUES (?, ?, ?)", [(c["claim_id"], c["statement"], " ".join(c["keywords"])) for c in claims])
        connection.executemany("INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [(e["evidence_id"], e["claim_id"], e["source_id"], e["line_start"], e["line_end"], e["quote"], e["sha256"], e["verification_method"], e["verification_status"]) for e in evidence])
        connection.executemany("INSERT INTO knowledge_edges VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [(k["knowledge_edge_id"], k["character_id"], k["claim_id"], k["acquisition_method"], k["acquired_at_event"], k["acquired_story_order"], k["acquired_sequence"], k["confidence"], k["belief_status"]) for k in knowledge_edges])
        connection.executemany("INSERT INTO relations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [(r["relation_id"], r["source_entity_id"], r["target_entity_id"], r["relation_type"], r["description"], 1, None, 1.0, "curated", "accepted", json.dumps(r["evidence_refs"], ensure_ascii=False)) for r in relations])
        connection.executemany("INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?)", [(s["snapshot_id"], s["character_id"], s["story_cutoff"], s["cutoff_sequence"], json.dumps(s["claim_ids"], ensure_ascii=False), s["claim_count"]) for s in snapshots])
        connection.commit()
    finally:
        connection.close()
    os.replace(temp, path)


def build_three_body_knowledge(source: Path, cards_dir: Path, output: Path, target_chars: int) -> dict[str, object]:
    text = _read_novel(source)
    lines = text.splitlines()
    cards = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(cards_dir.glob("*.json"))]
    if len(cards) != 5:
        raise SystemExit(f"需要先生成 5 张角色卡；当前找到 {len(cards)} 张：{cards_dir}")
    normalized = "\n".join(line.rstrip() for line in lines)
    document_id = _stable_id("doc", source.name, normalized)
    document: dict[str, object] = {"document_id": document_id, "source_id": source.name, "origin": str(source.resolve()), "source_tier": "canon", "sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(), "line_count": len(lines), "char_count": len(normalized), "text": normalized}
    scenes = _segment(normalized, source.name, document_id, target_chars)
    entities: list[dict[str, object]] = []
    aliases: list[dict[str, object]] = []
    name_lookup: dict[str, str] = {}
    for card in cards:
        identity = card["identity_core"]
        entities.append({"entity_id": card["npc_id"], "entity_type": "character", "canonical_name": identity["name"], "identity_kind": "canonical_character", "resolution_status": "curated", "description": identity["worldview_position"]})
        name_lookup[identity["name"]] = card["npc_id"]
        for alias in identity["aliases"]:
            aliases.append({"alias_id": _stable_id("alias", card["npc_id"], alias), "entity_id": card["npc_id"], "alias": alias, "alias_type": "declared_alias", "confidence": 1.0})
            name_lookup[alias] = card["npc_id"]
    mentions: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    claims: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    knowledge_edges: list[dict[str, object]] = []
    cutoffs: dict[str, dict[str, int]] = {}
    events_by_character: dict[str, list[str]] = {card["npc_id"]: [] for card in cards}
    for scene in scenes:
        participants: list[str] = []
        for surface, entity_id in sorted(name_lookup.items(), key=lambda item: len(item[0]), reverse=True):
            if surface not in scene["text"]:
                continue
            if entity_id not in participants:
                participants.append(entity_id)
            for match in re.finditer(re.escape(surface), str(scene["text"])):
                line = int(scene["line_start"]) + str(scene["text"])[:match.start()].count("\n")
                mentions.append({"mention_id": _stable_id("mention", scene["scene_id"], surface, match.start()), "scene_id": scene["scene_id"], "surface": surface, "entity_id": entity_id, "line": line, "resolution_status": "resolved", "resolution_method": "curated_name_or_alias_exact_match", "confidence": 1.0})
        if not participants:
            continue
        event_id = f"evt-{len(events) + 1:03d}"
        claim_id = f"claim-{event_id}"
        summary = _summary(str(scene["text"]))
        event = {"event_id": event_id, "event_type": "character_scene", "summary": summary, "story_order": len(events) + 1, "narrative_sequence": scene["sequence_start"], "participants": participants, "source_tier": "canon", "verification_status": "source_span_verified"}
        events.append(event)
        cutoffs[event_id] = {"story_order": int(event["story_order"]), "sequence": int(scene["sequence_end"])}
        keywords = list(dict.fromkeys([*[e["canonical_name"] for e in entities if e["entity_id"] in participants], *re.findall(r"[\u4e00-\u9fff]{2,4}", summary)]))[:24]
        claims.append({"claim_id": claim_id, "claim_scope": "story", "subject_ids": participants, "predicate": "scene_evidence", "object_text": summary, "statement": str(scene["text"]), "event_id": event_id, "modality": "asserted", "polarity": "positive", "valid_from_sequence": scene["sequence_start"], "importance": min(1.0, 0.55 + 0.08 * len(participants)), "confidence": 1.0, "keywords": keywords, "source_tier": "canon", "canon_status": "accepted", "verification_status": "source_span_verified"})
        quote = str(scene["text"])
        evidence.append({"evidence_id": f"evidence-{event_id}", "claim_id": claim_id, "source_id": source.name, "line_start": scene["line_start"], "line_end": scene["line_end"], "quote": quote, "sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(), "verification_method": "direct_source_span", "verification_status": "verified"})
        for character_id in participants:
            events_by_character[character_id].append(event_id)
            knowledge_edges.append({"knowledge_edge_id": _stable_id("knows", character_id, claim_id), "character_id": character_id, "claim_id": claim_id, "acquisition_method": "character_scene_relevance", "acquired_at_event": event_id, "acquired_story_order": event["story_order"], "acquired_sequence": scene["sequence_start"], "confidence": 0.9, "belief_status": "available"})

    relations: list[dict[str, object]] = []
    entity_ids = {e["entity_id"] for e in entities}
    for card in cards:
        for relation in card["relationships"]:
            target_id = relation["target_npc_id"] or _stable_id("entity", relation["target_name"])
            if target_id not in entity_ids:
                entities.append({"entity_id": target_id, "entity_type": "character", "canonical_name": relation["target_name"], "identity_kind": "relationship_target", "resolution_status": "curated_label", "description": relation["basis"]})
                entity_ids.add(target_id)
            relations.append({"relation_id": _stable_id("rel", card["npc_id"], target_id, relation["relationship_type"]), "source_entity_id": card["npc_id"], "target_entity_id": target_id, "relation_type": relation["relationship_type"], "description": relation["attitude"], "evidence_refs": relation["evidence_refs"]})

    snapshots: list[dict[str, object]] = []
    for card in cards:
        refs = events_by_character[card["npc_id"]]
        if not refs:
            refs = [events[0]["event_id"]]
        cutoff = refs[-1]
        card["knowledge_scope"]["world_fact_refs"] = refs
        card["knowledge_scope"]["story_cutoff"] = cutoff
        memory_refs = refs if len(refs) <= 8 else [refs[round(i * (len(refs) - 1) / 7)] for i in range(8)]
        event_lookup = {event["event_id"]: event for event in events}
        evidence_lookup = {item["claim_id"]: item for item in evidence}
        card["episodic_memory"] = []
        for event_id in memory_refs:
            event = event_lookup[event_id]
            span = evidence_lookup[f"claim-{event_id}"]
            card["episodic_memory"].append({"fact_ref": event_id, "valid_from": event_id, "valid_to": None, "source": "direct", "visibility": [card["npc_id"]], "confidence": 0.9, "evidence_ref": f"{source.name}:L{span['line_start']}-L{span['line_end']}"})
        card_path = cards_dir / f"{card['npc_id']}.json"
        card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        claim_ids = [f"claim-{event_id}" for event_id in refs]
        snapshots.append({"snapshot_id": _stable_id("snapshot", card["npc_id"], cutoff), "character_id": card["npc_id"], "story_cutoff": cutoff, "cutoff_sequence": cutoffs[cutoff]["sequence"], "claim_ids": claim_ids, "claim_count": len(claim_ids)})

    output.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output / "corpus" / "documents.jsonl", [document])
    _write_jsonl(output / "corpus" / "scenes.jsonl", scenes)
    _write_jsonl(output / "corpus" / "utterances.jsonl", [])
    _write_jsonl(output / "graph" / "entities.jsonl", entities)
    _write_jsonl(output / "graph" / "aliases.jsonl", aliases)
    _write_jsonl(output / "graph" / "entity_mentions.jsonl", mentions)
    _write_jsonl(output / "graph" / "events.jsonl", events)
    _write_jsonl(output / "graph" / "claims.jsonl", claims)
    _write_jsonl(output / "graph" / "evidence.jsonl", evidence)
    _write_jsonl(output / "graph" / "knowledge_edges.jsonl", knowledge_edges)
    _write_jsonl(output / "graph" / "relations.jsonl", relations)
    _write_jsonl(output / "quality" / "conflicts.jsonl", [])
    snapshots_dir = output / "snapshots"
    if snapshots_dir.is_dir():
        for stale_snapshot in snapshots_dir.glob("*.json"):
            stale_snapshot.unlink()
    for snapshot in snapshots:
        _write_json(snapshots_dir / f"{snapshot['character_id']}__{snapshot['story_cutoff']}.json", snapshot)
    story_records = []
    for index, event in enumerate(events):
        event_id = str(event["event_id"])
        participants = list(event["participants"])
        story_records.append({
            "event_id": event_id,
            "time_index": event["story_order"],
            "fact": event["summary"],
            "participants": participants,
            "witnesses": [],
            "informed_characters": [],
            "available_after": event_id,
            "source_type": "narration",
            "importance": claims[index]["importance"],
            "confidence": 0.9,
            "visibility": participants,
            "keywords": claims[index]["keywords"],
            "evidence_ref": f"{source.name}:L{evidence[index]['line_start']}-L{evidence[index]['line_end']}",
            "knowledge_by_character": {character_id: {"source": "direct", "available_after": event_id, "confidence": 0.9} for character_id in participants},
        })
    _write_jsonl(output.parent / "story" / "story_events.jsonl", story_records)
    sqlite_path = output / "character_knowledge_v2.sqlite3"
    _create_sqlite(sqlite_path, document, scenes, entities, aliases, mentions, events, claims, evidence, knowledge_edges, relations, snapshots, cutoffs)
    manifest: dict[str, object] = {
        "schema_version": "2.0.0", "knowledge_base_version": "v2", "title": "三体Ⅱ：黑暗森林", "build_mode": "hardcoded_five_character_source_grounded", "source_encoding": "GB18030", "source": str(source.resolve()),
        "counts": {"documents": 1, "scenes": len(scenes), "resolved_mentions": len(mentions), "entities": len(entities), "aliases": len(aliases), "events": len(events), "claims": len(claims), "evidence": len(evidence), "knowledge_edges": len(knowledge_edges), "relations": len(relations), "snapshots": len(snapshots)},
        "cutoffs": cutoffs, "runtime": {"database": "character_knowledge_v2.sqlite3", "fts_table": "claims_fts", "fts_tokenizer": "trigram", "minimum_inputs": ["character_id", "query", "story_cutoff"]},
        "validation": {"passed": bool(events and claims and len(cards) == 5), "error_count": 0, "errors": []},
    }
    _write_json(output / "manifest.json", manifest)
    _write_json(output / "quality" / "validation.json", manifest["validation"])
    return {"version": "v2", "output_dir": str(output.resolve()), "sqlite": str(sqlite_path.resolve()), **manifest["counts"], "validation_passed": manifest["validation"]["passed"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the V2 temporal epistemic character knowledge base")
    parser.add_argument("--three-body-2", action="store_true", help="构建《三体Ⅱ》固定五角色知识库")
    parser.add_argument("--mode", choices=("curated", "hybrid"), default="curated")
    parser.add_argument("--source", action="append", dest="sources")
    parser.add_argument("--output", type=Path, default=ROOT / "knowledge_base_v2")
    parser.add_argument("--scene-target-chars", type=int, default=2200)
    parser.add_argument("--scene-max-chars", type=int, default=3600)
    parser.add_argument("--model", default=os.getenv("MODEL_NAME"))
    parser.add_argument("--verifier-model", default=os.getenv("VERIFIER_MODEL_NAME"))
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"))
    parser.add_argument("--verifier-base-url", default=os.getenv("VERIFIER_BASE_URL"))
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY", ""))
    parser.add_argument("--cards", type=Path, default=THREE_BODY_ROOT / "characters")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.three_body_2:
        source = Path(args.sources[0]) if args.sources else THREE_BODY_SOURCE
        output = args.output if args.output != ROOT / "knowledge_base_v2" else THREE_BODY_ROOT / "knowledge_base_v2"
        print(json.dumps(build_three_body_knowledge(source, args.cards, output, args.scene_target_chars), ensure_ascii=False, indent=2))
        return
    from runtime import OpenAICompatibleChatModel
    from workflow_v2 import KnowledgeWorkflowV2, V2Config
    from workflow_v2.llm import V2EvidenceVerifier, V2SceneExtractor

    extractor = verifier = None
    if args.mode == "hybrid":
        if not args.model:
            raise SystemExit("hybrid 模式需要 --model 或 MODEL_NAME")
        extraction_model = OpenAICompatibleChatModel(
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
        )
        verifier_model = OpenAICompatibleChatModel(
            model=args.verifier_model or args.model,
            base_url=args.verifier_base_url or args.base_url,
            api_key=args.api_key,
        )
        extractor = V2SceneExtractor(extraction_model)
        verifier = V2EvidenceVerifier(verifier_model)
    config = V2Config(
        project_root=ROOT,
        output_dir=args.output,
        source_globs=tuple(args.sources or ("../145[3-8].txt",)),
        mode=args.mode,
        scene_target_chars=args.scene_target_chars,
        scene_max_chars=args.scene_max_chars,
    )
    result = KnowledgeWorkflowV2(config, extractor, verifier).run()
    print(
        json.dumps(
            {
                "version": "v2",
                "output_dir": str(result.output_dir),
                "sqlite": str(result.sqlite_path),
                **result.manifest["counts"],
                "validation_passed": result.manifest["validation"]["passed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
