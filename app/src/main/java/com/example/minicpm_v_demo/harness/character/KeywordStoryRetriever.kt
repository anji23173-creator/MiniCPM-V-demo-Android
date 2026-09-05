package com.example.minicpm_v_demo.harness.character

class KeywordStoryRetriever {
    fun retrieve(query: String, events: List<StoryEvent>, limit: Int = 12): List<RetrievedEvent> {
        val queryTerms = terms(query)
        val normalizedQuery = normalize(query)
        val results = mutableListOf<RetrievedEvent>()
        for (event in events) {
            val matchedKeywords = event.keywords.filter { keyword ->
                val normalizedKeyword = normalize(keyword)
                normalizedKeyword in normalizedQuery || normalizedQuery in normalizedKeyword
            }
            val eventTerms = terms(event.fact + event.keywords.joinToString(""))
            val overlap = queryTerms.intersect(eventTerms)
            if (matchedKeywords.isEmpty() && overlap.isEmpty()) continue
            val lexical = overlap.size.toDouble() / maxOf(1, queryTerms.size)
            // Exact phrases carry most of the signal for fictional names and terms. A
            // long name such as "太虚元序玄司营造法" should beat incidental two-character
            // n-gram overlap, while a character name can still recall its own events.
            val keywordScore = minOf(
                1.25,
                matchedKeywords.sumOf { keyword ->
                    val normalizedKeyword = normalize(keyword)
                    if (normalizedKeyword in normalizedQuery) {
                        keywordWeight(normalizedKeyword)
                    } else {
                        // The query only names the prefix/core of a longer keyword.
                        // Reward what the player actually typed, not the unmentioned tail.
                        keywordWeight(normalizedQuery)
                    }
                },
            )
            val score = lexical * 0.55 + keywordScore + event.importance * 0.08
            if (score < 0.2) continue
            val matched = (matchedKeywords + overlap.sorted()).distinct()
            results += RetrievedEvent(event, round5(score), matched)
        }
        return results.sortedWith(
            compareByDescending<RetrievedEvent> { it.score }
                .thenByDescending { it.event.importance }
                .thenBy { it.event.timeIndex },
        ).take(limit)
    }

    private fun normalize(text: String): String {
        var value = text.lowercase()
            .replace(Regex("\\s+"), "")
            .replace(Regex("[，。！？、：；“”‘’（）《》【】,.!?;:'\"()\\[\\]]"), "")
        for (filler in QueryFillers) {
            value = value.replace(filler, "")
        }
        return value
    }

    private fun keywordWeight(keyword: String): Double {
        val length = normalize(keyword).length
        return minOf(0.78, 0.30 + length * 0.08)
    }

    private fun terms(text: String): Set<String> {
        val normalized = normalize(text)
        val output = mutableSetOf<String>()
        Regex("[a-z0-9_]{2,}").findAll(normalized).forEach { output += it.value }
        val chinese = Regex("[\\u3400-\\u9fff]").findAll(normalized).joinToString("") { it.value }
        for (index in 0 until maxOf(0, chinese.length - 1)) {
            output += chinese.substring(index, index + 2)
        }
        for (index in 0 until maxOf(0, chinese.length - 2)) {
            output += chinese.substring(index, index + 3)
        }
        return output.filter { it.isNotBlank() && it !in SearchStopTerms }.toSet()
    }

    private fun round5(value: Double): Double = kotlin.math.round(value * 100000.0) / 100000.0

    private companion object {
        // Question scaffolding is noise; story-world names are deliberately not stop
        // terms. Removing names made queries such as "玄谙是什么" lose their only
        // discriminating token before they reached the event keywords.
        val QueryFillers = listOf(
            "究竟", "到底", "请问", "真的", "为什么", "是什么", "怎么样", "是不是",
            "会不会", "是谁", "什么", "怎么", "为何", "如何", "吗", "呢",
        )
        val SearchStopTerms = setOf("你是", "我是", "有何", "有关", "关于")
    }
}
