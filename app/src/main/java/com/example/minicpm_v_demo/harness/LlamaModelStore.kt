package com.example.minicpm_v_demo.harness

import android.content.Context
import com.example.minicpm_v_demo.LlamaEngine
import com.example.minicpm_v_demo.ModelInfo
import java.io.File

data class HarnessModelAvailability(
    val model: ModelInfo,
    val ggufMissing: Boolean,
    val supportArtifactMissing: Boolean
)

data class LlamaModelFiles(
    val model: ModelInfo,
    val spec: HarnessModelSpec,
    val artifactFiles: Map<String, File>
)

class LlamaModelStore(private val context: Context) {

    fun migrateLegacyLayoutIfNeeded() {
        LlamaEngine.migrateLegacyLayoutIfNeeded(context)
    }

    fun getSelectedModel(): ModelInfo = LlamaEngine.getSelectedModel(context)

    fun setSelectedModel(modelId: String) {
        LlamaEngine.setSelectedModel(context, modelId)
    }

    fun markModelSwitched() {
        LlamaEngine.markModelSwitched(context)
    }

    fun consumeModelSwitched(): Boolean = LlamaEngine.consumeModelSwitched(context)

    fun getImageMaxSliceNums(): Int = LlamaEngine.getImageMaxSliceNums(context)

    fun getSelectedModelSpec(): HarnessModelSpec =
        HarnessModelRegistry.findSpec(getSelectedModel().id) ?: HarnessModelRegistry.defaultEntry.spec

    fun getSelectedModelFiles(): LlamaModelFiles {
        val model = getSelectedModel()
        val spec = getSelectedModelSpec()
        val artifactFiles = buildMap {
            put("llm", File(LlamaEngine.modelPath(context)))
            LlamaEngine.mmprojPath(context)?.let { put("vision_projector", File(it)) }
            LlamaEngine.acousticPath(context)?.let { put("acoustic", File(it)) }
        }
        return LlamaModelFiles(
            model = model,
            spec = spec,
            artifactFiles = artifactFiles
        )
    }

    fun getSelectedModelAvailability(): HarnessModelAvailability {
        val files = getSelectedModelFiles()
        val ggufMissing = files.artifactFiles["llm"]?.exists() != true
        val supportArtifactMissing = files.spec.artifacts
            .filter { it.required && it.id != "llm" }
            .any { artifact -> files.artifactFiles[artifact.id]?.exists() != true }
        return HarnessModelAvailability(
            model = files.model,
            ggufMissing = ggufMissing,
            supportArtifactMissing = supportArtifactMissing
        )
    }

    fun isSelectedModelDownloaded(): Boolean {
        val files = getSelectedModelFiles()
        val requiredArtifacts = files.spec.artifacts.filter { it.required }
        return requiredArtifacts.all { artifact ->
            files.artifactFiles[artifact.id]?.exists() == true
        }
    }

    fun selectedModelArtifactNames(): List<String> =
        getSelectedModelSpec().artifacts.map { it.fileName }

    fun deleteSelectedModelFiles(): Boolean {
        val files = getSelectedModelFiles()
        var deleted = false
        for (file in files.artifactFiles.values) {
            if (file.exists() && file.delete()) {
                deleted = true
            }
        }
        return deleted
    }
}
