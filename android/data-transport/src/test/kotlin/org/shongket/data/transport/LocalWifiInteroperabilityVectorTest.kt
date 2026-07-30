package org.shongket.data.transport

import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import org.junit.Assert.assertEquals
import org.junit.Test

class LocalWifiInteroperabilityVectorTest {
    @Test
    fun requestFramingMatchesSharedSwiftVector() {
        val vector = vectorText()
        val frame = stringValue(vector, "frameHex").hexToBytes()
        val output = ByteArrayOutputStream()

        LocalWifiFraming.write(BufferedOutputStream(output), frame)

        assertEquals(stringValue(vector, "requestHex"), output.toByteArray().toHex())
        assertEquals(
            frame.toHex(),
            LocalWifiFraming.read(
                BufferedInputStream(ByteArrayInputStream(output.toByteArray())),
            ).toHex(),
        )
    }

    @Test
    fun acknowledgementsMatchSharedSwiftVectors() {
        val vector = vectorText()
        val frameId = stringValue(vector, "frameIdHex")
        val expectations = listOf(
            AckStatus.ACCEPTED to "acceptedAckHex",
            AckStatus.DUPLICATE to "duplicateAckHex",
            AckStatus.REFUSED to "refusedAckHex",
        )

        expectations.forEach { (status, key) ->
            val output = ByteArrayOutputStream()
            LocalWifiFraming.writeAck(BufferedOutputStream(output), frameId, status)
            val acknowledgement = output.toByteArray()

            assertEquals(stringValue(vector, key), acknowledgement.toHex())
            assertEquals(
                status,
                LocalWifiFraming.readAck(
                    BufferedInputStream(ByteArrayInputStream(acknowledgement)),
                    frameId,
                ),
            )
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

    private fun String.hexToBytes(): ByteArray {
        require(length.isEven())
        return ByteArray(length / 2) { index ->
            substring(index * 2, index * 2 + 2).toInt(16).toByte()
        }
    }

    private fun Int.isEven(): Boolean = this % 2 == 0
}
