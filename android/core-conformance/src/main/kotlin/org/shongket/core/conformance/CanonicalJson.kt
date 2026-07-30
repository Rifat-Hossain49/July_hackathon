package org.shongket.core.conformance

import java.nio.charset.StandardCharsets
import java.security.MessageDigest

/**
 * Language-neutral Shongket canonical JSON.
 *
 * The encoder deliberately accepts only null, booleans, integral numbers,
 * strings, lists and string-keyed maps. Maps are ordered by Unicode code
 * point, all non-ASCII UTF-16 code units are escaped with lower-case hex,
 * and no insignificant whitespace is emitted.
 */
object CanonicalJson {
    fun parse(text: String): Any? = Parser(text).parse()

    fun encode(value: Any?): String = buildString {
        appendCanonical(value)
    }

    fun encodeToBytes(value: Any?): ByteArray =
        encode(value).toByteArray(StandardCharsets.UTF_8)

    fun sha256Hex(value: Any?): String = sha256Hex(encodeToBytes(value))

    fun sha256Hex(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256")
            .digest(bytes)
            .joinToString(separator = "") { byte -> "%02x".format(byte.toInt() and 0xff) }

    private fun StringBuilder.appendCanonical(value: Any?) {
        when (value) {
            null -> append("null")
            is Boolean -> append(if (value) "true" else "false")
            is Byte, is Short, is Int, is Long -> append(value.toString())
            is Float, is Double -> throw IllegalArgumentException("floats are not canonical")
            is String -> appendString(value)
            is List<*> -> {
                append('[')
                value.forEachIndexed { index, item ->
                    if (index > 0) append(',')
                    appendCanonical(item)
                }
                append(']')
            }
            is Map<*, *> -> appendMap(value)
            else -> throw IllegalArgumentException(
                "unsupported canonical JSON type: ${value::class.qualifiedName}",
            )
        }
    }

    private fun StringBuilder.appendMap(value: Map<*, *>) {
        val entries = value.entries.map { entry ->
            val key = entry.key as? String
                ?: throw IllegalArgumentException("canonical JSON object keys must be strings")
            key to entry.value
        }.sortedWith { left, right -> compareCodePoints(left.first, right.first) }

        append('{')
        entries.forEachIndexed { index, (key, item) ->
            if (index > 0) append(',')
            appendString(key)
            append(':')
            appendCanonical(item)
        }
        append('}')
    }

    private fun StringBuilder.appendString(value: String) {
        append('"')
        value.forEach { char ->
            when (char) {
                '"' -> append("\\\"")
                '\\' -> append("\\\\")
                '\b' -> append("\\b")
                '\u000c' -> append("\\f")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                else -> {
                    if (char.code in 0x20..0x7e) {
                        append(char)
                    } else {
                        append("\\u")
                        append(char.code.toString(16).padStart(4, '0'))
                    }
                }
            }
        }
        append('"')
    }

    private fun compareCodePoints(left: String, right: String): Int {
        var leftIndex = 0
        var rightIndex = 0
        while (leftIndex < left.length && rightIndex < right.length) {
            val leftPoint = left.codePointAt(leftIndex)
            val rightPoint = right.codePointAt(rightIndex)
            if (leftPoint != rightPoint) {
                return leftPoint.compareTo(rightPoint)
            }
            leftIndex += Character.charCount(leftPoint)
            rightIndex += Character.charCount(rightPoint)
        }
        return (left.length - leftIndex).compareTo(right.length - rightIndex)
    }

    private class Parser(private val source: String) {
        private var index = 0

        fun parse(): Any? {
            skipWhitespace()
            val value = parseValue()
            skipWhitespace()
            require(index == source.length) { "trailing JSON data at index $index" }
            return value
        }

        private fun parseValue(): Any? {
            require(index < source.length) { "unexpected end of JSON" }
            return when (source[index]) {
                '{' -> parseObject()
                '[' -> parseArray()
                '"' -> parseString()
                't' -> parseLiteral("true", true)
                'f' -> parseLiteral("false", false)
                'n' -> parseLiteral("null", null)
                '-', in '0'..'9' -> parseInteger()
                else -> throw IllegalArgumentException("invalid JSON value at index $index")
            }
        }

        private fun parseObject(): Map<String, Any?> {
            index++
            skipWhitespace()
            val result = linkedMapOf<String, Any?>()
            if (consume('}')) return result

            while (true) {
                require(peek() == '"') { "object key must be a string at index $index" }
                val key = parseString()
                require(!result.containsKey(key)) { "duplicate object key: $key" }
                skipWhitespace()
                require(consume(':')) { "missing ':' after object key at index $index" }
                skipWhitespace()
                result[key] = parseValue()
                skipWhitespace()
                if (consume('}')) return result
                require(consume(',')) { "missing ',' in object at index $index" }
                skipWhitespace()
            }
        }

        private fun parseArray(): List<Any?> {
            index++
            skipWhitespace()
            val result = mutableListOf<Any?>()
            if (consume(']')) return result

            while (true) {
                result += parseValue()
                skipWhitespace()
                if (consume(']')) return result
                require(consume(',')) { "missing ',' in array at index $index" }
                skipWhitespace()
            }
        }

        private fun parseString(): String {
            require(consume('"')) { "missing string quote at index $index" }
            return buildString {
                while (true) {
                    require(index < source.length) { "unterminated JSON string" }
                    val char = source[index++]
                    when {
                        char == '"' -> return@buildString
                        char == '\\' -> append(parseEscape())
                        char.code < 0x20 -> throw IllegalArgumentException(
                            "unescaped control character at index ${index - 1}",
                        )
                        else -> append(char)
                    }
                }
            }
        }

        private fun parseEscape(): Char {
            require(index < source.length) { "unterminated JSON escape" }
            return when (val escaped = source[index++]) {
                '"' -> '"'
                '\\' -> '\\'
                '/' -> '/'
                'b' -> '\b'
                'f' -> '\u000c'
                'n' -> '\n'
                'r' -> '\r'
                't' -> '\t'
                'u' -> {
                    require(index + 4 <= source.length) { "short Unicode escape" }
                    val hex = source.substring(index, index + 4)
                    require(hex.all { it.isDigit() || it.lowercaseChar() in 'a'..'f' }) {
                        "invalid Unicode escape at index $index"
                    }
                    index += 4
                    hex.toInt(16).toChar()
                }
                else -> throw IllegalArgumentException("invalid JSON escape: \\$escaped")
            }
        }

        private fun parseInteger(): Long {
            val start = index
            consume('-')
            require(index < source.length) { "missing integer digits" }
            if (consume('0')) {
                require(index == source.length || source[index] !in '0'..'9') {
                    "leading zero in integer at index $start"
                }
            } else {
                require(source[index] in '1'..'9') { "invalid integer at index $start" }
                while (index < source.length && source[index] in '0'..'9') index++
            }
            require(index == source.length || source[index] !in charArrayOf('.', 'e', 'E')) {
                "floats are not canonical"
            }
            return source.substring(start, index).toLongOrNull()
                ?: throw IllegalArgumentException("integer is outside signed 64-bit range")
        }

        private fun <T> parseLiteral(literal: String, value: T): T {
            require(source.startsWith(literal, index)) { "invalid literal at index $index" }
            index += literal.length
            return value
        }

        private fun skipWhitespace() {
            while (index < source.length && source[index] in charArrayOf(' ', '\t', '\r', '\n')) {
                index++
            }
        }

        private fun peek(): Char? = source.getOrNull(index)

        private fun consume(expected: Char): Boolean {
            if (peek() != expected) return false
            index++
            return true
        }
    }
}
