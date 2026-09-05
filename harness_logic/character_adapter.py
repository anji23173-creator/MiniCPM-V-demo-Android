from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .character_registry import CharacterPackRegistry, CharacterRegistryError
from .constants import DEFAULT_CHARACTER_EVIDENCE_ROOT


@dataclass(frozen=True)
class CharacterTurnRequest:
    character_id: str
    user_input: str
    story_cutoff: str | None = None
    max_chars: int = 4500
    dynamic_state: dict[str, Any] | None = None
    conversation_summary: str = ""
    top_k: int = 8


@dataclass(frozen=True)
class CharacterTurn:
    character_id: str
    messages: list[dict[str, str]]
    debug: dict[str, Any] = field(default_factory=dict)


class CharacterPromptAdapter:
    def __init__(
        self,
        registry: CharacterPackRegistry | None = None,
        evidence_root: Path = DEFAULT_CHARACTER_EVIDENCE_ROOT,
    ):
        self.registry = registry or CharacterPackRegistry.default()
        self.evidence_root = evidence_root.expanduser().resolve()
        self._compiler_cache: dict[Path, Any] = {}

    def compile_turn(self, request: CharacterTurnRequest) -> CharacterTurn:
        if not request.character_id.strip():
            raise ValueError("character_id must not be empty")
        if not request.user_input.strip():
            raise ValueError("user_input must not be empty")

        pack = self.registry.resolve_pack_for_character(request.character_id)
        if pack is None:
            raise CharacterRegistryError(f"Unknown character id: {request.character_id}")

        compiler = self._compiler_for_pack(pack.root)
        from .character_system.runtime import RuntimeContext

        compiled = compiler.build_npc_prompt(
            npc_id=request.character_id,
            user_input=request.user_input,
            runtime_context=RuntimeContext(
                story_cutoff=request.story_cutoff,
                dynamic_state=request.dynamic_state,
                max_chars=request.max_chars,
                top_k=request.top_k,
                conversation_summary=request.conversation_summary,
            ),
        )
        return CharacterTurn(
            character_id=request.character_id,
            messages=compiled.messages,
            debug=compiled.debug,
        )

    def _compiler_for_pack(self, pack_root: Path) -> Any:
        root = pack_root.expanduser().resolve()
        compiler = self._compiler_cache.get(root)
        if compiler is not None:
            return compiler

        from .character_system.runtime import PromptCompiler

        compiler = PromptCompiler(root, validate_on_load=False)
        compiler.novel_dir = self.evidence_root
        self._compiler_cache[root] = compiler
        return compiler
