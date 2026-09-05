from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterator, List, Optional

from .backends import LlamaBackendAdapter
from .backend import HarnessBackend
from .character_adapter import CharacterPromptAdapter, CharacterTurn, CharacterTurnRequest
from .character_registry import CharacterPackRegistry
from .constants import DEFAULT_PREDICT_LENGTH
from .download import LlamaDownloadManager
from .memory import JsonlMemoryStore, MemoryManager, MemoryRecord, RetrievedMemory
from .models import DownloadCandidate, GenerationOptions, HarnessModelAvailability, HarnessModelSpec, LlamaState, ModelInfo
from .registry import HarnessModelRegistry
from .session import CharacterSession, ConversationTurn, JsonSessionStore
from .store import LlamaModelStore


class HarnessFacade:
    def __init__(
        self,
        root_dir: Path,
        model_store: Optional[LlamaModelStore] = None,
        backend: Optional[HarnessBackend] = None,
        download_manager: Optional[LlamaDownloadManager] = None,
        character_registry: Optional[CharacterPackRegistry] = None,
        character_adapter: Optional[CharacterPromptAdapter] = None,
        session_store: Optional[JsonSessionStore] = None,
        memory_manager: Optional[MemoryManager] = None,
    ):
        self.root_dir = root_dir
        self.model_store = model_store or LlamaModelStore(root_dir)
        self.backend = backend or LlamaBackendAdapter()
        self.download_manager = download_manager or LlamaDownloadManager(self.model_store)
        self.character_registry = character_registry or CharacterPackRegistry.default()
        self.character_adapter = character_adapter or CharacterPromptAdapter(self.character_registry)
        self.session_store = session_store or JsonSessionStore(root_dir)
        self.memory_manager = memory_manager or MemoryManager(JsonlMemoryStore(root_dir))

    @property
    def state(self) -> LlamaState:
        return self.backend.state

    @property
    def is_vision_supported(self) -> bool:
        return self.backend.is_vision_supported

    @property
    def is_video_understanding_supported(self) -> bool:
        return self.backend.is_video_understanding_supported

    def migrate_legacy_layout_if_needed(self) -> List[str]:
        return self.model_store.migrate_legacy_layout_if_needed()

    def get_selected_model(self) -> ModelInfo:
        return self.model_store.get_selected_model()

    def get_selected_model_spec(self) -> HarnessModelSpec:
        return self.model_store.get_selected_model_spec()

    def available_models(self) -> List[ModelInfo]:
        return HarnessModelRegistry.available_model_infos()

    def available_model_specs(self) -> List[HarnessModelSpec]:
        return HarnessModelRegistry.available_specs()

    def set_selected_model(self, model_id: str) -> None:
        self.model_store.set_selected_model(model_id)

    def mark_model_switched(self) -> None:
        self.model_store.mark_model_switched()

    def consume_model_switched(self) -> bool:
        return self.model_store.consume_model_switched()

    def is_selected_model_downloaded(self) -> bool:
        return self.model_store.is_selected_model_downloaded()

    def get_image_max_slice_nums(self) -> int:
        return self.model_store.get_image_max_slice_nums()

    def set_image_max_slice_nums(self, n: int) -> None:
        self.model_store.set_image_max_slice_nums(n)
        self.backend.set_image_max_slice_nums(n)

    def get_selected_model_availability(self) -> HarnessModelAvailability:
        return self.model_store.get_selected_model_availability()

    def load_selected_model(self) -> None:
        files = self.model_store.get_selected_model_files()
        llm_file = files.artifact_files.get("llm")
        if llm_file is None:
            raise RuntimeError(f"Missing llm artifact path for {files.model.id}")
        if not llm_file.exists():
            raise FileNotFoundError(f"File not found: {llm_file}")
        mmproj_file = files.artifact_files.get("vision_projector")
        if mmproj_file is not None and not mmproj_file.exists():
            mmproj_file = None
        self.backend.load_model(llm_file, mmproj_file)

    def unload_model(self) -> None:
        self.backend.unload_model()

    def clear_context(self) -> None:
        self.backend.clear_context()

    def prefill_image(self, image_data: bytes) -> None:
        self.backend.prefill_image(image_data)

    def prefill_video_frames(
        self,
        frames: List[bytes],
        on_progress: Callable[[int, int], None] = lambda _current, _total: None,
    ) -> None:
        self.backend.prefill_video_frames(frames, on_progress)

    def send_user_prompt(
        self,
        message: str,
        predict_length: int = DEFAULT_PREDICT_LENGTH,
    ) -> Iterator[str]:
        return self.backend.send_user_prompt(message, predict_length)

    def generate_chat(
        self,
        messages: List[dict[str, str]],
        options: GenerationOptions | None = None,
    ) -> Iterator[str]:
        if self.state != LlamaState.MODEL_READY:
            self.load_selected_model()
        return self.backend.generate_chat(messages, options)

    def compile_character_turn(self, request: CharacterTurnRequest) -> CharacterTurn:
        return self.character_adapter.compile_turn(request)

    def generate_character_turn(
        self,
        request: CharacterTurnRequest,
        options: GenerationOptions | None = None,
    ) -> Iterator[str]:
        turn = self.compile_character_turn(request)
        return self.generate_chat(turn.messages, options)

    def create_character_session(
        self,
        character_id: str,
        story_cutoff: str | None = None,
        selected_model_id: str | None = None,
        conversation_summary: str = "",
    ) -> CharacterSession:
        pack = self.character_registry.resolve_pack_for_character(character_id)
        if pack is None:
            raise ValueError(f"Unknown character id: {character_id}")
        self._validate_story_cutoff(pack.story_events_path, story_cutoff)
        model_id = selected_model_id or self.get_selected_model().id
        return self.session_store.create(
            character_id=character_id,
            character_pack_id=pack.pack_id,
            story_cutoff=story_cutoff,
            selected_model_id=model_id,
            conversation_summary=conversation_summary,
        )

    def get_character_session(self, session_id: str) -> CharacterSession:
        return self.session_store.get(session_id)

    def run_session_turn(
        self,
        session_id: str,
        user_input: str,
        options: GenerationOptions | None = None,
    ) -> tuple[CharacterSession, str, MemoryRecord]:
        session = self.session_store.get(session_id)
        pack = self.character_registry.resolve_pack_for_character(session.character_id)
        if pack is None:
            raise ValueError(f"Unknown character id in session {session_id}: {session.character_id}")
        self._validate_story_cutoff(pack.story_events_path, session.story_cutoff)
        self.set_selected_model(session.selected_model_id)
        request = CharacterTurnRequest(
            character_id=session.character_id,
            user_input=user_input,
            story_cutoff=session.story_cutoff,
            conversation_summary=session.conversation_summary,
            dynamic_state=session.dynamic_state,
        )
        assistant_output = "".join(self.generate_character_turn(request, options)).strip()
        updated = self.session_store.append_turns(
            session_id,
            [
                ConversationTurn(role="user", content=user_input),
                ConversationTurn(role="assistant", content=assistant_output),
            ],
        )
        memory = self.memory_manager.observe_turn(updated, user_input, assistant_output)
        return updated, assistant_output, memory

    def add_memory(
        self,
        text: str,
        kind: str = "session_memory",
        character_id: str | None = None,
        session_id: str | None = None,
        importance: float = 0.5,
        confidence: float = 1.0,
    ) -> MemoryRecord:
        scope = "session" if session_id else "character" if character_id else "global"
        return self.memory_manager.add_memory(
            text=text,
            kind=kind,  # type: ignore[arg-type]
            scope=scope,
            character_id=character_id,
            session_id=session_id,
            importance=importance,
            confidence=confidence,
        )

    def list_memories(
        self,
        session_id: str | None = None,
        character_id: str | None = None,
        kind: str | None = None,
    ) -> List[MemoryRecord]:
        return self.memory_manager.list_records(session_id=session_id, character_id=character_id, kind=kind)

    def search_memories(
        self,
        query: str,
        session_id: str | None = None,
        character_id: str | None = None,
        limit: int = 5,
    ) -> List[RetrievedMemory]:
        return self.memory_manager.search(
            query=query,
            session_id=session_id,
            character_id=character_id,
            limit=limit,
        )

    def cancel_generation(self) -> None:
        self.backend.cancel_generation()

    def reset_to_initialized(self) -> None:
        self.backend.reset_to_initialized()

    def destroy(self) -> None:
        self.backend.destroy()

    def start_download_service(self) -> List[DownloadCandidate]:
        return self.download_manager.start_foreground_download()

    def selected_model_artifact_names(self) -> List[str]:
        return self.model_store.selected_model_artifact_names()

    def delete_selected_model_files(self) -> bool:
        return self.model_store.delete_selected_model_files()

    @staticmethod
    def _validate_story_cutoff(story_events_path: Path, story_cutoff: str | None) -> None:
        if story_cutoff is None or story_cutoff == "":
            return
        event_ids: set[str] = set()
        with story_events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    event_ids.add(str(json.loads(line)["event_id"]))
        if story_cutoff not in event_ids:
            known = ", ".join(sorted(event_ids))
            raise ValueError(
                f"Unknown story cutoff: {story_cutoff}. Use an event id such as evt-018. Known ids: {known}"
            )
