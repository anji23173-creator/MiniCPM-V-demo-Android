package com.example.minicpm_v_demo.harness.rag

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class HashEmbeddingModelTest {
    @Test
    fun blake2b64MatchesPythonDigestSizeEight() {
        val cases = mapOf(
            "玄谙" to "5124d346423e7ba3",
            "元府" to "1a42fe5b1f583509",
            "world" to "5831c37fa7d6930f",
            "忘掉" to "02531412d8173d9f",
        )

        for ((text, expectedHex) in cases) {
            assertEquals(expectedHex, Blake2b64.digest(text.toByteArray(Charsets.UTF_8)).toHex())
        }
    }

    @Test
    fun emptyTextReturnsZeroVector() {
        val vector = HashEmbeddingModel().embedOne("   \n")

        assertEquals(384, vector.size)
        assertArrayEquals(DoubleArray(384), vector, 0.0)
    }

    private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it.toInt() and 0xff) }
}

