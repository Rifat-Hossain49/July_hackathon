package org.shongket.app

import java.net.InetAddress
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalWifiProtocolTest {
    @Test
    fun unicodeCapsuleRoundTripsWithStableContentIdentity() {
        val capsule = fixtureCapsule()
        val first = LocalWifiCapsuleCodec.decode(LocalWifiCapsuleCodec.encode(capsule))
        val second = LocalWifiCapsuleCodec.decode(LocalWifiCapsuleCodec.encode(capsule))

        assertEquals(capsule, first.capsule)
        assertEquals(first.capsuleId, second.capsuleId)
        assertEquals(64, first.capsuleId.length)
    }

    @Test
    fun corruptedCapsuleIsRejectedBeforeContentIsReturned() {
        val encoded = LocalWifiCapsuleCodec.encode(fixtureCapsule()).copyOf()
        encoded[encoded.lastIndex] = (encoded.last().toInt() xor 1).toByte()

        assertProtocolError("INTEGRITY_MISMATCH") {
            LocalWifiCapsuleCodec.decode(encoded)
        }
    }

    @Test
    fun unknownVersionIsRejectedAfterIntegrityVerification() {
        val encoded = LocalWifiCapsuleCodec.encode(fixtureCapsule())
        val body = encoded.copyOfRange(0, encoded.size - 32)
        body[4] = 99
        val unknownVersion = body + sha256(body)

        assertProtocolError("VERSION_UNSUPPORTED") {
            LocalWifiCapsuleCodec.decode(unknownVersion)
        }
    }

    @Test
    fun malformedUtf8IsRejected() {
        val encoded = LocalWifiCapsuleCodec.encode(fixtureCapsule())
        val body = encoded.copyOfRange(0, encoded.size - 32)
        val senderStart = 28
        body[senderStart] = 0xc3.toByte()
        body[senderStart + 1] = 0x28
        val malformed = body + sha256(body)

        assertProtocolError("SENDER_LABEL_UTF8_INVALID") {
            LocalWifiCapsuleCodec.decode(malformed)
        }
    }

    @Test
    fun trailingAndOversizedContentAreRejected() {
        val encoded = LocalWifiCapsuleCodec.encode(fixtureCapsule())
        val body = encoded.copyOfRange(0, encoded.size - 32) + byteArrayOf(0)
        assertProtocolError("TRAILING_BYTES") {
            LocalWifiCapsuleCodec.decode(body + sha256(body))
        }

        assertProtocolError("MESSAGE_TOO_LARGE") {
            LocalWifiCapsuleCodec.encode(
                fixtureCapsule().copy(message = "a".repeat(MAX_CAPSULE_MESSAGE_BYTES + 1)),
            )
        }
    }

    @Test
    fun onlyLocalNetworkAddressClassesAreAllowed() {
        assertTrue(LocalNetworkAddress.isAllowed(InetAddress.getByName("127.0.0.1")))
        assertTrue(LocalNetworkAddress.isAllowed(InetAddress.getByName("192.168.1.20")))
        assertTrue(LocalNetworkAddress.isAllowed(InetAddress.getByName("10.20.30.40")))
        assertTrue(LocalNetworkAddress.isAllowed(InetAddress.getByName("fd00::20")))
        assertFalse(LocalNetworkAddress.isAllowed(InetAddress.getByName("8.8.8.8")))
        assertFalse(LocalNetworkAddress.isAllowed(InetAddress.getByName("2001:4860:4860::8888")))
    }

    private fun fixtureCapsule(): LocalWifiCapsule =
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
        )

    private fun assertProtocolError(
        expectedCode: String,
        action: () -> Unit,
    ) {
        try {
            action()
            throw AssertionError("expected LocalWifiProtocolException")
        } catch (error: LocalWifiProtocolException) {
            assertEquals(expectedCode, error.code)
        }
    }
}
