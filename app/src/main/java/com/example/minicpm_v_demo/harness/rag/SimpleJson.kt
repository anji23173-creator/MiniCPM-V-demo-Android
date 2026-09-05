package com.example.minicpm_v_demo.harness.rag

class JsonParseException(message: String) : IllegalArgumentException(message)

class SimpleJsonParser(private val input: String) {
    private var index = 0

    fun parse(): Any? {
        val value = parseValue()
        skipWhitespace()
        if (index != input.length) {
            error("Unexpected trailing content")
        }
        return value
    }

    private fun parseValue(): Any? {
        skipWhitespace()
        if (index >= input.length) error("Unexpected end of JSON")
        return when (input[index]) {
            '{' -> parseObject()
            '[' -> parseArray()
            '"' -> parseString()
            't' -> parseLiteral("true", true)
            'f' -> parseLiteral("false", false)
            'n' -> parseLiteral("null", null)
            '-', in '0'..'9' -> parseNumber()
            else -> error("Unexpected character '${input[index]}'")
        }
    }

    private fun parseObject(): Map<String, Any?> {
        expect('{')
        skipWhitespace()
        val values = linkedMapOf<String, Any?>()
        if (peek('}')) {
            expect('}')
            return values
        }
        while (true) {
            skipWhitespace()
            val key = parseString()
            skipWhitespace()
            expect(':')
            values[key] = parseValue()
            skipWhitespace()
            when {
                peek(',') -> {
                    expect(',')
                }
                peek('}') -> {
                    expect('}')
                    return values
                }
                else -> error("Expected ',' or '}'")
            }
        }
    }

    private fun parseArray(): List<Any?> {
        expect('[')
        skipWhitespace()
        val values = mutableListOf<Any?>()
        if (peek(']')) {
            expect(']')
            return values
        }
        while (true) {
            values += parseValue()
            skipWhitespace()
            when {
                peek(',') -> {
                    expect(',')
                }
                peek(']') -> {
                    expect(']')
                    return values
                }
                else -> error("Expected ',' or ']'")
            }
        }
    }

    private fun parseString(): String {
        expect('"')
        val output = StringBuilder()
        while (index < input.length) {
            val char = input[index++]
            when (char) {
                '"' -> return output.toString()
                '\\' -> output.append(parseEscape())
                else -> output.append(char)
            }
        }
        error("Unclosed string")
    }

    private fun parseEscape(): Char {
        if (index >= input.length) error("Unclosed escape")
        return when (val char = input[index++]) {
            '"', '\\', '/' -> char
            'b' -> '\b'
            'f' -> '\u000C'
            'n' -> '\n'
            'r' -> '\r'
            't' -> '\t'
            'u' -> {
                if (index + 4 > input.length) error("Invalid unicode escape")
                val hex = input.substring(index, index + 4)
                index += 4
                hex.toInt(16).toChar()
            }
            else -> error("Invalid escape: \\$char")
        }
    }

    private fun parseNumber(): Double {
        val start = index
        if (peek('-')) index += 1
        while (index < input.length && input[index].isDigit()) index += 1
        if (peek('.')) {
            index += 1
            while (index < input.length && input[index].isDigit()) index += 1
        }
        if (index < input.length && (input[index] == 'e' || input[index] == 'E')) {
            index += 1
            if (index < input.length && (input[index] == '+' || input[index] == '-')) index += 1
            while (index < input.length && input[index].isDigit()) index += 1
        }
        return input.substring(start, index).toDouble()
    }

    private fun parseLiteral(literal: String, value: Any?): Any? {
        if (!input.startsWith(literal, index)) error("Expected $literal")
        index += literal.length
        return value
    }

    private fun skipWhitespace() {
        while (index < input.length && input[index].isWhitespace()) index += 1
    }

    private fun expect(char: Char) {
        if (index >= input.length || input[index] != char) error("Expected '$char'")
        index += 1
    }

    private fun peek(char: Char): Boolean = index < input.length && input[index] == char

    private fun error(message: String): Nothing {
        throw JsonParseException("$message at offset $index")
    }
}

@Suppress("UNCHECKED_CAST")
fun Any?.asJsonObject(label: String): Map<String, Any?> {
    return this as? Map<String, Any?> ?: throw JsonParseException("$label must be an object")
}

@Suppress("UNCHECKED_CAST")
fun Any?.asJsonArray(label: String): List<Any?> {
    return this as? List<Any?> ?: throw JsonParseException("$label must be an array")
}

fun Map<String, Any?>.stringValue(key: String): String {
    return this[key] as? String ?: throw JsonParseException("Missing string key: $key")
}

fun Map<String, Any?>.intValue(key: String): Int {
    return when (val value = this[key]) {
        is Double -> value.toInt()
        is Int -> value
        else -> throw JsonParseException("Missing integer key: $key")
    }
}

fun Map<String, Any?>.doubleListValue(key: String): List<Double> {
    return this[key].asJsonArray(key).map {
        it as? Double ?: throw JsonParseException("$key must contain only numbers")
    }
}
