package com.example.minicpm_v_demo.harness.character

import com.example.minicpm_v_demo.harness.rag.SimpleJsonParser
import com.example.minicpm_v_demo.harness.rag.asJsonArray
import com.example.minicpm_v_demo.harness.rag.asJsonObject
import com.example.minicpm_v_demo.harness.rag.intValue
import com.example.minicpm_v_demo.harness.rag.stringValue
import java.io.File

class CharacterJsonLoader(
    private val charactersDir: File,
    private val storyEventsFile: File,
    private val promptTemplateFile: File,
) {
    fun loadCharacter(npcId: String): CharacterCard {
        val file = File(charactersDir, "$npcId.json")
        require(file.isFile) { "Unknown NPC: $npcId" }
        return parseCharacter(SimpleJsonParser(file.readText(Charsets.UTF_8)).parse().asJsonObject("character"))
    }

    fun listCharacters(): List<CharacterCard> {
        require(charactersDir.isDirectory) { "Characters directory does not exist: ${charactersDir.absolutePath}" }
        return charactersDir.listFiles { file -> file.isFile && file.extension == "json" }
            .orEmpty()
            .sortedBy { it.nameWithoutExtension }
            .map { file -> loadCharacter(file.nameWithoutExtension) }
    }

    fun loadEvents(): List<StoryEvent> {
        require(storyEventsFile.isFile) { "Story events file does not exist: ${storyEventsFile.absolutePath}" }
        return storyEventsFile.readLines(Charsets.UTF_8)
            .filter { it.isNotBlank() }
            .map { parseStoryEvent(SimpleJsonParser(it).parse().asJsonObject("story event")) }
    }

    fun loadPromptTemplate(): String {
        require(promptTemplateFile.isFile) { "Prompt template does not exist: ${promptTemplateFile.absolutePath}" }
        return promptTemplateFile.readText(Charsets.UTF_8)
    }

    private fun parseCharacter(root: Map<String, Any?>): CharacterCard {
        val identity = root["identity_core"].asJsonObject("identity_core")
        val knowledgeScope = root["knowledge_scope"].asJsonObject("knowledge_scope")
        return CharacterCard(
            npcId = root.stringValue("npc_id"),
            identity = IdentityCore(
                name = identity.stringValue("name"),
                aliases = identity.stringList("aliases"),
                worldviewPosition = identity.stringValue("worldview_position"),
                background = identity.stringList("background"),
                coreMotivations = identity.stringList("core_motivations"),
                values = identity.stringList("values"),
                psychologicalTraits = identity.stringList("psychological_traits"),
                speechStyle = identity.stringList("speech_style"),
                speechExamples = identity.optionalStringList("speech_examples"),
                behaviorRules = identity.stringList("behavior_rules"),
                hardConstraints = identity.stringList("hard_constraints"),
            ),
            relationships = root["relationships"].asJsonArray("relationships").map { raw ->
                val relation = raw.asJsonObject("relationship")
                CharacterRelationship(
                    targetName = relation.stringValue("target_name"),
                    relationshipType = relation.stringValue("relationship_type"),
                    attitude = relation.stringValue("attitude"),
                )
            },
            knowledgeScope = KnowledgeScope(
                worldFactRefs = knowledgeScope.stringList("world_fact_refs").toSet(),
                storyCutoff = knowledgeScope.stringValue("story_cutoff"),
            ),
            dynamicState = parseDynamicState(root["dynamic_state"].asJsonObject("dynamic_state")),
            episodicMemory = root["episodic_memory"].asJsonArray("episodic_memory").map { raw ->
                val memory = raw.asJsonObject("episodic_memory item")
                EpisodicMemory(
                    factRef = memory.stringValue("fact_ref"),
                    validFrom = memory.stringValue("valid_from"),
                    validTo = memory["valid_to"] as? String,
                    source = memory.stringValue("source"),
                    visibility = memory.stringList("visibility").toSet(),
                    confidence = memory.doubleValue("confidence"),
                )
            },
        )
    }

    private fun Map<String, Any?>.optionalStringList(key: String): List<String> =
        (this[key] as? List<*>)?.mapNotNull { it as? String }.orEmpty()

    private fun parseDynamicState(value: Map<String, Any?>): DynamicState {
        val emotion = value["emotion"].asJsonObject("emotion")
        return DynamicState(
            scene = value.stringValue("scene"),
            emotion = EmotionState(
                label = emotion.stringValue("label"),
                trigger = emotion.stringValue("trigger"),
                intensity = emotion.doubleValue("intensity"),
                decayRule = emotion.stringValue("decay_rule"),
            ),
            questState = value.stringValue("quest_state"),
            currentGoal = value.stringValue("current_goal"),
            affinity = value.intValue("affinity"),
        )
    }

    private fun parseStoryEvent(root: Map<String, Any?>): StoryEvent {
        val knowledge = root["knowledge_by_character"].asJsonObject("knowledge_by_character")
        return StoryEvent(
            eventId = root.stringValue("event_id"),
            timeIndex = root.intValue("time_index"),
            fact = root.stringValue("fact"),
            importance = root.doubleValue("importance"),
            confidence = root.doubleValue("confidence"),
            visibility = root.stringList("visibility").toSet(),
            keywords = root.stringList("keywords"),
            knowledgeByCharacter = knowledge.mapValues { (_, raw) ->
                val item = raw.asJsonObject("knowledge item")
                CharacterKnowledge(
                    source = item.stringValue("source"),
                    availableAfter = item.stringValue("available_after"),
                    confidence = item.doubleValue("confidence"),
                )
            },
        )
    }

    private fun Map<String, Any?>.stringList(key: String): List<String> {
        return this[key].asJsonArray(key).map { it as? String ?: error("$key must contain strings") }
    }

    private fun Map<String, Any?>.doubleValue(key: String): Double {
        return this[key] as? Double ?: error("Missing number key: $key")
    }
}
