from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .constants import DEFAULT_IMAGE_SLICE, MAX_IMAGE_SLICE, MIN_IMAGE_SLICE, MODEL_SUBDIR
from .models import HarnessModelAvailability, HarnessModelSpec, LlamaModelFiles, ModelInfo
from .registry import HarnessModelRegistry


LEGACY_FILE_RENAMES: Dict[str, List[tuple[str, str]]] = {
    "minicpm-v-4_6-instruct": [
        ("MiniCPM-V4.6-instruct-Q4_K_M.gguf", "MiniCPM-V-4_6-Q4_K_M.gguf"),
        ("minicpmv46-llm-Q4_K_M.gguf", "MiniCPM-V-4_6-Q4_K_M.gguf"),
    ],
    "minicpm5-0.9b": [
        ("MiniCPM5-0.9B-Q4_K_M.gguf", "MiniCPM5-1B-Q4_K_M.gguf"),
    ],
    "voxcpm2": [
        ("VoxCPM2-BaseLM-F16.gguf", "VoxCPM2-BaseLM-Q4_K_M.gguf"),
    ],
}


STALE_MMPROJ_NAMES: Dict[str, List[str]] = {
    "minicpm-v-4_6-instruct": [
        "mmproj-v46-model-f16.gguf",
        "mmproj-model-merger-f16.gguf",
    ],
}


class JsonPreferenceStore:
    def __init__(self, path: Path):
        self.path = path

    def read(self) -> Dict[str, object]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def write(self, data: Dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def get(self, key: str, default: object) -> object:
        return self.read().get(key, default)

    def set(self, key: str, value: object) -> None:
        data = self.read()
        data[key] = value
        self.write(data)


class LlamaModelStore:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.model_root = root_dir / MODEL_SUBDIR
        self.prefs = JsonPreferenceStore(root_dir / ".harness_state.json")

    def migrate_legacy_layout_if_needed(self) -> List[str]:
        events: List[str] = []
        if not self.model_root.exists():
            return events

        for model in HarnessModelRegistry.available_model_infos():
            target_dir = self.model_dir_for(model)
            flat_files = [self.model_root / model.gguf_file_name]
            if model.mmproj_file_name:
                flat_files.append(self.model_root / model.mmproj_file_name)

            if any(path.exists() for path in flat_files):
                target_dir.mkdir(parents=True, exist_ok=True)
                for src in flat_files:
                    dst = target_dir / src.name
                    if src.exists() and not dst.exists():
                        src.rename(dst)
                        events.append(f"migrated {src.name} -> {model.id}/{dst.name}")

            for old_name, new_name in LEGACY_FILE_RENAMES.get(model.id, []):
                src = target_dir / old_name
                dst = target_dir / new_name
                if src.exists() and not dst.exists():
                    src.rename(dst)
                    events.append(f"renamed {model.id}/{old_name} -> {new_name}")

            for name in STALE_MMPROJ_NAMES.get(model.id, []):
                for stale in [target_dir / name, target_dir / f"{name}.tmp"]:
                    if stale.exists():
                        stale.unlink()
                        events.append(f"purged stale {model.id}/{stale.name}")

        return events

    def get_selected_model(self) -> ModelInfo:
        default_id = HarnessModelRegistry.default_entry.spec.id
        model_id = str(self.prefs.get("selected_model_id", default_id))
        return HarnessModelRegistry.find_legacy_model(model_id) or HarnessModelRegistry.default_entry.legacy_model_info

    def set_selected_model(self, model_id: str) -> None:
        if HarnessModelRegistry.find_entry(model_id) is None:
            known = ", ".join(model.id for model in HarnessModelRegistry.available_model_infos())
            raise ValueError(f"Unknown model id: {model_id}. Known ids: {known}")
        self.prefs.set("selected_model_id", model_id)

    def mark_model_switched(self) -> None:
        self.prefs.set("model_switched", True)

    def consume_model_switched(self) -> bool:
        switched = bool(self.prefs.get("model_switched", False))
        if switched:
            self.prefs.set("model_switched", False)
        return switched

    def get_image_max_slice_nums(self) -> int:
        value = int(self.prefs.get("image_max_slice_nums", DEFAULT_IMAGE_SLICE))
        return max(MIN_IMAGE_SLICE, min(MAX_IMAGE_SLICE, value))

    def set_image_max_slice_nums(self, n: int) -> None:
        clamped = max(MIN_IMAGE_SLICE, min(MAX_IMAGE_SLICE, n))
        self.prefs.set("image_max_slice_nums", clamped)

    def model_dir_for(self, model: ModelInfo) -> Path:
        return self.model_root / model.id

    def get_selected_model_spec(self) -> HarnessModelSpec:
        model = self.get_selected_model()
        return HarnessModelRegistry.find_spec(model.id) or HarnessModelRegistry.default_entry.spec

    def get_selected_model_files(self) -> LlamaModelFiles:
        model = self.get_selected_model()
        spec = self.get_selected_model_spec()
        model_dir = self.model_dir_for(model)
        artifact_files: Dict[str, Path] = {"llm": model_dir / model.gguf_file_name}
        if model.mmproj_file_name:
            artifact_files["vision_projector"] = model_dir / model.mmproj_file_name
        if model.acoustic_file_name:
            artifact_files["acoustic"] = model_dir / model.acoustic_file_name
        return LlamaModelFiles(model=model, spec=spec, artifact_files=artifact_files)

    def get_selected_model_availability(self) -> HarnessModelAvailability:
        files = self.get_selected_model_files()
        gguf_missing = not files.artifact_files["llm"].exists()
        support_artifact_missing = any(
            not files.artifact_files.get(artifact.id, Path()).exists()
            for artifact in files.spec.artifacts
            if artifact.required and artifact.id != "llm"
        )
        return HarnessModelAvailability(
            model=files.model,
            gguf_missing=gguf_missing,
            support_artifact_missing=support_artifact_missing,
        )

    def is_selected_model_downloaded(self) -> bool:
        files = self.get_selected_model_files()
        return all(
            files.artifact_files.get(artifact.id, Path()).exists()
            for artifact in files.spec.artifacts
            if artifact.required
        )

    def selected_model_artifact_names(self) -> List[str]:
        return [artifact.file_name for artifact in self.get_selected_model_spec().artifacts]

    def delete_selected_model_files(self) -> bool:
        files = self.get_selected_model_files()
        deleted = False
        for path in files.artifact_files.values():
            if path.exists():
                path.unlink()
                deleted = True
        return deleted
