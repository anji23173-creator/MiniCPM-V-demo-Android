from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterator, List, Optional

from .constants import DEFAULT_IMAGE_SLICE, DEFAULT_PREDICT_LENGTH, MAX_IMAGE_SLICE, MIN_IMAGE_SLICE
from .models import GenerationOptions, LlamaState


class HarnessBackend:
    def __init__(self):
        self.state = LlamaState.INITIALIZED
        self.loaded_model_path: Optional[Path] = None
        self.loaded_mmproj_path: Optional[Path] = None
        self.image_max_slice_nums = DEFAULT_IMAGE_SLICE
        self._cancelled = False

    @property
    def is_vision_supported(self) -> bool:
        return self.loaded_mmproj_path is not None and self.loaded_mmproj_path.exists()

    @property
    def is_video_understanding_supported(self) -> bool:
        return self.is_vision_supported

    def load_model(self, model_path: Path, mmproj_path: Optional[Path] = None) -> None:
        self.state = LlamaState.LOADING_MODEL
        if not model_path.exists():
            self.state = LlamaState.ERROR
            raise FileNotFoundError(f"File not found: {model_path}")
        if mmproj_path is not None and not mmproj_path.exists():
            self.state = LlamaState.ERROR
            raise FileNotFoundError(f"File not found: {mmproj_path}")
        self.loaded_model_path = model_path
        self.loaded_mmproj_path = mmproj_path
        self.state = LlamaState.MODEL_READY

    def unload_model(self) -> None:
        self.state = LlamaState.UNLOADING_MODEL
        self.loaded_model_path = None
        self.loaded_mmproj_path = None
        self.state = LlamaState.INITIALIZED

    def prefill_image(self, image_data: bytes) -> None:
        if not self.is_vision_supported:
            raise RuntimeError("Vision projector is not loaded.")
        self.state = LlamaState.PREFILLING_IMAGE
        if not image_data:
            raise ValueError("image_data is empty")
        self.state = LlamaState.MODEL_READY

    def prefill_video_frames(
        self,
        frames: List[bytes],
        on_progress: Callable[[int, int], None] = lambda _current, _total: None,
    ) -> None:
        if not self.is_video_understanding_supported:
            raise RuntimeError("Video understanding is not supported by the loaded backend.")
        total = len(frames)
        for index, frame in enumerate(frames, start=1):
            if not frame:
                raise ValueError(f"frame {index} is empty")
            on_progress(index, total)

    def clear_context(self) -> None:
        self.state = LlamaState.MODEL_READY if self.loaded_model_path else LlamaState.INITIALIZED

    def set_image_max_slice_nums(self, n: int) -> None:
        self.image_max_slice_nums = max(MIN_IMAGE_SLICE, min(MAX_IMAGE_SLICE, n))

    def send_user_prompt(self, message: str, predict_length: int = DEFAULT_PREDICT_LENGTH) -> Iterator[str]:
        yield from self.generate_chat(
            [{"role": "user", "content": message}],
            GenerationOptions(max_tokens=predict_length),
        )

    def generate_chat(
        self,
        messages: List[dict[str, str]],
        options: GenerationOptions | None = None,
    ) -> Iterator[str]:
        if self.state != LlamaState.MODEL_READY:
            raise RuntimeError(f"Model is not ready. Current state: {self.state.value}")
        self._cancelled = False
        self.state = LlamaState.GENERATING
        options = options or GenerationOptions()
        user_message = next(
            (message.get("content", "") for message in reversed(messages) if message.get("role") == "user"),
            "",
        )
        system_message = next(
            (message.get("content", "") for message in messages if message.get("role") == "system"),
            "",
        )
        mode = "character-chat" if system_message else "plain-chat"
        response = (
            f"[mock backend] model={self.loaded_model_path.name if self.loaded_model_path else 'none'} "
            f"mode={mode} max_tokens={options.max_tokens}: {user_message}"
        )
        for token in response.split(" "):
            if self._cancelled:
                break
            yield token + " "
        self.state = LlamaState.MODEL_READY

    def cancel_generation(self) -> None:
        self._cancelled = True

    def reset_to_initialized(self) -> None:
        self.loaded_model_path = None
        self.loaded_mmproj_path = None
        self.state = LlamaState.INITIALIZED

    def destroy(self) -> None:
        self.reset_to_initialized()
        self.state = LlamaState.UNINITIALIZED
