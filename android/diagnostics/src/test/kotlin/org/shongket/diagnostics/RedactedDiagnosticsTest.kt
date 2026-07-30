package org.shongket.diagnostics

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RedactedDiagnosticsTest {
    @Test
    fun exportRequiresExplicitActionAndContainsOnlyAllowedFields() {
        val recorder = RedactedDiagnosticRecorder()
        recorder.record(DiagnosticEvent(7, DiagnosticComponent.TRANSPORT, "INTERRUPTED", 2))
        assertEquals(
            ExportResult.Refused("EXPLICIT_ACTION_REQUIRED"),
            recorder.export(userInitiated = false),
        )
        val document = (recorder.export(userInitiated = true) as ExportResult.Exported).canonicalJson
        assertTrue(document.contains("\"tick\":7"))
        assertTrue(document.contains("\"code\":\"INTERRUPTED\""))
        listOf("capsule", "location", "peer_id", "media_bytes", "key_material").forEach {
            assertFalse(document.lowercase().contains(it))
        }
    }

    @Test(expected = IllegalArgumentException::class)
    fun freeFormSensitiveTextCannotEnterCodeField() {
        RedactedDiagnosticRecorder().record(
            DiagnosticEvent(0, DiagnosticComponent.APPLICATION, "location: home", 0),
        )
    }
}
