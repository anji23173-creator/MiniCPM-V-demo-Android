from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional

from .character_adapter import CharacterTurnRequest
from .character_registry import CharacterPackRegistry
from .constants import (
    DEFAULT_CHARACTER_EVIDENCE_ROOT,
    DEFAULT_CHARACTER_SYSTEM_ROOT,
    DEFAULT_HARNESS_ROOT,
    DEFAULT_PREDICT_LENGTH,
    HARNESS_LOGIC_DIR,
)
from .facade import HarnessFacade
from .models import DownloadCandidate, GenerationOptions, LlamaState
from .registry import HarnessModelRegistry
from .utils import compute_md5, print_json


def command_list(_facade: HarnessFacade, _args: argparse.Namespace) -> None:
    for spec in HarnessModelRegistry.available_specs():
        capabilities = ",".join(sorted(cap.value for cap in spec.capabilities))
        artifacts = ", ".join(artifact.file_name for artifact in spec.artifacts)
        print(f"{spec.id}\t{spec.display_name}\t{spec.family.value}\t{capabilities}\t{artifacts}")


def command_spec(_facade: HarnessFacade, args: argparse.Namespace) -> None:
    spec = HarnessModelRegistry.find_spec(args.model_id)
    if spec is None:
        raise SystemExit(f"Unknown model id: {args.model_id}")
    print_json(spec)


def command_select(facade: HarnessFacade, args: argparse.Namespace) -> None:
    previous = facade.get_selected_model().id
    facade.set_selected_model(args.model_id)
    if previous != args.model_id:
        facade.mark_model_switched()
    print(f"selected_model_id={facade.get_selected_model().id}")


def command_status(facade: HarnessFacade, _args: argparse.Namespace) -> None:
    files = facade.model_store.get_selected_model_files()
    availability = facade.get_selected_model_availability()
    print(f"selected={files.model.id} ({files.model.display_name})")
    print(f"state={facade.state.value}")
    print(f"image_max_slice_nums={facade.get_image_max_slice_nums()}")
    print(f"downloaded={availability.complete}")
    for artifact in files.spec.artifacts:
        path = files.artifact_files[artifact.id]
        status = "present" if path.exists() else "missing"
        md5_info = ""
        if path.exists() and artifact.md5:
            actual = compute_md5(path)
            md5_info = f" md5={'ok' if actual.lower() == artifact.md5.lower() else actual}"
        print(f"{artifact.id}: {status} {_display_path(path)}{md5_info}")


def command_download_plan(facade: HarnessFacade, _args: argparse.Namespace) -> None:
    plan = facade.start_download_service()
    if not plan:
        print("No download sources configured.")
        return
    grouped: Dict[str, List[DownloadCandidate]] = {}
    for candidate in plan:
        grouped.setdefault(candidate.file_name, []).append(candidate)
    for file_name, candidates in grouped.items():
        labels = "+".join(candidate.source_label for candidate in candidates)
        print(f"{file_name}: race {labels}")
        for candidate in candidates:
            md5 = f" md5={candidate.md5}" if candidate.md5 else ""
            print(f"  - {candidate.source_label}: {candidate.url}{md5}")


def command_migrate(facade: HarnessFacade, _args: argparse.Namespace) -> None:
    events = facade.migrate_legacy_layout_if_needed()
    if not events:
        print("No legacy files changed.")
        return
    for event in events:
        print(event)


def command_touch_demo_files(facade: HarnessFacade, _args: argparse.Namespace) -> None:
    files = facade.model_store.get_selected_model_files()
    for artifact in files.spec.artifacts:
        path = files.artifact_files[artifact.id]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(f"demo artifact for {files.model.id}/{artifact.id}\n".encode("utf-8"))
            print(f"created {_display_path(path)}")
        else:
            print(f"exists {_display_path(path)}")


def command_load(facade: HarnessFacade, _args: argparse.Namespace) -> None:
    facade.load_selected_model()
    print(f"state={facade.state.value}")
    print(f"vision_supported={facade.is_vision_supported}")


def command_prompt(facade: HarnessFacade, args: argparse.Namespace) -> None:
    if facade.state != LlamaState.MODEL_READY:
        facade.load_selected_model()
    for chunk in facade.send_user_prompt(args.message, args.predict_length):
        print(chunk, end="")
    print()


def command_delete(facade: HarnessFacade, _args: argparse.Namespace) -> None:
    deleted = facade.delete_selected_model_files()
    print(f"deleted={deleted}")


def command_character_list(_facade: HarnessFacade, _args: argparse.Namespace) -> None:
    registry = CharacterPackRegistry.default()
    for index, character in enumerate(registry.available_characters(), 1):
        aliases = ",".join(character.aliases)
        print(
            f"{index}\t{character.character_id}\t{character.display_name}\t"
            f"{character.pack_id}\t{character.story_cutoff or ''}\t{aliases}"
        )


def command_character_pack_validate(_facade: HarnessFacade, args: argparse.Namespace) -> None:
    path = _resolve_local_path(args.path)
    evidence_root = _resolve_local_path(args.evidence_root) if args.evidence_root is not None else None
    result = CharacterPackRegistry.validate_pack_root(path, evidence_root)
    display_path = _display_path(result.path)
    if result.ok:
        print(
            f"OK: pack_id={result.pack_id} characters={result.character_count} "
            f"events={result.event_count} path={display_path}"
        )
        return
    print(f"FAILED: path={display_path}")
    for error in result.errors:
        print(f"- {error}")
    raise SystemExit(1)


def _character_request_from_args(args: argparse.Namespace) -> CharacterTurnRequest:
    return CharacterTurnRequest(
        character_id=args.character,
        user_input=args.input,
        story_cutoff=args.cutoff,
        max_chars=args.max_chars,
        conversation_summary=args.conversation_summary or "",
        top_k=args.top_k,
    )


def command_character_prompt(facade: HarnessFacade, args: argparse.Namespace) -> None:
    turn = facade.compile_character_turn(_character_request_from_args(args))
    payload = {"messages": turn.messages}
    if args.debug:
        payload["debug"] = turn.debug
    print_json(payload)


def command_character_chat(facade: HarnessFacade, args: argparse.Namespace) -> None:
    if args.backend != "mock":
        raise SystemExit(f"Unsupported backend for current phase: {args.backend}")
    if args.model:
        previous = facade.get_selected_model().id
        facade.set_selected_model(args.model)
        if previous != args.model:
            facade.mark_model_switched()
    if args.touch_demo_files:
        command_touch_demo_files(facade, args)
    options = GenerationOptions(max_tokens=args.max_tokens)
    for chunk in facade.generate_character_turn(_character_request_from_args(args), options):
        print(chunk, end="")
    print()


def command_session_new(facade: HarnessFacade, args: argparse.Namespace) -> None:
    if args.model:
        facade.set_selected_model(args.model)
    session = facade.create_character_session(
        character_id=args.character,
        story_cutoff=args.cutoff,
        selected_model_id=args.model,
        conversation_summary=args.conversation_summary or "",
    )
    print_json(session)


def command_session_show(facade: HarnessFacade, args: argparse.Namespace) -> None:
    _require_non_empty(args.session, "session")
    print_json(facade.get_character_session(args.session))


def command_session_chat(facade: HarnessFacade, args: argparse.Namespace) -> None:
    _require_non_empty(args.session, "session")
    if args.backend != "mock":
        raise SystemExit(f"Unsupported backend for current phase: {args.backend}")
    if args.touch_demo_files:
        session = facade.get_character_session(args.session)
        facade.set_selected_model(session.selected_model_id)
        command_touch_demo_files(facade, args)
    _session, assistant_output, memory = facade.run_session_turn(
        session_id=args.session,
        user_input=args.input,
        options=GenerationOptions(max_tokens=args.max_tokens),
    )
    if args.json:
        print_json({"assistant": assistant_output, "memory": memory})
        return
    print(assistant_output)


def command_memory_list(facade: HarnessFacade, args: argparse.Namespace) -> None:
    print_json(
        facade.list_memories(
            session_id=args.session,
            character_id=args.character,
            kind=args.kind,
        )
    )


def command_memory_search(facade: HarnessFacade, args: argparse.Namespace) -> None:
    _require_non_empty(args.query, "query")
    print_json(
        facade.search_memories(
            query=args.query,
            session_id=args.session,
            character_id=args.character,
            limit=args.limit,
        )
    )


def command_memory_add(facade: HarnessFacade, args: argparse.Namespace) -> None:
    _require_non_empty(args.text, "text")
    print_json(
        facade.add_memory(
            text=args.text,
            kind=args.kind,
            character_id=args.character,
            session_id=args.session,
            importance=args.importance,
            confidence=args.confidence,
        )
    )


def command_memory_delete(facade: HarnessFacade, args: argparse.Namespace) -> None:
    _require_non_empty(args.memory_id, "memory-id")
    print(f"deleted={facade.memory_manager.delete(args.memory_id)}")


def _require_non_empty(value: str, name: str) -> None:
    if not value or not value.strip():
        raise SystemExit(f"{name} must not be empty")


def _resolve_local_path(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.exists() or expanded.is_absolute():
        return expanded
    package_relative = HARNESS_LOGIC_DIR / expanded
    if package_relative.exists():
        return package_relative
    return expanded


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        try:
            return str(path.resolve().relative_to(HARNESS_LOGIC_DIR.resolve()))
        except ValueError:
            return str(path)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Runnable Python extraction of MiniCPM-V-demo-Android harness logic."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_HARNESS_ROOT,
        help="Root used for .harness_state.json and models/. Defaults to harness_logic/data.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List registered harness models.").set_defaults(func=command_list)

    spec = subparsers.add_parser("spec", help="Print one HarnessModelSpec as JSON.")
    spec.add_argument("model_id")
    spec.set_defaults(func=command_spec)

    select = subparsers.add_parser("select", help="Persist selected model id.")
    select.add_argument("model_id")
    select.set_defaults(func=command_select)

    subparsers.add_parser("status", help="Show selected model, artifact paths, and local availability.").set_defaults(
        func=command_status
    )
    subparsers.add_parser("download-plan", help="Show the selected model's download race candidates.").set_defaults(
        func=command_download_plan
    )
    subparsers.add_parser("migrate", help="Run legacy flat models/ migration and stale file cleanup.").set_defaults(
        func=command_migrate
    )
    subparsers.add_parser(
        "touch-demo-files",
        help="Create tiny placeholder files for the selected model so mock load/prompt can run.",
    ).set_defaults(func=command_touch_demo_files)
    subparsers.add_parser("load", help="Load selected model into the mock backend.").set_defaults(func=command_load)

    prompt = subparsers.add_parser("prompt", help="Run a prompt through the mock backend.")
    prompt.add_argument("message")
    prompt.add_argument("--predict-length", type=int, default=DEFAULT_PREDICT_LENGTH)
    prompt.set_defaults(func=command_prompt)

    subparsers.add_parser("delete", help="Delete selected model artifact files.").set_defaults(func=command_delete)

    subparsers.add_parser("character-list", help="List registered characters.").set_defaults(
        func=command_character_list
    )

    character_pack = subparsers.add_parser("character-pack", help="Manage character packs.")
    character_pack_subparsers = character_pack.add_subparsers(dest="character_pack_command", required=True)
    validate = character_pack_subparsers.add_parser("validate", help="Validate a character pack directory.")
    validate.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_CHARACTER_SYSTEM_ROOT,
        help="Character pack root to validate. Defaults to the built-in character_system.",
    )
    validate.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_CHARACTER_EVIDENCE_ROOT,
        help="Directory containing evidence text files referenced by the character pack.",
    )
    validate.set_defaults(func=command_character_pack_validate)

    character_prompt = subparsers.add_parser("character-prompt", help="Compile character messages without generation.")
    _add_character_turn_args(character_prompt)
    character_prompt.add_argument("--debug", action="store_true", help="Include local-only compiler debug output.")
    character_prompt.set_defaults(func=command_character_prompt)

    character_chat = subparsers.add_parser("character-chat", help="Compile a character turn and run it through backend.")
    _add_character_turn_args(character_chat)
    character_chat.add_argument("--backend", default="mock", choices=["mock"])
    character_chat.add_argument("--model", help="Select model before running the character turn.")
    character_chat.add_argument("--max-tokens", type=int, default=DEFAULT_PREDICT_LENGTH)
    character_chat.add_argument(
        "--touch-demo-files",
        action="store_true",
        help="Create tiny placeholder model files before loading the mock backend.",
    )
    character_chat.set_defaults(func=command_character_chat)

    session_new = subparsers.add_parser("session-new", help="Create a character chat session.")
    session_new.add_argument("--character", required=True)
    session_new.add_argument("--cutoff")
    session_new.add_argument("--model")
    session_new.add_argument("--conversation-summary", default="")
    session_new.set_defaults(func=command_session_new)

    session_show = subparsers.add_parser("session-show", help="Show one character session as JSON.")
    session_show.add_argument("--session", required=True)
    session_show.set_defaults(func=command_session_show)

    session_chat = subparsers.add_parser("session-chat", help="Run one mock character turn inside a session.")
    session_chat.add_argument("--session", required=True)
    session_chat.add_argument("--input", required=True)
    session_chat.add_argument("--backend", default="mock", choices=["mock"])
    session_chat.add_argument("--max-tokens", type=int, default=DEFAULT_PREDICT_LENGTH)
    session_chat.add_argument("--touch-demo-files", action="store_true")
    session_chat.add_argument("--json", action="store_true", help="Print assistant output plus written memory as JSON.")
    session_chat.set_defaults(func=command_session_chat)

    memory_list = subparsers.add_parser("memory-list", help="List stored memories.")
    _add_memory_filter_args(memory_list)
    memory_list.set_defaults(func=command_memory_list)

    memory_search = subparsers.add_parser("memory-search", help="Search stored memories.")
    _add_memory_filter_args(memory_search)
    memory_search.add_argument("--query", required=True)
    memory_search.add_argument("--limit", type=int, default=5)
    memory_search.set_defaults(func=command_memory_search)

    memory_add = subparsers.add_parser("memory-add", help="Add an explicit memory record.")
    memory_add.add_argument("--text", required=True)
    memory_add.add_argument("--kind", default="character_memory")
    memory_add.add_argument("--character")
    memory_add.add_argument("--session")
    memory_add.add_argument("--importance", type=float, default=0.5)
    memory_add.add_argument("--confidence", type=float, default=1.0)
    memory_add.set_defaults(func=command_memory_add)

    memory_delete = subparsers.add_parser("memory-delete", help="Delete a memory record by id.")
    memory_delete.add_argument("--memory-id", required=True)
    memory_delete.set_defaults(func=command_memory_delete)

    return parser


def _add_character_turn_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--character", required=True, help="Character id, for example lu_jiangxian.")
    parser.add_argument("--input", required=True, help="User input for this character turn.")
    parser.add_argument("--cutoff", help="Story cutoff event id, for example evt-018.")
    parser.add_argument("--max-chars", type=int, default=4500, help="Max compiled system prompt chars.")
    parser.add_argument("--conversation-summary", default="", help="Optional conversation summary.")
    parser.add_argument("--top-k", type=int, default=8, help="Maximum retrieved story facts before prompt budgeting.")


def _add_memory_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--session")
    parser.add_argument("--character")
    parser.add_argument("--kind")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    facade = HarnessFacade(root)
    try:
        args.func(facade, args)
    except (ValueError, KeyError, FileNotFoundError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0
