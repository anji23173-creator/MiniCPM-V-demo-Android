package com.example.minicpm_v_demo.harness.rag

import com.example.minicpm_v_demo.harness.character.HarnessChatMessage

data class RagSource(
    val source: String,
    val start: Int,
    val end: Int,
    val score: Double,
)

data class CompiledRagPrompt(
    val messages: List<HarnessChatMessage>,
    val contextText: String,
    val sources: List<RagSource>,
)

class PromptBuilder(
    private val maxContextChars: Int = 900,
) {
    init {
        require(maxContextChars >= 500) { "maxContextChars must be at least 500" }
    }

    fun build(query: String, results: List<SearchResult>): CompiledRagPrompt {
        val (contextText, sources) = compileContext(results)
        val system = listOf(
            "你是一个本地 RAG 助手。",
            "你必须优先依据<检索资料>回答。不要把检索资料之外的信息说成已证实事实。",
        ).joinToString("\n\n")
        val user = listOf(
            "<检索资料>",
            contextText,
            "</检索资料>",
            "",
            "<用户问题>",
            query,
            "</用户问题>",
        ).joinToString("\n")
        return CompiledRagPrompt(
            messages = listOf(
                HarnessChatMessage("system", system),
                HarnessChatMessage("user", user),
            ),
            contextText = contextText,
            sources = sources,
        )
    }

    private fun compileContext(results: List<SearchResult>): Pair<String, List<RagSource>> {
        val parts = mutableListOf<String>()
        val sources = mutableListOf<RagSource>()
        var usedChars = 0
        for ((index, result) in results.withIndex()) {
            val block = "[资料 ${index + 1}] source=${result.chunk.sourcePath} " +
                "span=${result.chunk.start}:${result.chunk.end} " +
                "score=${"%.4f".format(result.score)}\n${result.chunk.text}"
            val selectedBlock = if (usedChars + block.length > maxContextChars) {
                if (parts.isNotEmpty()) continue
                block.take(maxContextChars)
            } else {
                block
            }
            parts += selectedBlock
            usedChars += selectedBlock.length
            sources += RagSource(
                source = result.chunk.sourcePath,
                start = result.chunk.start,
                end = result.chunk.end,
                score = round6(result.score),
            )
        }
        return (parts.joinToString("\n\n").ifBlank { "没有检索到可用资料。" }) to sources
    }
}

internal fun round6(value: Double): Double = kotlin.math.round(value * 1000000.0) / 1000000.0
