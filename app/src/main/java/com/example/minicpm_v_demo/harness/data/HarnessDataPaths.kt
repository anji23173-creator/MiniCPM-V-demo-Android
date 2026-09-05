package com.example.minicpm_v_demo.harness.data

import android.content.Context
import java.io.File

data class HarnessDataPaths(val rootDir: File) {
    val manifestFile: File get() = File(rootDir, "manifest.json")
    val ragDir: File get() = File(rootDir, "rag")
    val ragIndexFile: File get() = File(ragDir, "index.json")
    val charactersRootDir: File get() = File(rootDir, "characters")
    val charactersDir: File get() = File(charactersRootDir, "characters")
    val storyEventsFile: File get() = File(charactersRootDir, "story/story_events.jsonl")
    val promptsDir: File get() = File(charactersRootDir, "prompts")
    val sessionsDir: File get() = File(rootDir, "sessions")
    val memoryDir: File get() = File(rootDir, "memory")
    val settingsDir: File get() = File(rootDir, "settings")

    fun ensureRuntimeDirs() {
        listOf(rootDir, sessionsDir, memoryDir, settingsDir).forEach { directory ->
            check(directory.isDirectory || directory.mkdirs()) {
                "Failed to create Harness directory: ${directory.absolutePath}"
            }
        }
    }

    companion object {
        fun from(context: Context): HarnessDataPaths =
            HarnessDataPaths(File(context.filesDir, "harness"))
    }
}

fun harnessAssetsDir(): File {
    val candidates = listOf(
        File("app/src/main/assets/harness"),
        File("src/main/assets/harness"),
    )
    return candidates.firstOrNull { it.isDirectory }
        ?: error("Cannot locate test harness assets directory")
}
