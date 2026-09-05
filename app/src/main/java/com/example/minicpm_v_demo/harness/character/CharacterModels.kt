package com.example.minicpm_v_demo.harness.character

data class HarnessChatMessage(
    val role: String,
    val content: String,
)

data class RuntimeContext(
    val storyCutoff: String? = null,
    val dynamicState: DynamicState? = null,
    val maxChars: Int = 4500,
    val topK: Int = 8,
    val conversationSummary: String = "",
)

data class CompiledCharacterPrompt(
    val messages: List<HarnessChatMessage>,
    val debug: CharacterPromptDebug,
)

data class CharacterPromptDebug(
    val npcId: String,
    val storyCutoff: String,
    val maxChars: Int,
    val promptChars: Int,
    val mandatoryChars: Int,
    val budgetExceededByMandatory: Boolean,
    val selectedItems: List<SelectedPromptItem>,
    val droppedItems: List<DroppedPromptItem>,
    val retrievalDecisions: List<RetrievalDecision>,
)

data class SelectedPromptItem(
    val kind: String,
    val id: String,
    val priority: Double,
)

data class DroppedPromptItem(
    val kind: String,
    val id: String,
    val reason: String,
)

data class RetrievalDecision(
    val eventId: String,
    val allowed: Boolean,
    val reason: String,
    val score: Double,
)

data class CharacterCard(
    val npcId: String,
    val identity: IdentityCore,
    val relationships: List<CharacterRelationship>,
    val knowledgeScope: KnowledgeScope,
    val dynamicState: DynamicState,
    val episodicMemory: List<EpisodicMemory>,
)

data class IdentityCore(
    val name: String,
    val aliases: List<String>,
    val worldviewPosition: String,
    val background: List<String>,
    val coreMotivations: List<String>,
    val values: List<String>,
    val psychologicalTraits: List<String>,
    val speechStyle: List<String>,
    val speechExamples: List<String>,
    val behaviorRules: List<String>,
    val hardConstraints: List<String>,
)

data class CharacterRelationship(
    val targetName: String,
    val relationshipType: String,
    val attitude: String,
)

data class KnowledgeScope(
    val worldFactRefs: Set<String>,
    val storyCutoff: String,
)

data class DynamicState(
    val scene: String,
    val emotion: EmotionState,
    val questState: String,
    val currentGoal: String,
    val affinity: Int,
)

data class EmotionState(
    val label: String,
    val trigger: String,
    val intensity: Double,
    val decayRule: String,
)

data class EpisodicMemory(
    val factRef: String,
    val validFrom: String,
    val validTo: String?,
    val source: String,
    val visibility: Set<String>,
    val confidence: Double,
)

data class StoryEvent(
    val eventId: String,
    val timeIndex: Int,
    val fact: String,
    val importance: Double,
    val confidence: Double,
    val visibility: Set<String>,
    val keywords: List<String>,
    val knowledgeByCharacter: Map<String, CharacterKnowledge>,
)

data class CharacterKnowledge(
    val source: String,
    val availableAfter: String,
    val confidence: Double,
)

data class RetrievedEvent(
    val event: StoryEvent,
    val score: Double,
    val matchedTerms: List<String>,
)

data class RetrievedMemory(
    val memory: EpisodicMemory,
    val event: StoryEvent,
    val score: Double,
)
