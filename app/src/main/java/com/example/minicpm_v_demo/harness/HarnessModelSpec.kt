package com.example.minicpm_v_demo.harness

import com.example.minicpm_v_demo.LlamaEngine
import com.example.minicpm_v_demo.ModelInfo

enum class HarnessCapability {
    TEXT,
    VISION,
    VIDEO,
    TTS
}

enum class HarnessModelFamily {
    MINICPM_VISION,
    MINICPM_TEXT,
    VOXCPM2,
    LLAMA,
    QWEN,
    OTHER
}

enum class HarnessDownloadSourceType {
    HUGGING_FACE,
    MODELSCOPE,
    DIRECT
}

data class HarnessArtifact(
    val id: String,
    val fileName: String,
    val required: Boolean = true,
    val remotePath: String? = null,
    val md5: String? = null
)

data class HarnessDownloadSource(
    val artifactId: String,
    val type: HarnessDownloadSourceType,
    val repo: String? = null,
    val branch: String? = null,
    val remotePath: String? = null,
    val url: String? = null
)

data class HarnessRuntimeHints(
    val defaultPredictLength: Int = LlamaEngine.DEFAULT_PREDICT_LENGTH,
    val recommendedThreads: Int = 4,
    val defaultImageMaxSliceNums: Int? = null,
    val contextSize: Int? = null,
    val supportsSystemPrompt: Boolean = true
)

data class HarnessModelSpec(
    val id: String,
    val displayName: String,
    val family: HarnessModelFamily,
    val capabilities: Set<HarnessCapability>,
    val artifacts: List<HarnessArtifact>,
    val downloadSources: List<HarnessDownloadSource>,
    val runtimeHints: HarnessRuntimeHints
)

fun ModelInfo.toHarnessSpec(): HarnessModelSpec {
    val capabilities = linkedSetOf(HarnessCapability.TEXT)
    if (mmprojFileName != null) {
        capabilities += HarnessCapability.VISION
        if (id == "minicpm-v-4_6-instruct") {
            capabilities += HarnessCapability.VIDEO
        }
    }
    if (isTts) {
        capabilities += HarnessCapability.TTS
    }

    val artifacts = buildList {
        add(
            HarnessArtifact(
                id = "llm",
                fileName = ggufFileName,
                remotePath = ggufRemotePath,
                md5 = ggufMd5
            )
        )
        mmprojFileName?.let {
            add(
                HarnessArtifact(
                    id = "vision_projector",
                    fileName = it,
                    remotePath = mmprojRemotePath,
                    md5 = mmprojMd5
                )
            )
        }
        acousticFileName?.let {
            add(
                HarnessArtifact(
                    id = "acoustic",
                    fileName = it,
                    remotePath = acousticRemotePath,
                    md5 = acousticMd5
                )
            )
        }
    }

    val downloadSources = buildList {
        if (!hfRepo.isNullOrBlank()) {
            add(
                HarnessDownloadSource(
                    artifactId = "llm",
                    type = HarnessDownloadSourceType.HUGGING_FACE,
                    repo = hfRepo,
                    branch = hfBranch,
                    remotePath = ggufRemotePath
                )
            )
            mmprojRemotePath?.let {
                add(
                    HarnessDownloadSource(
                        artifactId = "vision_projector",
                        type = HarnessDownloadSourceType.HUGGING_FACE,
                        repo = hfRepo,
                        branch = hfBranch,
                        remotePath = it
                    )
                )
            }
            acousticRemotePath?.let {
                add(
                    HarnessDownloadSource(
                        artifactId = "acoustic",
                        type = HarnessDownloadSourceType.HUGGING_FACE,
                        repo = hfRepo,
                        branch = hfBranch,
                        remotePath = it
                    )
                )
            }
        }
        if (!msRepo.isNullOrBlank()) {
            add(
                HarnessDownloadSource(
                    artifactId = "llm",
                    type = HarnessDownloadSourceType.MODELSCOPE,
                    repo = msRepo,
                    branch = msBranch,
                    remotePath = ggufRemotePath
                )
            )
            mmprojRemotePath?.let {
                add(
                    HarnessDownloadSource(
                        artifactId = "vision_projector",
                        type = HarnessDownloadSourceType.MODELSCOPE,
                        repo = msRepo,
                        branch = msBranch,
                        remotePath = it
                    )
                )
            }
            acousticRemotePath?.let {
                add(
                    HarnessDownloadSource(
                        artifactId = "acoustic",
                        type = HarnessDownloadSourceType.MODELSCOPE,
                        repo = msRepo,
                        branch = msBranch,
                        remotePath = it
                    )
                )
            }
        }
        directGgufUrl?.let {
            add(
                HarnessDownloadSource(
                    artifactId = "llm",
                    type = HarnessDownloadSourceType.DIRECT,
                    url = it
                )
            )
        }
        directMmprojUrl?.let {
            add(
                HarnessDownloadSource(
                    artifactId = "vision_projector",
                    type = HarnessDownloadSourceType.DIRECT,
                    url = it
                )
            )
        }
        directAcousticUrl?.let {
            add(
                HarnessDownloadSource(
                    artifactId = "acoustic",
                    type = HarnessDownloadSourceType.DIRECT,
                    url = it
                )
            )
        }
    }

    return HarnessModelSpec(
        id = id,
        displayName = displayName,
        family = inferHarnessModelFamily(),
        capabilities = capabilities,
        artifacts = artifacts,
        downloadSources = downloadSources,
        runtimeHints = inferRuntimeHints()
    )
}

private fun ModelInfo.inferHarnessModelFamily(): HarnessModelFamily = when {
    isTts -> HarnessModelFamily.VOXCPM2
    id.startsWith("minicpm-v") -> HarnessModelFamily.MINICPM_VISION
    id.startsWith("minicpm5") -> HarnessModelFamily.MINICPM_TEXT
    id.startsWith("llama") -> HarnessModelFamily.LLAMA
    id.startsWith("qwen") -> HarnessModelFamily.QWEN
    else -> HarnessModelFamily.OTHER
}

private fun ModelInfo.inferRuntimeHints(): HarnessRuntimeHints = when {
    id == "minicpm-v-4_6-instruct" -> HarnessRuntimeHints(
        defaultImageMaxSliceNums = LlamaEngine.DEFAULT_IMAGE_SLICE,
        contextSize = 8192
    )
    mmprojFileName != null -> HarnessRuntimeHints(
        defaultImageMaxSliceNums = LlamaEngine.DEFAULT_IMAGE_SLICE,
        contextSize = 4096
    )
    else -> HarnessRuntimeHints(contextSize = 4096)
}
