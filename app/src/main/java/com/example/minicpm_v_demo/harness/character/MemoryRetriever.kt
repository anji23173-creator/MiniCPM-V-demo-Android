package com.example.minicpm_v_demo.harness.character

class MemoryRetriever {
    fun retrieve(
        npc: CharacterCard,
        authorized: List<RetrievedEvent>,
        events: List<StoryEvent>,
        storyCutoff: String,
        limit: Int = 3,
    ): List<RetrievedMemory> {
        val indexes = events.associate { it.eventId to it.timeIndex }
        val cutoff = indexes[storyCutoff] ?: error("unknown story cutoff: $storyCutoff")
        val eventById = events.associateBy { it.eventId }
        val scoreById = authorized.associate { it.event.eventId to it.score }
        return npc.episodicMemory.mapNotNull { memory ->
            val score = scoreById[memory.factRef] ?: return@mapNotNull null
            val event = eventById[memory.factRef] ?: return@mapNotNull null
            val validFrom = indexes[memory.validFrom] ?: return@mapNotNull null
            val validTo = memory.validTo?.let { indexes[it] }
            if (validFrom > cutoff) return@mapNotNull null
            if (validTo != null && validTo < cutoff) return@mapNotNull null
            if (npc.npcId !in memory.visibility && "public" !in memory.visibility) return@mapNotNull null
            RetrievedMemory(memory, event, score * memory.confidence)
        }.sortedByDescending { it.score }.take(limit)
    }
}

