package com.example.minicpm_v_demo.harness.character

import com.example.minicpm_v_demo.harness.data.HarnessDataPaths

class CharacterPromptCompiler(
    private val loader: CharacterJsonLoader,
    private val retriever: KeywordStoryRetriever = KeywordStoryRetriever(),
    private val boundaryFilter: KnowledgeBoundaryFilter = KnowledgeBoundaryFilter(),
    private val memoryRetriever: MemoryRetriever = MemoryRetriever(),
) {
    private val events: List<StoryEvent> by lazy { loader.loadEvents() }
    private val eventsById: Map<String, StoryEvent> by lazy { events.associateBy { it.eventId } }
    private val template: String by lazy { loader.loadPromptTemplate() }

    fun availableCharacters(): List<CharacterCard> = loader.listCharacters()

    fun buildNpcPrompt(
        npcId: String,
        userInput: String,
        runtimeContext: RuntimeContext = RuntimeContext(),
    ): CompiledCharacterPrompt {
        require(userInput.isNotBlank()) { "userInput must not be empty" }
        require(runtimeContext.maxChars >= 400) { "maxChars must be at least 400" }
        val npc = loader.loadCharacter(npcId)
        val cutoff = runtimeContext.storyCutoff ?: npc.knowledgeScope.storyCutoff
        require(eventsById.containsKey(cutoff)) { "unknown story cutoff: $cutoff" }

        val candidates = retriever.retrieve(userInput, events, limit = maxOf(runtimeContext.topK * 2, 12))
        val (authorizedAll, decisions) = boundaryFilter.filter(candidates, npc, cutoff, events, userInput)
        val authorized = authorizedAll.take(runtimeContext.topK)
        val memories = memoryRetriever.retrieve(npc, authorized, events, cutoff, limit = 3)
        val memoryIds = memories.map { it.event.eventId }.toSet()
        val factCandidates = authorized.filter { it.event.eventId !in memoryIds }
        val relationships = selectRelationships(npc, userInput)
        val definitionIntent = isDefinitionQuery(userInput)
        val primaryDefinitionEventId = if (definitionIntent) {
            authorized.firstOrNull()?.event?.eventId
        } else {
            null
        }
        val dynamicState = runtimeContext.dynamicState ?: npc.dynamicState

        val mandatory = linkedMapOf(
            "global_summary" to compileGlobalSummary(npc, cutoff),
            "core_personality" to compileCorePersonality(npc),
            "speech_examples" to compileSpeechExamples(npc),
            "story_cutoff" to formatCutoff(cutoff),
            "dynamic_state" to compileDynamicState(dynamicState),
            "relevant_relationships" to "无。",
            "authorized_story_facts" to "无；不得自行补全。",
            "retrieved_memories" to "无。",
            "conversation_summary" to runtimeContext.conversationSummary.trim().take(100).ifBlank { "无。" },
        )

        var content = render(mandatory)
        require(content.length <= runtimeContext.maxChars) {
            "mandatory character prompt exceeds maxChars: ${content.length} > ${runtimeContext.maxChars}"
        }
        val optionalItems = mutableListOf<PromptCandidate>()
        relationships.forEach { relation ->
            optionalItems += PromptCandidate(
                section = "relevant_relationships",
                id = relation.targetName,
                text = "${relation.targetName}是你的${relation.relationshipType}；${relation.attitude.take(58)}",
                priority = if (definitionIntent) 1.65 else 2.0,
            )
        }
        factCandidates.forEach { item ->
            optionalItems += PromptCandidate(
                section = "authorized_story_facts",
                id = item.event.eventId,
                text = formatFact(item, npc),
                priority = item.score + item.event.importance +
                    definitionBoost(item.event.eventId, primaryDefinitionEventId),
            )
        }
        memories.forEach { item ->
            optionalItems += PromptCandidate(
                section = "retrieved_memories",
                id = item.event.eventId,
                text = formatMemory(item, npc),
                priority = item.score + 0.5 +
                    definitionBoost(item.event.eventId, primaryDefinitionEventId),
            )
        }
        optionalItems.sortByDescending { it.priority }

        val selected = mutableListOf<SelectedPromptItem>()
        val dropped = mutableListOf<DroppedPromptItem>()
        val sectionLines = mutableMapOf(
            "relevant_relationships" to mutableListOf<String>(),
            "authorized_story_facts" to mutableListOf<String>(),
            "retrieved_memories" to mutableListOf<String>(),
        )
        for (item in optionalItems) {
            val proposedLines = sectionLines.mapValues { it.value.toMutableList() }.toMutableMap()
            proposedLines.getValue(item.section).add(item.text)
            val values = mandatory.toMutableMap()
            proposedLines.forEach { (section, lines) ->
                if (lines.isNotEmpty()) values[section] = lines.joinToString("\n")
            }
            val proposed = render(values)
            if (proposed.length <= runtimeContext.maxChars) {
                sectionLines.clear()
                sectionLines.putAll(proposedLines)
                content = proposed
                selected += SelectedPromptItem(item.section, item.id, round5(item.priority))
            } else {
                dropped += DroppedPromptItem(item.section, item.id, "character_budget")
            }
        }

        val mandatorySize = render(mandatory).length
        return CompiledCharacterPrompt(
            messages = listOf(
                HarnessChatMessage("system", content),
                HarnessChatMessage("user", userInput),
            ),
            debug = CharacterPromptDebug(
                npcId = npcId,
                storyCutoff = cutoff,
                maxChars = runtimeContext.maxChars,
                promptChars = content.length,
                mandatoryChars = mandatorySize,
                budgetExceededByMandatory = mandatorySize > runtimeContext.maxChars,
                selectedItems = selected,
                droppedItems = dropped,
                retrievalDecisions = decisions,
            ),
        )
    }

    private fun render(values: Map<String, String>): String {
        var rendered = template
        for ((key, value) in values) {
            rendered = rendered.replace("{{$key}}", value)
        }
        require(!rendered.contains("{{") && !rendered.contains("}}")) {
            "shared prompt contains an unresolved placeholder"
        }
        return rendered.trim()
    }

    private fun compileGlobalSummary(npc: CharacterCard, cutoff: String): String {
        val identity = npc.identity
        val alias = identity.aliases.firstOrNull()?.let { "，亲近的人也会叫你$it" }.orEmpty()
        return "${identity.name}$alias。${identity.worldviewPosition.take(58)}"
    }

    private fun compileCorePersonality(npc: CharacterCard): String {
        val identity = npc.identity
        return identity.speechStyle.take(2).joinToString("；") { it.take(52) }
            .ifBlank { "自然、简洁，像真实的人在交谈。" }
    }

    private fun compileSpeechExamples(npc: CharacterCard): String {
        return npc.identity.speechExamples.take(4)
            .joinToString("\n") { "“${it.take(54)}”" }
            .ifBlank { "“此事我知道多少，便只说多少。”" }
    }

    private fun compileDynamicState(state: DynamicState): String {
        val emotion = state.emotion
        return "${state.scene.take(46)}；你此刻${emotion.label}。"
    }

    private fun formatCutoff(cutoff: String): String {
        val event = eventsById.getValue(cutoff)
        return "$cutoff（叙事序号 ${event.timeIndex}）"
    }

    private fun formatFact(item: RetrievedEvent, npc: CharacterCard): String {
        val event = item.event
        val knowledge = event.knowledgeByCharacter.getValue(npc.npcId)
        val perspectiveFact = event.fact.replace(npc.identity.name, "你")
        return "${KnowledgeLeadIns.getValue(knowledge.source)}$perspectiveFact"
    }

    private fun formatMemory(item: RetrievedMemory, npc: CharacterCard): String {
        val perspectiveFact = item.event.fact.replace(npc.identity.name, "你")
        return "${KnowledgeLeadIns.getValue(item.memory.source)}$perspectiveFact"
    }

    private fun isDefinitionQuery(query: String): Boolean = DefinitionSignals.any { it in query }

    private fun definitionBoost(eventId: String, primaryEventId: String?): Double =
        if (eventId == primaryEventId) 1.5 else 0.0

    private fun selectRelationships(npc: CharacterCard, query: String): List<CharacterRelationship> {
        val selected = npc.relationships.filter { it.targetName in query }
        if (selected.isNotEmpty()) return selected
        return if (listOf("关系", "怎么看", "他", "祂", "他们").any { it in query }) {
            npc.relationships.take(2)
        } else {
            emptyList()
        }
    }

    private fun round5(value: Double): Double = kotlin.math.round(value * 100000.0) / 100000.0

    private data class PromptCandidate(
        val section: String,
        val id: String,
        val text: String,
        val priority: Double,
    )

    companion object {
        private val KnowledgeLeadIns = mapOf(
            "direct" to "你亲历并确认：",
            "witnessed" to "你亲眼见到：",
            "reported" to "你听人提及：",
            "inferred" to "你据现有线索推断：",
        )
        private val DefinitionSignals = listOf(
            "是什么", "究竟是什么", "到底是什么", "是谁", "何人", "何物",
            "什么关系", "有何关系", "有什么关系", "指什么",
        )

        private fun List<String>.takeJoined(limit: Int, itemChars: Int): String =
            take(limit)
                .joinToString("；") { it.take(itemChars) }
                .ifBlank { "无" }

        fun fromPaths(paths: HarnessDataPaths): CharacterPromptCompiler {
            return CharacterPromptCompiler(
                CharacterJsonLoader(
                    charactersDir = paths.charactersDir,
                    storyEventsFile = paths.storyEventsFile,
                    promptTemplateFile = java.io.File(paths.promptsDir, "roleplay_system.prompt"),
                ),
            )
        }
    }
}
