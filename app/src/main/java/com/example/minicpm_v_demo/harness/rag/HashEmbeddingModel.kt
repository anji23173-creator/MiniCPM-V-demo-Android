package com.example.minicpm_v_demo.harness.rag

import java.nio.charset.StandardCharsets

class HashEmbeddingModel(
    private val dimensions: Int = 384,
    private val ngramMin: Int = 2,
    private val ngramMax: Int = 4,
) : EmbeddingModel {
    init {
        require(dimensions > 0) { "dimensions must be positive" }
        require(ngramMin > 0 && ngramMax >= ngramMin) { "invalid n-gram range" }
    }

    override fun embed(texts: List<String>): List<DoubleArray> {
        return texts.map { embedOne(it) }
    }

    fun embedOne(text: String): DoubleArray {
        val vector = DoubleArray(dimensions)
        val normalized = text.lowercase().filterNot { it.isWhitespace() }
        if (normalized.isEmpty()) return vector
        for (token in tokens(normalized)) {
            val digest = Blake2b64.digest(token.toByteArray(StandardCharsets.UTF_8))
            val bucket = (
                ((digest[0].toLong() and 0xffL) shl 24) or
                    ((digest[1].toLong() and 0xffL) shl 16) or
                    ((digest[2].toLong() and 0xffL) shl 8) or
                    (digest[3].toLong() and 0xffL)
                ).mod(dimensions)
            val sign = if ((digest[4].toInt() and 0xff) % 2 == 0) 1.0 else -1.0
            vector[bucket] += sign
        }
        return normalize(vector)
    }

    private fun tokens(text: String): List<String> {
        val output = mutableListOf<String>()
        for (size in ngramMin..ngramMax) {
            if (text.length < size) continue
            for (index in 0..(text.length - size)) {
                output += text.substring(index, index + size)
            }
        }
        return output.ifEmpty { listOf(text) }
    }
}

internal object Blake2b64 {
    private const val BlockBytes = 128
    private const val DigestBytes = 8

    private val iv = longArrayOf(
        0x6a09e667f3bcc908UL.toLong(),
        0xbb67ae8584caa73bUL.toLong(),
        0x3c6ef372fe94f82bUL.toLong(),
        0xa54ff53a5f1d36f1UL.toLong(),
        0x510e527fade682d1UL.toLong(),
        0x9b05688c2b3e6c1fUL.toLong(),
        0x1f83d9abfb41bd6bUL.toLong(),
        0x5be0cd19137e2179UL.toLong(),
    )

    private val sigma = arrayOf(
        intArrayOf(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15),
        intArrayOf(14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3),
        intArrayOf(11, 8, 12, 0, 5, 2, 15, 13, 10, 14, 3, 6, 7, 1, 9, 4),
        intArrayOf(7, 9, 3, 1, 13, 12, 11, 14, 2, 6, 5, 10, 4, 0, 15, 8),
        intArrayOf(9, 0, 5, 7, 2, 4, 10, 15, 14, 1, 11, 12, 6, 8, 3, 13),
        intArrayOf(2, 12, 6, 10, 0, 11, 8, 3, 4, 13, 7, 5, 15, 14, 1, 9),
        intArrayOf(12, 5, 1, 15, 14, 13, 4, 10, 0, 7, 6, 3, 9, 2, 8, 11),
        intArrayOf(13, 11, 7, 14, 12, 1, 3, 9, 5, 0, 15, 4, 8, 6, 2, 10),
        intArrayOf(6, 15, 14, 9, 11, 3, 0, 8, 12, 2, 13, 7, 1, 4, 10, 5),
        intArrayOf(10, 2, 8, 4, 7, 6, 1, 5, 15, 11, 9, 14, 3, 12, 13, 0),
        intArrayOf(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15),
        intArrayOf(14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3),
    )

    fun digest(input: ByteArray): ByteArray {
        val h = iv.copyOf()
        h[0] = h[0] xor 0x01010000L xor DigestBytes.toLong()
        var offset = 0
        var bytesCompressed = 0L
        while (input.size - offset > BlockBytes) {
            compress(h, input.copyOfRange(offset, offset + BlockBytes), bytesCompressed + BlockBytes, false)
            bytesCompressed += BlockBytes
            offset += BlockBytes
        }
        val block = ByteArray(BlockBytes)
        val remaining = input.size - offset
        input.copyInto(block, 0, offset, input.size)
        compress(h, block, bytesCompressed + remaining, true)
        return longToLittleEndian(h[0])
    }

    private fun compress(h: LongArray, block: ByteArray, counter: Long, last: Boolean) {
        val m = LongArray(16)
        for (index in 0 until 16) {
            m[index] = littleEndianToLong(block, index * 8)
        }
        val v = LongArray(16)
        for (index in 0 until 8) {
            v[index] = h[index]
            v[index + 8] = iv[index]
        }
        v[12] = v[12] xor counter
        if (last) v[14] = v[14].inv()

        for (round in 0 until 12) {
            val s = sigma[round]
            g(v, 0, 4, 8, 12, m[s[0]], m[s[1]])
            g(v, 1, 5, 9, 13, m[s[2]], m[s[3]])
            g(v, 2, 6, 10, 14, m[s[4]], m[s[5]])
            g(v, 3, 7, 11, 15, m[s[6]], m[s[7]])
            g(v, 0, 5, 10, 15, m[s[8]], m[s[9]])
            g(v, 1, 6, 11, 12, m[s[10]], m[s[11]])
            g(v, 2, 7, 8, 13, m[s[12]], m[s[13]])
            g(v, 3, 4, 9, 14, m[s[14]], m[s[15]])
        }
        for (index in 0 until 8) {
            h[index] = h[index] xor v[index] xor v[index + 8]
        }
    }

    private fun g(v: LongArray, a: Int, b: Int, c: Int, d: Int, x: Long, y: Long) {
        v[a] = v[a] + v[b] + x
        v[d] = java.lang.Long.rotateRight(v[d] xor v[a], 32)
        v[c] += v[d]
        v[b] = java.lang.Long.rotateRight(v[b] xor v[c], 24)
        v[a] = v[a] + v[b] + y
        v[d] = java.lang.Long.rotateRight(v[d] xor v[a], 16)
        v[c] += v[d]
        v[b] = java.lang.Long.rotateRight(v[b] xor v[c], 63)
    }

    private fun littleEndianToLong(bytes: ByteArray, offset: Int): Long {
        var value = 0L
        for (index in 0 until 8) {
            value = value or ((bytes[offset + index].toLong() and 0xffL) shl (8 * index))
        }
        return value
    }

    private fun longToLittleEndian(value: Long): ByteArray {
        val output = ByteArray(DigestBytes)
        for (index in 0 until DigestBytes) {
            output[index] = ((value ushr (8 * index)) and 0xff).toByte()
        }
        return output
    }
}
