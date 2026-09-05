from __future__ import annotations

from typing import List, Optional

from .models import DownloadCandidate, HarnessDownloadSourceType, ModelInfo
from .registry import HarnessModelRegistry
from .store import LlamaModelStore


class LlamaDownloadManager:
    def __init__(self, model_store: LlamaModelStore):
        self.model_store = model_store

    def build_download_plan(self, model: Optional[ModelInfo] = None) -> List[DownloadCandidate]:
        model = model or self.model_store.get_selected_model()
        spec = HarnessModelRegistry.find_spec(model.id)
        if spec is None:
            raise ValueError(f"Unknown model: {model.id}")
        md5_by_artifact = {artifact.id: artifact.md5 for artifact in spec.artifacts}
        file_by_artifact = {artifact.id: artifact.file_name for artifact in spec.artifacts}

        candidates: List[DownloadCandidate] = []
        for source in spec.download_sources:
            url = source.url
            label = source.type.value
            if source.type == HarnessDownloadSourceType.HUGGING_FACE:
                url = f"https://huggingface.co/{source.repo}/resolve/{source.branch}/{source.remote_path}"
                label = "HuggingFace"
            elif source.type == HarnessDownloadSourceType.MODELSCOPE:
                url = f"https://www.modelscope.cn/models/{source.repo}/resolve/{source.branch}/{source.remote_path}"
                label = "ModelScope"
            elif source.type == HarnessDownloadSourceType.DIRECT:
                label = "Direct"
            if not url:
                continue
            candidates.append(
                DownloadCandidate(
                    artifact_id=source.artifact_id,
                    file_name=file_by_artifact[source.artifact_id],
                    source_label=label,
                    url=url,
                    md5=md5_by_artifact[source.artifact_id],
                )
            )
        return candidates

    def start_foreground_download(self) -> List[DownloadCandidate]:
        return self.build_download_plan()
