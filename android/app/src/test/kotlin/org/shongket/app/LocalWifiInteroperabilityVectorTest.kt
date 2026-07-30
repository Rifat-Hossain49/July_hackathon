package org.shongket.app

import org.junit.Assert.assertEquals
import org.junit.Test

class LocalWifiInteroperabilityVectorTest {
    @Test
    fun swiftAndAndroidCapsuleVectorIsByteExact() {
        val vector = vectorText()
        val frame = LocalWifiCapsuleCodec.encode(
            LocalWifiCapsule(
                senderLabel = "Shongket-A1B2",
                message = "নদীর পাশের গ্রামে পানি প্রয়োজন",
                location = "পুরনো সেতুর পূর্ব পাড়",
                urgency = LocalWifiUrgency.CRITICAL,
                visibility = LocalWifiVisibility.PUBLIC,
                humanConfirmed = true,
                forwardingConsent = false,
                createdAtEpochSeconds = 1_800_000_000,
                expiresAtEpochSeconds = 1_800_086_400,
            ),
        )
        val decoded = LocalWifiCapsuleCodec.decode(frame)

        assertEquals(stringValue(vector, "frameHex"), frame.toHex())
        assertEquals(stringValue(vector, "capsuleIdHex"), decoded.capsuleId)
        assertEquals("নদীর পাশের গ্রামে পানি প্রয়োজন", decoded.capsule.message)
    }

    @Test
    fun nonCanonicalBooleanIsRejected() {
        val encoded = LocalWifiCapsuleCodec.encode(
            LocalWifiCapsule(
                senderLabel = "Shongket-A1B2",
                message = "help",
                location = "bridge",
                urgency = LocalWifiUrgency.CRITICAL,
                visibility = LocalWifiVisibility.PUBLIC,
                humanConfirmed = true,
                forwardingConsent = false,
                createdAtEpochSeconds = 1_800_000_000,
                expiresAtEpochSeconds = 1_800_086_400,
            ),
        )
        val body = encoded.copyOfRange(0, encoded.size - 32)
        body[24] = 2
        val malformed = body + sha256(body)

        try {
            LocalWifiCapsuleCodec.decode(malformed)
            throw AssertionError("expected LocalWifiProtocolException")
        } catch (error: LocalWifiProtocolException) {
            assertEquals("BOOLEAN_INVALID", error.code)
        }
    }

    private fun vectorText(): String =
        checkNotNull(javaClass.classLoader?.getResource("local_wifi_v1.json"))
            .readText(Charsets.UTF_8)

    private fun stringValue(document: String, key: String): String =
        checkNotNull(
            Regex("\"${Regex.escape(key)}\"\\s*:\\s*\"([^\"]+)\"")
                .find(document)
                ?.groupValues
                ?.get(1),
        )
}
