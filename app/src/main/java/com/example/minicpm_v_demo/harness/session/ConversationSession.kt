package com.example.minicpm_v_demo.harness.session

import com.example.minicpm_v_demo.harness.rag.RagSource

data class ChatSession(
    val sessionId: String,
    val characterId: String,
    val characterPackId: String,
    val storyCutoff: String?,
    val selectedModelId: String,
    val turns: List<ChatTurn> = emptyList(),
    val conversationSummary: String = "",
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
)

data class ChatTurn(
    val turnId: String,
    val userText: String,
    val assistantText: String,
    val ragMode: String,
    val sources: List<RagSource> = emptyList(),
    val renderedPrompt: String? = null,
    val characterId: String,
    val modelId: String,
    val createdAt: Long = System.currentTimeMillis(),
)
