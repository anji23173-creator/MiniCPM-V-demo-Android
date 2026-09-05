package com.example.minicpm_v_demo.harness.session

class MemoryPromptSelector {
    fun selectPromptSafeLongTerm(records: List<MemoryRecord>): List<MemoryRecord> {
        return records.filter { record ->
            record.promptSafe &&
                record.scope != "session" &&
                record.kind in setOf("summary_memory", "profile_memory", "character_memory")
        }
    }
}
