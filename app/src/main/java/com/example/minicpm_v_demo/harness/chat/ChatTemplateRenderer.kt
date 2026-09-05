package com.example.minicpm_v_demo.harness.chat

import com.example.minicpm_v_demo.harness.HarnessModelFamily
import com.example.minicpm_v_demo.harness.character.HarnessChatMessage

data class SplitPrompt(
    val systemPrompt: String,
    val userPrompt: String,
)

data class RenderedChatPrompt(
    val messages: List<HarnessChatMessage>,
    val renderedSinglePrompt: String,
    val splitPrompt: SplitPrompt,
    val profile: String,
)

class ChatTemplateRenderer(
    private val profile: String = "android_send_user_prompt_v1",
) {
    fun render(messages: List<HarnessChatMessage>): RenderedChatPrompt {
        require(messages.size == 2) { "Android renderer expects exactly system and user messages" }
        require(messages[0].role == "system" && messages[1].role == "user") {
            "messages must be ordered as system, user"
        }
        val system = messages[0].content
        val user = messages[1].content
        require(system.isNotBlank() && user.isNotBlank()) { "message content must be non-empty" }
        return RenderedChatPrompt(
            messages = messages,
            renderedSinglePrompt = renderSingle(system, user),
            splitPrompt = SplitPrompt(system, user),
            profile = profile,
        )
    }

    private fun renderSingle(system: String, user: String): String {
        return when (profile) {
            "llama" -> "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n" +
                "$system<|eot_id|><|start_header_id|>user<|end_header_id|>\n" +
                "$user<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
            "qwen" -> "<|im_start|>system\n$system<|im_end|>\n" +
                "<|im_start|>user\n$user<|im_end|>\n" +
                "<|im_start|>assistant\n"
            else -> "<|system|>\n$system\n\n<|user|>\n$user\n\n<|assistant|>\n"
        }
    }

    companion object {
        fun forModelFamily(family: HarnessModelFamily): ChatTemplateRenderer {
            val profile = when (family) {
                HarnessModelFamily.LLAMA -> "llama"
                HarnessModelFamily.QWEN -> "qwen"
                HarnessModelFamily.MINICPM_TEXT -> "minicpm_text"
                HarnessModelFamily.MINICPM_VISION -> "minicpm_vision"
                else -> "android_send_user_prompt_v1"
            }
            return ChatTemplateRenderer(profile)
        }
    }
}

