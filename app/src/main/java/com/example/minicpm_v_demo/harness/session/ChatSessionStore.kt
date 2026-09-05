package com.example.minicpm_v_demo.harness.session

import com.example.minicpm_v_demo.harness.data.HarnessDataPaths
import com.example.minicpm_v_demo.harness.rag.RagSource
import com.example.minicpm_v_demo.harness.rag.SimpleJsonParser
import com.example.minicpm_v_demo.harness.rag.asJsonObject
import java.io.File
import java.util.UUID

class ChatSessionStore(
    private val paths: HarnessDataPaths,
    private val summaryBuilder: ConversationSummaryBuilder = ConversationSummaryBuilder(),
) {
    private val recentSessionFile: File = File(paths.sessionsDir, "recent_session.json")

    fun create(
        characterId: String,
        storyCutoff: String?,
        selectedModelId: String,
        characterPackId: String = "character_system",
    ): ChatSession {
        return ChatSession(
            sessionId = UUID.randomUUID().toString().replace("-", ""),
            characterId = characterId,
            characterPackId = characterPackId,
            storyCutoff = storyCutoff,
            selectedModelId = selectedModelId,
        ).also { save(it) }
    }

    fun loadRecentSession(): ChatSession? {
        if (!recentSessionFile.isFile) return null
        return runCatching {
            parseSession(SimpleJsonParser(recentSessionFile.readText(Charsets.UTF_8)).parse().asJsonObject("session"))
        }.getOrNull()
    }

    fun appendTurn(session: ChatSession, turn: ChatTurn): ChatSession {
        val turns = session.turns + turn
        val updated = session.copy(
            turns = turns,
            conversationSummary = summaryBuilder.build(turns),
            selectedModelId = turn.modelId,
            updatedAt = System.currentTimeMillis(),
        )
        save(updated)
        return updated
    }

    fun save(session: ChatSession) {
        paths.ensureRuntimeDirs()
        recentSessionFile.writeText(serialize(session), Charsets.UTF_8)
    }

    fun clearRecentSession() {
        if (recentSessionFile.isFile) recentSessionFile.delete()
    }

    private fun serialize(session: ChatSession): String {
        return jsonObject(
            mapOf(
                "session_id" to session.sessionId,
                "character_id" to session.characterId,
                "character_pack_id" to session.characterPackId,
                "story_cutoff" to session.storyCutoff,
                "selected_model_id" to session.selectedModelId,
                "turns" to session.turns.map { serializeTurnMap(it) },
                "conversation_summary" to session.conversationSummary,
                "created_at" to session.createdAt,
                "updated_at" to session.updatedAt,
            ),
        )
    }

    private fun serializeTurnMap(turn: ChatTurn): Map<String, Any?> {
        return mapOf(
            "turn_id" to turn.turnId,
            "user_text" to turn.userText,
            "assistant_text" to turn.assistantText,
            "rag_mode" to turn.ragMode,
            "sources" to turn.sources.map {
                mapOf(
                    "source" to it.source,
                    "start" to it.start,
                    "end" to it.end,
                    "score" to it.score,
                )
            },
            "rendered_prompt" to turn.renderedPrompt,
            "character_id" to turn.characterId,
            "model_id" to turn.modelId,
            "created_at" to turn.createdAt,
        )
    }

    private fun parseSession(value: Map<String, Any?>): ChatSession {
        return ChatSession(
            sessionId = value.optionalString("session_id").orEmpty(),
            characterId = value.optionalString("character_id").orEmpty(),
            characterPackId = value.optionalString("character_pack_id") ?: "character_system",
            storyCutoff = value.optionalString("story_cutoff"),
            selectedModelId = value.optionalString("selected_model_id").orEmpty(),
            turns = (value["turns"] as? List<*>).orEmpty().mapNotNull { raw ->
                (raw as? Map<*, *>)?.entries?.associate { it.key.toString() to it.value }?.let(::parseTurn)
            },
            conversationSummary = value.optionalString("conversation_summary").orEmpty(),
            createdAt = value.optionalLong("created_at") ?: 0L,
            updatedAt = value.optionalLong("updated_at") ?: 0L,
        )
    }

    private fun parseTurn(value: Map<String, Any?>): ChatTurn {
        return ChatTurn(
            turnId = value.optionalString("turn_id").orEmpty(),
            userText = value.optionalString("user_text").orEmpty(),
            assistantText = value.optionalString("assistant_text").orEmpty(),
            ragMode = value.optionalString("rag_mode").orEmpty(),
            sources = (value["sources"] as? List<*>).orEmpty().mapNotNull { raw ->
                (raw as? Map<*, *>)?.entries?.associate { it.key.toString() to it.value }?.let(::parseSource)
            },
            renderedPrompt = value.optionalString("rendered_prompt"),
            characterId = value.optionalString("character_id").orEmpty(),
            modelId = value.optionalString("model_id").orEmpty(),
            createdAt = value.optionalLong("created_at") ?: 0L,
        )
    }

    private fun parseSource(value: Map<String, Any?>): RagSource {
        return RagSource(
            source = value.optionalString("source").orEmpty(),
            start = value.optionalLong("start")?.toInt() ?: 0,
            end = value.optionalLong("end")?.toInt() ?: 0,
            score = value.optionalDouble("score") ?: 0.0,
        )
    }
}
