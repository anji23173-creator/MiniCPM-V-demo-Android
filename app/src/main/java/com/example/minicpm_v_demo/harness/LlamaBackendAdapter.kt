package com.example.minicpm_v_demo.harness

import android.content.Context
import com.example.minicpm_v_demo.LlamaEngine
import com.example.minicpm_v_demo.LlamaState
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow

class LlamaBackendAdapter(context: Context) : HarnessBackend {
    private val engine = LlamaEngine.getInstance(context.applicationContext)

    override val state: StateFlow<LlamaState>
        get() = engine.state

    override val isVisionSupported: Boolean
        get() = engine.isVisionSupported

    override val isVideoUnderstandingSupported: Boolean
        get() = engine.isVideoUnderstandingSupported

    override suspend fun loadModel(modelPath: String, mmprojPath: String?) {
        engine.loadModel(modelPath, mmprojPath)
    }

    override suspend fun unloadModel() {
        engine.unloadModel()
    }

    override suspend fun prefillImage(imageData: ByteArray) {
        engine.prefillImage(imageData)
    }

    override suspend fun prefillVideoFrames(
        frames: List<ByteArray>,
        onProgress: suspend (current: Int, total: Int) -> Unit
    ) {
        engine.prefillVideoFrames(frames, onProgress)
    }

    override suspend fun setSystemPrompt(prompt: String) {
        engine.setSystemPrompt(prompt)
    }

    override suspend fun clearContext() {
        engine.clearContext()
    }

    override suspend fun setImageMaxSliceNums(n: Int) {
        engine.setImageMaxSliceNums(n)
    }

    override fun sendUserPrompt(message: String, predictLength: Int): Flow<String> =
        engine.sendUserPrompt(message, predictLength)

    override fun cancelGeneration() {
        engine.cancelGeneration()
    }

    override fun resetToInitialized() {
        engine.resetToInitialized()
    }

    override fun destroy() {
        engine.destroy()
    }
}
