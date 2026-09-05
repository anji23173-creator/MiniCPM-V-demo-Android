from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

from .constants import DEFAULT_IMAGE_SLICE, DEFAULT_PREDICT_LENGTH


class LlamaState(str, Enum):
    UNINITIALIZED = "Uninitialized"
    INITIALIZING = "Initializing"
    INITIALIZED = "Initialized"
    LOADING_MODEL = "LoadingModel"
    MODEL_READY = "ModelReady"
    PROCESSING_SYSTEM_PROMPT = "ProcessingSystemPrompt"
    PREFILLING_IMAGE = "PrefillingImage"
    PROCESSING_USER_PROMPT = "ProcessingUserPrompt"
    GENERATING = "Generating"
    UNLOADING_MODEL = "UnloadingModel"
    ERROR = "Error"


class HarnessCapability(str, Enum):
    TEXT = "TEXT"
    VISION = "VISION"
    VIDEO = "VIDEO"
    TTS = "TTS"


class HarnessModelFamily(str, Enum):
    MINICPM_VISION = "MINICPM_VISION"
    MINICPM_TEXT = "MINICPM_TEXT"
    VOXCPM2 = "VOXCPM2"
    LLAMA = "LLAMA"
    QWEN = "QWEN"
    OTHER = "OTHER"


class HarnessDownloadSourceType(str, Enum):
    HUGGING_FACE = "HUGGING_FACE"
    MODELSCOPE = "MODELSCOPE"
    DIRECT = "DIRECT"


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str
    description_res_name: str
    gguf_file_name: str
    mmproj_file_name: Optional[str] = None
    acoustic_file_name: Optional[str] = None
    hf_repo: Optional[str] = None
    ms_repo: Optional[str] = None
    hf_branch: str = "main"
    ms_branch: str = "master"
    gguf_remote_name: Optional[str] = None
    mmproj_remote_name: Optional[str] = None
    acoustic_remote_name: Optional[str] = None
    direct_gguf_url: Optional[str] = None
    direct_mmproj_url: Optional[str] = None
    direct_acoustic_url: Optional[str] = None
    gguf_md5: Optional[str] = None
    mmproj_md5: Optional[str] = None
    acoustic_md5: Optional[str] = None

    @property
    def is_text_only(self) -> bool:
        return self.mmproj_file_name is None and self.acoustic_file_name is None

    @property
    def is_tts(self) -> bool:
        return self.acoustic_file_name is not None

    @property
    def gguf_remote_path(self) -> str:
        return self.gguf_remote_name or self.gguf_file_name

    @property
    def mmproj_remote_path(self) -> Optional[str]:
        if self.mmproj_file_name is None:
            return None
        return self.mmproj_remote_name or self.mmproj_file_name

    @property
    def acoustic_remote_path(self) -> Optional[str]:
        if self.acoustic_file_name is None:
            return None
        return self.acoustic_remote_name or self.acoustic_file_name

    @property
    def has_direct_urls(self) -> bool:
        if self.is_text_only:
            return bool(self.direct_gguf_url)
        if self.is_tts:
            return bool(self.direct_gguf_url and self.direct_acoustic_url)
        return bool(self.direct_gguf_url and self.direct_mmproj_url)

    @property
    def has_hf_ms_sources(self) -> bool:
        return bool(self.hf_repo and self.ms_repo)


@dataclass(frozen=True)
class HarnessArtifact:
    id: str
    file_name: str
    required: bool = True
    remote_path: Optional[str] = None
    md5: Optional[str] = None


@dataclass(frozen=True)
class HarnessDownloadSource:
    artifact_id: str
    type: HarnessDownloadSourceType
    repo: Optional[str] = None
    branch: Optional[str] = None
    remote_path: Optional[str] = None
    url: Optional[str] = None


@dataclass(frozen=True)
class HarnessRuntimeHints:
    default_predict_length: int = DEFAULT_PREDICT_LENGTH
    recommended_threads: int = 4
    default_image_max_slice_nums: Optional[int] = None
    context_size: Optional[int] = None
    supports_system_prompt: bool = True


@dataclass(frozen=True)
class HarnessModelSpec:
    id: str
    display_name: str
    family: HarnessModelFamily
    capabilities: Set[HarnessCapability]
    artifacts: List[HarnessArtifact]
    download_sources: List[HarnessDownloadSource]
    runtime_hints: HarnessRuntimeHints


@dataclass(frozen=True)
class HarnessModelEntry:
    legacy_model_info: ModelInfo
    spec: HarnessModelSpec


@dataclass(frozen=True)
class HarnessModelAvailability:
    model: ModelInfo
    gguf_missing: bool
    support_artifact_missing: bool

    @property
    def complete(self) -> bool:
        return not self.gguf_missing and not self.support_artifact_missing


@dataclass(frozen=True)
class LlamaModelFiles:
    model: ModelInfo
    spec: HarnessModelSpec
    artifact_files: Dict[str, Path]


@dataclass(frozen=True)
class DownloadCandidate:
    artifact_id: str
    file_name: str
    source_label: str
    url: str
    md5: Optional[str] = None


@dataclass(frozen=True)
class GenerationOptions:
    max_tokens: int = DEFAULT_PREDICT_LENGTH
    temperature: float = 0.7
    top_p: float = 0.9
    stop: List[str] = field(default_factory=list)
    stream: bool = True
    seed: Optional[int] = None


def default_vision_runtime_hints(context_size: int = 4096) -> HarnessRuntimeHints:
    return HarnessRuntimeHints(
        default_image_max_slice_nums=DEFAULT_IMAGE_SLICE,
        context_size=context_size,
    )
