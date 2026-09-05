from __future__ import annotations

from typing import List, Optional, Set

from .constants import DEFAULT_IMAGE_SLICE
from .models import (
    HarnessArtifact,
    HarnessCapability,
    HarnessDownloadSource,
    HarnessDownloadSourceType,
    HarnessModelEntry,
    HarnessModelFamily,
    HarnessModelSpec,
    HarnessRuntimeHints,
    ModelInfo,
)


AVAILABLE_MODELS: List[ModelInfo] = [
    ModelInfo(
        id="minicpm-v-4",
        display_name="MiniCPM-V-4 (Q4_K_M)",
        description_res_name="model_desc_v4",
        gguf_file_name="ggml-model-Q4_K_M.gguf",
        mmproj_file_name="mmproj-model-f16.gguf",
        hf_repo="openbmb/MiniCPM-V-4-gguf",
        ms_repo="OpenBMB/MiniCPM-V-4-gguf",
    ),
    ModelInfo(
        id="minicpm-v-4_6-instruct",
        display_name="MiniCPM-V-4.6 (Q4_K_M)",
        description_res_name="model_desc_v46",
        gguf_file_name="MiniCPM-V-4_6-Q4_K_M.gguf",
        mmproj_file_name="mmproj-model-f16.gguf",
        hf_repo="openbmb/MiniCPM-V-4.6-gguf",
        ms_repo="OpenBMB/MiniCPM-V-4.6-gguf",
        gguf_md5="fd778481dd56b6036dd8f9cf7c1519cf",
        mmproj_md5="54aea6e04d752f47309a48f12795a1a3",
    ),
    ModelInfo(
        id="minicpm5-0.9b",
        display_name="MiniCPM5-1B (Q4_K_M)",
        description_res_name="model_desc_minicpm5",
        gguf_file_name="MiniCPM5-1B-Q4_K_M.gguf",
        hf_repo="openbmb/MiniCPM5-1B-GGUF",
        ms_repo="OpenBMB/MiniCPM5-1B-GGUF",
    ),
    ModelInfo(
        id="voxcpm2",
        display_name="VoxCPM2",
        description_res_name="model_desc_voxcpm2",
        gguf_file_name="VoxCPM2-BaseLM-Q4_K_M.gguf",
        acoustic_file_name="VoxCPM2-Acoustic-F16.gguf",
        hf_repo="tc-mb/MiniCPM-V-Apps-gguf",
        direct_gguf_url=(
            "https://huggingface.co/tc-mb/MiniCPM-V-Apps-gguf/resolve/main/"
            "VoxCPM2-BaseLM-Q4_K_M.gguf"
        ),
        direct_acoustic_url=(
            "https://huggingface.co/tc-mb/MiniCPM-V-Apps-gguf/resolve/main/"
            "VoxCPM2-Acoustic-F16.gguf"
        ),
        gguf_md5="d8cd571526464d225187d326caa289be",
        acoustic_md5="0f16229cfffe935102d21433f6969f8b",
    ),
    ModelInfo(
        id="llama-3.2-1b-instruct",
        display_name="Llama 3.2 1B Instruct (Q4_K_M)",
        description_res_name="model_desc_llama32_1b",
        gguf_file_name="Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        direct_gguf_url=(
            "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/"
            "resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
        ),
    ),
    ModelInfo(
        id="qwen3-0.6b",
        display_name="qwen3-0.6b",
        description_res_name="验证模型",
        gguf_file_name="Qwen3.5-0.8B-Q4_K_M.gguf",
        hf_repo="unsloth/Qwen3.5-0.8B-GGUF",
        ms_repo="unsloth/Qwen3.5-0.8B-GGUF",
    ),
]


def infer_harness_model_family(model: ModelInfo) -> HarnessModelFamily:
    if model.is_tts:
        return HarnessModelFamily.VOXCPM2
    if model.id.startswith("minicpm-v"):
        return HarnessModelFamily.MINICPM_VISION
    if model.id.startswith("minicpm5"):
        return HarnessModelFamily.MINICPM_TEXT
    if model.id.startswith("llama"):
        return HarnessModelFamily.LLAMA
    if model.id.startswith("qwen"):
        return HarnessModelFamily.QWEN
    return HarnessModelFamily.OTHER


def infer_runtime_hints(model: ModelInfo) -> HarnessRuntimeHints:
    if model.id == "minicpm-v-4_6-instruct":
        return HarnessRuntimeHints(
            default_image_max_slice_nums=DEFAULT_IMAGE_SLICE,
            context_size=8192,
        )
    if model.mmproj_file_name is not None:
        return HarnessRuntimeHints(
            default_image_max_slice_nums=DEFAULT_IMAGE_SLICE,
            context_size=4096,
        )
    return HarnessRuntimeHints(context_size=4096)


def model_to_harness_spec(model: ModelInfo) -> HarnessModelSpec:
    capabilities: Set[HarnessCapability] = {HarnessCapability.TEXT}
    if model.mmproj_file_name is not None:
        capabilities.add(HarnessCapability.VISION)
        if model.id == "minicpm-v-4_6-instruct":
            capabilities.add(HarnessCapability.VIDEO)
    if model.is_tts:
        capabilities.add(HarnessCapability.TTS)

    artifacts = [
        HarnessArtifact(
            id="llm",
            file_name=model.gguf_file_name,
            remote_path=model.gguf_remote_path,
            md5=model.gguf_md5,
        )
    ]
    if model.mmproj_file_name is not None:
        artifacts.append(
            HarnessArtifact(
                id="vision_projector",
                file_name=model.mmproj_file_name,
                remote_path=model.mmproj_remote_path,
                md5=model.mmproj_md5,
            )
        )
    if model.acoustic_file_name is not None:
        artifacts.append(
            HarnessArtifact(
                id="acoustic",
                file_name=model.acoustic_file_name,
                remote_path=model.acoustic_remote_path,
                md5=model.acoustic_md5,
            )
        )

    download_sources: List[HarnessDownloadSource] = []
    if model.hf_repo:
        download_sources.extend(_repo_sources(model, HarnessDownloadSourceType.HUGGING_FACE))
    if model.ms_repo:
        download_sources.extend(_repo_sources(model, HarnessDownloadSourceType.MODELSCOPE))
    if model.direct_gguf_url:
        download_sources.append(
            HarnessDownloadSource(
                artifact_id="llm",
                type=HarnessDownloadSourceType.DIRECT,
                url=model.direct_gguf_url,
            )
        )
    if model.direct_mmproj_url:
        download_sources.append(
            HarnessDownloadSource(
                artifact_id="vision_projector",
                type=HarnessDownloadSourceType.DIRECT,
                url=model.direct_mmproj_url,
            )
        )
    if model.direct_acoustic_url:
        download_sources.append(
            HarnessDownloadSource(
                artifact_id="acoustic",
                type=HarnessDownloadSourceType.DIRECT,
                url=model.direct_acoustic_url,
            )
        )

    return HarnessModelSpec(
        id=model.id,
        display_name=model.display_name,
        family=infer_harness_model_family(model),
        capabilities=capabilities,
        artifacts=artifacts,
        download_sources=download_sources,
        runtime_hints=infer_runtime_hints(model),
    )


def _repo_sources(
    model: ModelInfo,
    source_type: HarnessDownloadSourceType,
) -> List[HarnessDownloadSource]:
    repo = model.hf_repo if source_type == HarnessDownloadSourceType.HUGGING_FACE else model.ms_repo
    branch = model.hf_branch if source_type == HarnessDownloadSourceType.HUGGING_FACE else model.ms_branch
    sources = [
        HarnessDownloadSource(
            artifact_id="llm",
            type=source_type,
            repo=repo,
            branch=branch,
            remote_path=model.gguf_remote_path,
        )
    ]
    if model.mmproj_remote_path:
        sources.append(
            HarnessDownloadSource(
                artifact_id="vision_projector",
                type=source_type,
                repo=repo,
                branch=branch,
                remote_path=model.mmproj_remote_path,
            )
        )
    if model.acoustic_remote_path:
        sources.append(
            HarnessDownloadSource(
                artifact_id="acoustic",
                type=source_type,
                repo=repo,
                branch=branch,
                remote_path=model.acoustic_remote_path,
            )
        )
    return sources


class HarnessModelRegistry:
    entries: List[HarnessModelEntry] = [
        HarnessModelEntry(model, model_to_harness_spec(model)) for model in AVAILABLE_MODELS
    ]
    default_entry: HarnessModelEntry = entries[0]

    @classmethod
    def available_entries(cls) -> List[HarnessModelEntry]:
        return list(cls.entries)

    @classmethod
    def available_model_infos(cls) -> List[ModelInfo]:
        return [entry.legacy_model_info for entry in cls.entries]

    @classmethod
    def available_specs(cls) -> List[HarnessModelSpec]:
        return [entry.spec for entry in cls.entries]

    @classmethod
    def find_entry(cls, model_id: str) -> Optional[HarnessModelEntry]:
        return next((entry for entry in cls.entries if entry.spec.id == model_id), None)

    @classmethod
    def find_legacy_model(cls, model_id: str) -> Optional[ModelInfo]:
        entry = cls.find_entry(model_id)
        return entry.legacy_model_info if entry else None

    @classmethod
    def find_spec(cls, model_id: str) -> Optional[HarnessModelSpec]:
        entry = cls.find_entry(model_id)
        return entry.spec if entry else None
