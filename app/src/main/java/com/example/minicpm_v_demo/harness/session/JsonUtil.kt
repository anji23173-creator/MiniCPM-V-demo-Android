package com.example.minicpm_v_demo.harness.session

internal fun jsonObject(values: Map<String, Any?>): String {
    return values.entries.joinToString(prefix = "{", postfix = "}") { (key, value) ->
        "${jsonString(key)}:${jsonValue(value)}"
    }
}

internal fun jsonArray(values: List<Any?>): String {
    return values.joinToString(prefix = "[", postfix = "]") { jsonValue(it) }
}

internal fun jsonValue(value: Any?): String {
    return when (value) {
        null -> "null"
        is String -> jsonString(value)
        is Number -> value.toString()
        is Boolean -> value.toString()
        is Map<*, *> -> jsonObject(value.entries.associate { it.key.toString() to it.value })
        is List<*> -> jsonArray(value)
        else -> jsonString(value.toString())
    }
}

internal fun jsonString(value: String): String {
    val output = StringBuilder(value.length + 8)
    output.append('"')
    for (char in value) {
        when (char) {
            '"' -> output.append("\\\"")
            '\\' -> output.append("\\\\")
            '\b' -> output.append("\\b")
            '\u000C' -> output.append("\\f")
            '\n' -> output.append("\\n")
            '\r' -> output.append("\\r")
            '\t' -> output.append("\\t")
            else -> {
                if (char.code < 0x20) {
                    output.append("\\u")
                    output.append(char.code.toString(16).padStart(4, '0'))
                } else {
                    output.append(char)
                }
            }
        }
    }
    output.append('"')
    return output.toString()
}

internal fun Map<String, Any?>.optionalString(key: String): String? = this[key] as? String

internal fun Map<String, Any?>.optionalLong(key: String): Long? {
    return when (val value = this[key]) {
        is Double -> value.toLong()
        is Int -> value.toLong()
        is Long -> value
        else -> null
    }
}

internal fun Map<String, Any?>.optionalDouble(key: String): Double? {
    return when (val value = this[key]) {
        is Double -> value
        is Int -> value.toDouble()
        is Long -> value.toDouble()
        else -> null
    }
}

internal fun Map<String, Any?>.optionalStringList(key: String): List<String> {
    return (this[key] as? List<*>).orEmpty().mapNotNull { it as? String }
}
