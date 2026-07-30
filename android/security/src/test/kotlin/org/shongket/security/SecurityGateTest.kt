package org.shongket.security

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SecurityGateTest {
    @Test
    fun malformedAndOversizedInputsAreRefusedWithoutState() {
        val cases = listOf(
            byteArrayOf(),
            byteArrayOf(0xc3.toByte(), 0x28),
            """{"schema":""".toByteArray(),
            ("[".repeat(40) + "0" + "]".repeat(40)).toByteArray(),
            """{"schema":"shongket.application.v1.0","schema":"duplicate"}""".toByteArray(),
        )
        cases.forEach {
            assertTrue(ApplicationInputGate.decode(it) is InputGateResult.Refused)
        }
        assertEquals(
            InputGateResult.Refused("PAYLOAD_TOO_LARGE"),
            ApplicationInputGate.decode(ByteArray(MAX_APPLICATION_PAYLOAD_BYTES + 1)),
        )
    }

    @Test
    fun unknownVersionsNeverDowngrade() {
        listOf(0 to 9, 1 to 1, 2 to 0).forEach { (major, minor) ->
            assertEquals("VERSION_UNSUPPORTED", VersionGate.refusalCode(major, minor))
        }
        assertEquals(null, VersionGate.refusalCode(1, 0))
    }

    @Test
    fun alteredUnknownAndImpersonatedMetadataAreRejected() {
        val identity = InjectedDevelopmentIdentity(mapOf("known" to ByteArray(32) { 7 }))
        val payload = "canonical".toByteArray()
        val signature = identity.sign("known", payload)
        assertEquals(
            "SIGNATURE_INVALID",
            SignedMetadataGate.verify(identity, "known", "unknown", payload, signature),
        )
        assertEquals(
            "SIGNATURE_INVALID",
            SignedMetadataGate.verify(identity, "known", "known", "altered".toByteArray(), signature),
        )
        assertEquals(null, SignedMetadataGate.verify(identity, "known", "known", payload, signature))
    }

    @Test
    fun privateForwardRequiresUnselectedConsentAndCompatiblePeer() {
        assertEquals(
            ConsentDecision.Refused("CONSENT_REQUIRED"),
            PrivateForwardConsentGate.evaluate(true, false, true),
        )
        assertEquals(
            ConsentDecision.Refused("PEER_PUBLIC_ONLY"),
            PrivateForwardConsentGate.evaluate(true, true, false),
        )
        assertEquals(
            ConsentDecision.Allowed,
            PrivateForwardConsentGate.evaluate(true, true, true),
        )
    }

    @Test
    fun replayAndDuplicatesDoNotGrowStorage() {
        val guard = ReplayGuard()
        val objectId = "a".repeat(64)
        assertEquals(ReplayDecision.Accepted, guard.evaluate("0".repeat(16), objectId, 20, 10))
        assertEquals(
            ReplayDecision.Refused("DUPLICATE"),
            guard.evaluate("0".repeat(16), objectId, 20, 10),
        )
        assertEquals(1, guard.storedEntries())
        assertEquals(
            ReplayDecision.Refused("EXPIRED"),
            guard.evaluate("0".repeat(16), "b".repeat(64), 9, 10),
        )
        assertEquals(1, guard.storedEntries())
    }
}
