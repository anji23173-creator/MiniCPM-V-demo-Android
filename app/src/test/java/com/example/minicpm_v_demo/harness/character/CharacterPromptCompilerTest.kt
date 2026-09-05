package com.example.minicpm_v_demo.harness.character

import com.example.minicpm_v_demo.harness.data.HarnessDataPaths
import com.example.minicpm_v_demo.harness.data.harnessAssetsDir
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class CharacterPromptCompilerTest {
    @Test
    fun loaderReadsSixCharactersAndTwentyEightEvents() {
        val loader = testLoader()

        val characters = File(harnessAssetsDir(), "characters/characters")
            .listFiles { file -> file.extension == "json" }
            .orEmpty()
            .map { loader.loadCharacter(it.nameWithoutExtension) }

        assertEquals(6, characters.size)
        assertEquals(28, loader.loadEvents().size)
        assertTrue(characters.any { it.npcId == "lu_jiangxian" })
        assertTrue(characters.any { it.npcId == "bai_junyi" })
    }

    @Test
    fun compilerBuildsSystemAndUserMessages() {
        val compiled = testCompiler().buildNpcPrompt(
            npcId = "lu_jiangxian",
            userInput = "玄谙究竟是什么？",
            runtimeContext = RuntimeContext(storyCutoff = "evt-010"),
        )

        assertEquals("system", compiled.messages[0].role)
        assertEquals("user", compiled.messages[1].role)
        assertEquals("玄谙究竟是什么？", compiled.messages[1].content)
        assertTrue(compiled.messages[0].content.contains("你就是陆江仙"))
        assertTrue(compiled.messages[0].content.contains("此前对话只用于理解代词或明确承接"))
        assertTrue(compiled.messages[0].content.contains("玄谙"))
        assertTrue(compiled.messages[0].content.length <= compiled.debug.maxChars)
        assertFalse(compiled.debug.budgetExceededByMandatory)
        assertEquals("lu_jiangxian", compiled.debug.npcId)
        assertEquals("evt-010", compiled.debug.storyCutoff)
    }

    @Test
    fun compilerKeepsFutureEventsOutOfEarlierCutoff() {
        val compiled = testCompiler().buildNpcPrompt(
            npcId = "lu_jiangxian",
            userInput = "玄谙最后会消散吗？",
            runtimeContext = RuntimeContext(storyCutoff = "evt-010"),
        )

        assertFalse(compiled.messages[0].content.contains("自行消散"))
        assertTrue(compiled.debug.retrievalDecisions.any { !it.allowed && it.reason == "future_event" })
    }

    @Test
    fun compilerRejectsMetaQuestionsFromStoryFacts() {
        val compiled = testCompiler().buildNpcPrompt(
            npcId = "xuan_an",
            userInput = "作者为什么这样写这个角色？",
            runtimeContext = RuntimeContext(storyCutoff = "evt-018"),
        )

        assertTrue(compiled.messages[0].content.contains("无；不得自行补全"))
        assertTrue(compiled.debug.retrievalDecisions.all { !it.allowed && it.reason == "meta_or_author_topic" })
    }

    @Test
    fun compactPromptLeavesRoomForRelevantYuanfuStoryFact() {
        val compiled = testCompiler().buildNpcPrompt(
            npcId = "lu_jiangxian",
            userInput = "当年的元府是如何建立的？主要成员有哪些？",
            runtimeContext = RuntimeContext(storyCutoff = "evt-010", maxChars = 900),
        )

        assertTrue(compiled.messages[0].content.length <= 900)
        assertFalse(compiled.debug.budgetExceededByMandatory)
        assertTrue(compiled.debug.selectedItems.any { it.id == "evt-004" })
        assertTrue(compiled.messages[0].content.contains("元府三司"))
    }

    @Test
    fun compactPromptExplicitlyForbidsStructuredOrCardLikeOutput() {
        val compiled = testCompiler().buildNpcPrompt(
            npcId = "lu_jiangxian",
            userInput = "你是谁",
            runtimeContext = RuntimeContext(storyCutoff = "evt-010", maxChars = 900),
        )

        val system = compiled.messages[0].content
        assertTrue(system.contains("只说角色此刻会亲口说的话"))
        assertTrue(system.contains("通常一至三句、少于120字"))
        assertTrue(system.contains("不要旁白、分析、标题、列表、资料摘要"))
        assertTrue(system.contains("任何尖括号标签"))
        assertTrue(system.contains("把这些短句当作语气标尺"))
        assertTrue(system.length <= 900)
    }

    @Test
    fun properNounQuestionsRecallTheSpecificStoryEvent() {
        val retriever = KeywordStoryRetriever()
        val events = testLoader().loadEvents()
        val cases = listOf(
            "玄谙究竟是什么？" to "evt-009",
            "道皓清阳玄玉真君做过什么？" to "evt-025",
            "薜荔剑和李江群有什么关系？" to "evt-028",
            "太虚元序玄司营造法进展如何？" to "evt-021",
        )

        cases.forEach { (query, expectedEventId) ->
            val results = retriever.retrieve(query, events, limit = 5)
            assertTrue("$query did not recall $expectedEventId", results.any { it.event.eventId == expectedEventId })
            assertEquals("$query ranked the wrong event first", expectedEventId, results.first().event.eventId)
        }
    }

    @Test
    fun definitionQuestionPrioritizesAnUnambiguousKnownFact() {
        val compiled = testCompiler().buildNpcPrompt(
            npcId = "lu_jiangxian",
            userInput = "玄谙究竟是什么？",
            runtimeContext = RuntimeContext(storyCutoff = "evt-010", maxChars = 900),
        )

        val system = compiled.messages[0].content
        assertEquals("evt-009", compiled.debug.selectedItems.first().id)
        assertTrue(system.contains("你听人提及：青诣元心仪是玄鉴的鉴身权柄"))
        assertTrue(system.contains("玄谙是洞华天中一块青铜残片"))
        assertFalse(system.contains("自己是洞华天"))
    }

    @Test
    fun promptKeepsRulesOutOfIdentityAndFocusesTheLatestQuestion() {
        val compiled = testCompiler().buildNpcPrompt(
            npcId = "lu_jiangxian",
            userInput = "玄明之气到底有什么用途？",
            runtimeContext = RuntimeContext(
                storyCutoff = "evt-010",
                maxChars = 900,
                conversationSummary = "玩家上一轮问过元府三司。",
            ),
        )

        val system = compiled.messages[0].content
        assertFalse(system.contains("你绝不会自称别人"))
        assertTrue(system.contains("只回答玩家最后这一问"))
        assertTrue(system.contains("不补答上一轮"))
        assertTrue(system.contains("此事我尚不清楚"))
        assertTrue(system.contains("不要追加索要依据"))
    }

    @Test
    fun everyBundledCharacterFitsTheAndroidPromptBudget() {
        val compiler = testCompiler()

        compiler.availableCharacters().forEach { character ->
            val compiled = compiler.buildNpcPrompt(
                npcId = character.npcId,
                userInput = "你是谁",
                runtimeContext = RuntimeContext(
                    storyCutoff = character.knowledgeScope.storyCutoff,
                    maxChars = 900,
                ),
            )

            assertTrue(
                "${character.npcId} prompt was ${compiled.messages[0].content.length} chars",
                compiled.messages[0].content.length <= 900,
            )
            assertFalse(compiled.debug.budgetExceededByMandatory)
        }
    }

    @Test
    fun compilerReportsUnknownNpcAndCutoff() {
        val compiler = testCompiler()

        assertTrue(runCatching {
            compiler.buildNpcPrompt("missing", "你好")
        }.exceptionOrNull() is IllegalArgumentException)
        assertTrue(runCatching {
            compiler.buildNpcPrompt("lu_jiangxian", "你好", RuntimeContext(storyCutoff = "evt-999"))
        }.exceptionOrNull() is IllegalArgumentException)
    }

    private fun testCompiler(): CharacterPromptCompiler = CharacterPromptCompiler(testLoader())

    private fun testLoader(): CharacterJsonLoader {
        val root = harnessAssetsDir()
        return CharacterJsonLoader(
            charactersDir = File(root, "characters/characters"),
            storyEventsFile = File(root, "characters/story/story_events.jsonl"),
            promptTemplateFile = File(root, "characters/prompts/roleplay_system.prompt"),
        )
    }
}
