package com.example.minicpm_v_demo.harness.session

import com.example.minicpm_v_demo.harness.data.HarnessDataPaths
import com.example.minicpm_v_demo.harness.rag.SimpleJsonParser
import com.example.minicpm_v_demo.harness.rag.asJsonObject
import java.io.File
import java.util.UUID

data class MemoryRecord(
    val memoryId: String,
    val scope: String,
    val kind: String,
    val text: String,
    val importance: Double,
    val confidence: Double,
    val characterId: String?,
    val sessionId: String?,
    val sourceTurnIds: List<String> = emptyList(),
    val tags: List<String> = emptyList(),
    val promptSafe: Boolean = false,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
)

data class RetrievedMemoryRecord(
    val record: MemoryRecord,
    val score: Double,
)

class MemoryStore(private val paths: HarnessDataPaths) {
    private val memoryFile: File = File(paths.memoryDir, "memories.jsonl")

    fun append(record: MemoryRecord) {
        paths.ensureRuntimeDirs()
        memoryFile.appendText(jsonObject(serializeMap(record)) + "\n", Charsets.UTF_8)
    }

    fun observeTurn(session: ChatSession, turn: ChatTurn): MemoryRecord {
        val record = MemoryRecord(
            memoryId = UUID.randomUUID().toString().replace("-", ""),
            scope = "session",
            kind = "session_memory",
            text = "玩家：${turn.userText.trim()}\n角色：${turn.assistantText.trim()}",
            importance = 0.4,
            confidence = 1.0,
            characterId = session.characterId,
            sessionId = session.sessionId,
            sourceTurnIds = listOf(turn.turnId),
            tags = listOf("session_chat"),
            promptSafe = false,
        )
        append(record)
        return record
    }

    fun listRecords(
        sessionId: String? = null,
        characterId: String? = null,
        kind: String? = null,
    ): List<MemoryRecord> {
        if (!memoryFile.isFile) return emptyList()
        return memoryFile.readLines(Charsets.UTF_8)
            .asSequence()
            .filter { it.isNotBlank() }
            .mapNotNull { line ->
                runCatching {
                    parseRecord(SimpleJsonParser(line).parse().asJsonObject("memory record"))
                }.getOrNull()
            }
            .filter { record ->
                (sessionId == null || record.sessionId == sessionId) &&
                    (characterId == null || record.characterId == characterId) &&
                    (kind == null || record.kind == kind)
            }
            .toList()
    }

    fun search(
        query: String,
        sessionId: String? = null,
        characterId: String? = null,
        limit: Int = 5,
    ): List<RetrievedMemoryRecord> {
        val queryTerms = terms(query)
        return listRecords(sessionId = sessionId, characterId = characterId)
            .mapNotNull { record ->
                val overlap = queryTerms.intersect(terms(record.text)).size
                val substringBonus = if (query.isNotBlank() && record.text.contains(query)) 1 else 0
                val score = overlap + substringBonus + record.importance
                if (score > 0) RetrievedMemoryRecord(record, kotlin.math.round(score * 100000.0) / 100000.0) else null
            }
            .sortedWith(compareByDescending<RetrievedMemoryRecord> { it.score }.thenByDescending { it.record.updatedAt })
            .take(limit)
    }

    private fun serializeMap(record: MemoryRecord): Map<String, Any?> {
        return mapOf(
            "memory_id" to record.memoryId,
            "scope" to record.scope,
            "kind" to record.kind,
            "text" to record.text,
            "importance" to record.importance,
            "confidence" to record.confidence,
            "character_id" to record.characterId,
            "session_id" to record.sessionId,
            "source_turn_ids" to record.sourceTurnIds,
            "tags" to record.tags,
            "prompt_safe" to record.promptSafe,
            "created_at" to record.createdAt,
            "updated_at" to record.updatedAt,
        )
    }

    private fun parseRecord(value: Map<String, Any?>): MemoryRecord {
        return MemoryRecord(
            memoryId = value.optionalString("memory_id").orEmpty(),
            scope = value.optionalString("scope").orEmpty(),
            kind = value.optionalString("kind").orEmpty(),
            text = value.optionalString("text").orEmpty(),
            importance = value.optionalDouble("importance") ?: 0.0,
            confidence = value.optionalDouble("confidence") ?: 1.0,
            characterId = value.optionalString("character_id"),
            sessionId = value.optionalString("session_id"),
            sourceTurnIds = value.optionalStringList("source_turn_ids"),
            tags = value.optionalStringList("tags"),
            promptSafe = value["prompt_safe"] as? Boolean ?: false,
            createdAt = value.optionalLong("created_at") ?: 0L,
            updatedAt = value.optionalLong("updated_at") ?: 0L,
        )
    }

    private fun terms(value: String): Set<String> {
        val normalized = value.lowercase()
        val tokens = normalized.replace("\n", " ").split(" ").filter { it.isNotBlank() }.toSet()
        val chineseChars = normalized.filter { it in '\u4e00'..'\u9fff' }.map { it.toString() }.toSet()
        return tokens + chineseChars
    }
}
