package com.example.minicpm_v_demo.harness.rag

interface EmbeddingModel {
    fun embed(texts: List<String>): List<DoubleArray>
}

fun cosine(left: DoubleArray, right: DoubleArray): Double {
    val size = minOf(left.size, right.size)
    var sum = 0.0
    for (index in 0 until size) {
        sum += left[index] * right[index]
    }
    return sum
}

fun normalize(vector: DoubleArray): DoubleArray {
    var squared = 0.0
    for (value in vector) {
        squared += value * value
    }
    if (squared == 0.0) return vector
    val norm = kotlin.math.sqrt(squared)
    for (index in vector.indices) {
        vector[index] = vector[index] / norm
    }
    return vector
}

