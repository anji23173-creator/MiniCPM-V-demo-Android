package com.example.minicpm_v_demo.harness

import com.example.minicpm_v_demo.LlamaState
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emitAll
import kotlinx.coroutines.flow.flow

data class HarnessChatRequest(
    val userPrompt: String,
    val systemPrompt: String? = null,
) {
    init {
        require(userPrompt.isNotBlank()) { "User prompt must not be blank" }
        require(systemPrompt == null || systemPrompt.isNotBlank()) {
            "System prompt must be null or non-blank"
        }
    }
}

interface HarnessBackend {
    val state: StateFlow<LlamaState>
    val isVisionSupported: Boolean
    val isVideoUnderstandingSupported: Boolean

    suspend fun loadModel(modelPath: String, mmprojPath: String? = null)
    suspend fun unloadModel()
    suspend fun prefillImage(imageData: ByteArray)
    suspend fun prefillVideoFrames(
        frames: List<ByteArray>,
        onProgress: suspend (current: Int, total: Int) -> Unit = { _, _ -> }
    )
    suspend fun setSystemPrompt(prompt: String)
    suspend fun clearContext()
    suspend fun setImageMaxSliceNums(n: Int)
    fun sendUserPrompt(message: String, predictLength: Int): Flow<String>

    /**
     * Sends a role-aware chat request to the runtime.
     *
     * A structured prompt starts from a fresh context because the native runtime only accepts a
     * system message immediately after model load/reset. This also prevents a previous turn from
     * changing the authority or position of the new system message. Conversation history needed by
     * character mode is already supplied explicitly by the Harness prompt compiler.
     */
    fun sendChatPrompt(request: HarnessChatRequest, predictLength: Int): Flow<String> = flow {
        request.systemPrompt?.let { systemPrompt ->
            clearContext()
            setSystemPrompt(systemPrompt)
        }
        emitAll(sendUserPrompt(request.userPrompt, predictLength))
    }

    fun cancelGeneration()
    fun resetToInitialized()
    fun destroy()
}
