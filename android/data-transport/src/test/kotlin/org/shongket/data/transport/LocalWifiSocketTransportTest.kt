package org.shongket.data.transport

import java.net.InetAddress
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalWifiSocketTransportTest {
    @Test
    fun twoLocalEndpointsExchangeAndAcknowledgeABoundedFrame() {
        val received = arrayOfNulls<ByteArray>(1)
        val latch = CountDownLatch(1)
        val server = LocalWifiSocketServer { frame, _ ->
            received[0] = frame
            latch.countDown()
            LocalWifiReceiveDecision.Accepted
        }
        try {
            val port = server.start()
            val frame = LocalWifiCapsuleCodec.encode(fixtureCapsule())
            val result = LocalWifiSocketClient.send(loopbackEndpoint(port), frame)

            assertTrue(result is LocalWifiSendResult.Accepted)
            assertTrue(latch.await(2, TimeUnit.SECONDS))
            assertArrayEquals(frame, received[0])
        } finally {
            server.close()
        }
    }

    @Test
    fun duplicateFrameIsAcknowledgedWithoutSecondDelivery() {
        val deliveries = AtomicInteger()
        val server = LocalWifiSocketServer { _, _ ->
            deliveries.incrementAndGet()
            LocalWifiReceiveDecision.Accepted
        }
        try {
            val port = server.start()
            val frame = LocalWifiCapsuleCodec.encode(fixtureCapsule())
            val first = LocalWifiSocketClient.send(loopbackEndpoint(port), frame)
            val second = LocalWifiSocketClient.send(loopbackEndpoint(port), frame)

            assertEquals(false, (first as LocalWifiSendResult.Accepted).duplicate)
            assertEquals(true, (second as LocalWifiSendResult.Accepted).duplicate)
            assertEquals(1, deliveries.get())
        } finally {
            server.close()
        }
    }

    @Test
    fun receiverRefusalIsReturnedAndNotRememberedAsDuplicate() {
        val attempts = AtomicInteger()
        val server = LocalWifiSocketServer { _, _ ->
            attempts.incrementAndGet()
            LocalWifiReceiveDecision.Refused("POLICY_REFUSED")
        }
        try {
            val port = server.start()
            val frame = LocalWifiCapsuleCodec.encode(fixtureCapsule())
            assertEquals(
                LocalWifiSendResult.Refused("PEER_REFUSED"),
                LocalWifiSocketClient.send(loopbackEndpoint(port), frame),
            )
            assertEquals(
                LocalWifiSendResult.Refused("PEER_REFUSED"),
                LocalWifiSocketClient.send(loopbackEndpoint(port), frame),
            )
            assertEquals(2, attempts.get())
        } finally {
            server.close()
        }
    }

    @Test
    fun publicInternetAndOversizedFramesAreRefusedBeforeConnection() {
        val publicEndpoint = LocalWifiPeerEndpoint(
            "public-address",
            InetAddress.getByName("8.8.8.8"),
            8_080,
        )
        assertEquals(
            LocalWifiSendResult.Refused("NON_LOCAL_ADDRESS"),
            LocalWifiSocketClient.send(publicEndpoint, byteArrayOf(1)),
        )
        assertEquals(
            LocalWifiSendResult.Refused("PAYLOAD_TOO_LARGE"),
            LocalWifiSocketClient.send(
                loopbackEndpoint(9),
                ByteArray(MAX_LOCAL_WIFI_FRAME_BYTES + 1),
            ),
        )
    }

    private fun loopbackEndpoint(port: Int): LocalWifiPeerEndpoint =
        LocalWifiPeerEndpoint(
            serviceName = "Shongket-test",
            address = InetAddress.getLoopbackAddress(),
            port = port,
        )

    private fun fixtureCapsule(): LocalWifiCapsule =
        LocalWifiCapsule(
            senderLabel = "Shongket-test",
            message = "water needed",
            location = "east bank",
            urgency = LocalWifiUrgency.IMPORTANT,
            visibility = LocalWifiVisibility.PUBLIC,
            humanConfirmed = true,
            forwardingConsent = false,
            createdAtEpochSeconds = 1_800_000_000,
            expiresAtEpochSeconds = 1_800_086_400,
        )
}
