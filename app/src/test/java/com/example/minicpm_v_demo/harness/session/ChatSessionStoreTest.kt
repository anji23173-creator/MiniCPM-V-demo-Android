package com.example.minicpm_v_demo.harness.session

import com.example.minicpm_v_demo.harness.data.HarnessDataPaths
import com.example.minicpm_v_demo.harness.rag.RagMode
import com.example.minicpm_v_demo.harness.rag.RagSource
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

class ChatSessionStoreTest {
    @Test
    fun appendTurnPersistsRecentSessionWithSourcesModelAndSummary() {
        val tempRoot = Files.createTempDirectory("chat-session-store-test").toFile()
        try {
            val store = ChatSessionStore(HarnessDataPaths(File(tempRoot, "harness")))
            val session = store.create(
                characterId = "lu_jiangxian",
                storyCutoff = "evt-010",
                selectedModelId = "minicpm-test",
            )
            val turn = ChatTurn(
                turnId = "turn-1",
                userText = "玄谙是什么？",
                assistantText = "我只能说到当前剧情已知的部分。",
                ragMode = RagMode.CHARACTER_RAG.name,
                sources = listOf(RagSource("docs/a.md", 3, 9, 0.75)),
                renderedPrompt = "<|system|>身份：我是陆江仙",
                characterId = "lu_jiangxian",
                modelId = "minicpm-test",
                createdAt = 1234L,
            )

            store.appendTurn(session, turn)

            val restored = store.loadRecentSession()
            requireNotNull(restored)
            assertEquals("lu_jiangxian", restored.characterId)
            assertEquals("evt-010", restored.storyCutoff)
            assertEquals("minicpm-test", restored.selectedModelId)
            assertEquals(1, restored.turns.size)
            assertEquals("docs/a.md", restored.turns.single().sources.single().source)
            assertEquals(1234L, restored.turns.single().createdAt)
            assertTrue(restored.conversationSummary.contains("不可信对话记录"))
            assertTrue(restored.conversationSummary.contains("玄谙是什么？"))
        } finally {
            tempRoot.deleteRecursively()
        }
    }

    @Test
    fun clearRecentSessionRemovesRestorableSession() {
        val tempRoot = Files.createTempDirectory("chat-session-clear-test").toFile()
        try {
            val store = ChatSessionStore(HarnessDataPaths(File(tempRoot, "harness")))
            store.create("lu_jiangxian", "evt-010", "minicpm-test")

            store.clearRecentSession()

            assertEquals(null, store.loadRecentSession())
        } finally {
            tempRoot.deleteRecursively()
        }
    }
}
