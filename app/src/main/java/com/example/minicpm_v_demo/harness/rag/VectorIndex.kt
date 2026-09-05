package com.example.minicpm_v_demo.harness.rag

import java.io.File

data class RagChunk(
    val id: String,
    val text: String,
    val sourcePath: String,
    val start: Int,
    val end: Int,
    val metadata: Map<String, String>,
)

data class IndexedChunk(
    val chunk: RagChunk,
    val embedding: DoubleArray,
)

data class SearchResult(
    val chunk: RagChunk,
    val score: Double,
)

class VectorIndex(
    private val items: List<IndexedChunk>,
) {
    val size: Int get() = items.size

    fun search(query: String, embeddingModel: EmbeddingModel, topK: Int = 5): List<SearchResult> {
        require(topK > 0) { "topK must be positive" }
        val queryEmbedding = embeddingModel.embed(listOf(query)).first()
        return items
            .map { SearchResult(it.chunk, cosine(queryEmbedding, it.embedding)) }
            .sortedByDescending { it.score }
            .take(topK)
    }

    companion object {
        fun load(file: File): VectorIndex {
            require(file.isFile) { "RAG index does not exist: ${file.absolutePath}" }
            return fromJson(file.readText(Charsets.UTF_8))
        }

        fun fromJson(json: String): VectorIndex {
            val root = SimpleJsonParser(json).parse().asJsonObject("index")
            val schemaVersion = root.stringValue("schema_version")
            require(schemaVersion == "1.1") { "Unsupported RAG index schema: $schemaVersion" }
            val items = root["items"].asJsonArray("items").mapIndexed { itemIndex, rawItem ->
                val item = rawItem.asJsonObject("items[$itemIndex]")
                val chunkObject = item["chunk"].asJsonObject("items[$itemIndex].chunk")
                IndexedChunk(
                    chunk = RagChunk(
                        id = chunkObject.stringValue("id"),
                        text = chunkObject.stringValue("text"),
                        sourcePath = chunkObject.stringValue("source_path"),
                        start = chunkObject.intValue("start"),
                        end = chunkObject.intValue("end"),
                        metadata = parseMetadata(chunkObject["metadata"].asJsonObject("metadata")),
                    ),
                    embedding = item.doubleListValue("embedding").toDoubleArray(),
                )
            }
            return VectorIndex(items)
        }

        private fun parseMetadata(value: Map<String, Any?>): Map<String, String> {
            return value.mapValues { (_, raw) -> raw?.toString().orEmpty() }
        }
    }
}

