package org.shongket.security

import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.nio.charset.StandardCharsets
import org.shongket.core.conformance.CanonicalJson

const val MAX_APPLICATION_PAYLOAD_BYTES: Int = 1_048_576

sealed interface InputGateResult {
    data class Accepted(val document: Map<String, Any?>) : InputGateResult
    data class Refused(val code: String) : InputGateResult
}

object ApplicationInputGate {
    fun decode(payload: ByteArray): InputGateResult {
        if (payload.isEmpty()) return InputGateResult.Refused("MALFORMED_PAYLOAD")
        if (payload.size > MAX_APPLICATION_PAYLOAD_BYTES) {
            return InputGateResult.Refused("PAYLOAD_TOO_LARGE")
        }
        val text = try {
            StandardCharsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(payload))
                .toString()
        } catch (_: Exception) {
            return InputGateResult.Refused("MALFORMED_PAYLOAD")
        }
        val decoded = try {
            CanonicalJson.parse(
                text,
                maxDepth = 32,
                maxCharacters = MAX_APPLICATION_PAYLOAD_BYTES,
            )
        } catch (_: IllegalArgumentException) {
            return InputGateResult.Refused("MALFORMED_PAYLOAD")
        }
        val document = decoded as? Map<*, *>
            ?: return InputGateResult.Refused("MALFORMED_PAYLOAD")
        if (document.keys.any { it !is String }) {
            return InputGateResult.Refused("MALFORMED_PAYLOAD")
        }
        @Suppress("UNCHECKED_CAST")
        val typed = document as Map<String, Any?>
        if (typed["schema"] != "shongket.application.v1.0") {
            return InputGateResult.Refused("VERSION_UNSUPPORTED")
        }
        return InputGateResult.Accepted(typed)
    }
}

object VersionGate {
    fun accepts(major: Int, minor: Int): Boolean = major == 1 && minor == 0

    fun refusalCode(major: Int, minor: Int): String? =
        if (accepts(major, minor)) null else "VERSION_UNSUPPORTED"
}
