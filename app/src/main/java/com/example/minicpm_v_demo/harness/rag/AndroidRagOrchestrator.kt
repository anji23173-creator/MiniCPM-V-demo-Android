package com.example.minicpm_v_demo.harness.rag

import android.content.Context
import com.example.minicpm_v_demo.harness.HarnessModelFamily
import com.example.minicpm_v_demo.harness.character.CharacterCard
import com.example.minicpm_v_demo.harness.character.CharacterPromptCompiler
import com.example.minicpm_v_demo.harness.character.RuntimeContext
import com.example.minicpm_v_demo.harness.chat.ChatTemplateRenderer
import com.example.minicpm_v_demo.harness.chat.RenderedChatPrompt
import com.example.minicpm_v_demo.harness.data.HarnessDataPaths

enum class RagMode {
    OFF,
    RAG,
    CHARACTER_RAG,
}

data class CompiledAndroidPrompt(
    val renderedPrompt: String,
    val rendered: RenderedChatPrompt,
    val sources: List<RagSource>,
    val contextText: String,
    val characterDebug: Any? = null,
    val mode: RagMode,
)

class AndroidRagOrchestrator(
    private val ragSearchService: RagSearchService,
    private val characterCompiler: CharacterPromptCompiler,
    private val promptBuilder: PromptBuilder = PromptBuilder(),
    private val characterRagPromptBuilder: CharacterRagPromptBuilder = CharacterRagPromptBuilder(),
) {
    fun availableCharacters(): List<CharacterCard> = characterCompiler.availableCharacters()

    fun compile(
        userInput: String,
        mode: RagMode = RagMode.OFF,
        characterId: String = "lu_jiangxian",
        storyCutoff: String? = "evt-010",
        topK: Int = 1,
        maxCharacterChars: Int = 900,
        conversationSummary: String = "",
        modelFamily: HarnessModelFamily = HarnessModelFamily.MINICPM_TEXT,
    ): CompiledAndroidPrompt {
        if (mode == RagMode.OFF) {
            val messages = listOf(
                com.example.minicpm_v_demo.harness.character.HarnessChatMessage("system", "你是一个本地助手。"),
                com.example.minicpm_v_demo.harness.character.HarnessChatMessage("user", userInput),
            )
            val rendered = ChatTemplateRenderer.forModelFamily(modelFamily).render(messages)
            return CompiledAndroidPrompt(rendered.renderedSinglePrompt, rendered, emptyList(), "", null, mode)
        }
        val renderer = ChatTemplateRenderer.forModelFamily(modelFamily)
        return if (mode == RagMode.RAG) {
            val results = ragSearchService.search(userInput, topK, minScore = GENERAL_RAG_MIN_SCORE)
            val prompt = promptBuilder.build(userInput, results)
            val rendered = renderer.render(prompt.messages)
            CompiledAndroidPrompt(
                renderedPrompt = rendered.renderedSinglePrompt,
                rendered = rendered,
                sources = prompt.sources,
                contextText = prompt.contextText,
                mode = mode,
            )
        } else {
            val results = if (CharacterQueryRouter.requiresExternalKnowledge(userInput)) {
                ragSearchService.search(
                    query = userInput,
                    topK = maxOf(topK * 8, 20),
                    minScore = CHARACTER_EXTERNAL_RAG_MIN_SCORE,
                ).filterNot { it.chunk.sourcePath.contains("/novel_test/") }
                    .take(topK)
            } else {
                emptyList()
            }
            val characterPrompt = characterCompiler.buildNpcPrompt(
                npcId = characterId,
                userInput = userInput,
                runtimeContext = RuntimeContext(
                    storyCutoff = storyCutoff,
                    maxChars = maxCharacterChars,
                    conversationSummary = conversationSummary,
                ),
            )
            val prompt = characterRagPromptBuilder.build(
                characterMessages = characterPrompt.messages,
                userInput = userInput,
                results = results,
                characterDebug = characterPrompt.debug,
            )
            val rendered = renderer.render(prompt.messages)
            CompiledAndroidPrompt(
                renderedPrompt = rendered.renderedSinglePrompt,
                rendered = rendered,
                sources = prompt.sources,
                contextText = prompt.contextText,
                characterDebug = prompt.characterDebug,
                mode = mode,
            )
        }
    }

    companion object {
        private const val GENERAL_RAG_MIN_SCORE = 0.10
        private const val CHARACTER_EXTERNAL_RAG_MIN_SCORE = 0.10

        fun fromContext(context: Context): AndroidRagOrchestrator {
            val paths = HarnessDataPaths.from(context.applicationContext)
            return AndroidRagOrchestrator(
                ragSearchService = RagSearchService.fromPaths(paths),
                characterCompiler = CharacterPromptCompiler.fromPaths(paths),
            )
        }
    }
}

internal object CharacterQueryRouter {
    private val externalKnowledgeSignals = listOf(
        "外部资料", "文档", "文件", "新闻", "现实", "现实世界", "世界杯", "联网", "搜索",
    )

    fun requiresExternalKnowledge(query: String): Boolean =
        externalKnowledgeSignals.any { signal -> signal in query }
}
