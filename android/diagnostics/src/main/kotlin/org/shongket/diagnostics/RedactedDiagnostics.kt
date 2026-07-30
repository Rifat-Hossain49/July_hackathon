package org.shongket.diagnostics

import org.shongket.core.conformance.CanonicalJson

const val MAX_DIAGNOSTIC_EVENTS: Int = 2_048
const val MAX_DIAGNOSTIC_EXPORT_BYTES: Int = 256 * 1024

enum class DiagnosticComponent {
    APPLICATION,
    STORAGE,
    TRANSPORT,
    MEDIA,
    SEMANTIC,
    SECURITY,
}

data class DiagnosticEvent(
    val tick: Long,
    val component: DiagnosticComponent,
    val code: String,
    val counter: Long,
) {
    fun validate() {
        require(tick >= 0)
        require(counter >= 0)
        require(code.matches(Regex("[A-Z][A-Z0-9_]{0,63}")))
    }
}

sealed interface ExportResult {
    data class Exported(val canonicalJson: String) : ExportResult
    data class Refused(val code: String) : ExportResult
}

class RedactedDiagnosticRecorder {
    private val events = mutableListOf<DiagnosticEvent>()

    fun record(event: DiagnosticEvent) {
        event.validate()
        require(events.size < MAX_DIAGNOSTIC_EVENTS) { "diagnostic event limit reached" }
        events += event
    }

    fun export(userInitiated: Boolean): ExportResult {
        if (!userInitiated) return ExportResult.Refused("EXPLICIT_ACTION_REQUIRED")
        val document = linkedMapOf<String, Any?>(
            "schema" to "shongket.diagnostics.v1.0",
            "events" to events.map {
                linkedMapOf(
                    "tick" to it.tick,
                    "component" to it.component.name,
                    "code" to it.code,
                    "counter" to it.counter,
                )
            },
        )
        val encoded = CanonicalJson.encode(document)
        if (encoded.toByteArray().size > MAX_DIAGNOSTIC_EXPORT_BYTES) {
            return ExportResult.Refused("RESOURCE_LIMIT")
        }
        return ExportResult.Exported(encoded)
    }
}
