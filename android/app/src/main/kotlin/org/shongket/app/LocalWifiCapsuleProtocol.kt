package org.shongket.app

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import org.shongket.data.transport.LOCAL_WIFI_PROTOCOL_VERSION
import org.shongket.data.transport.MAX_LOCAL_WIFI_FRAME_BYTES

const val MAX_CAPSULE_MESSAGE_BYTES: Int = 4_096
const val MAX_CAPSULE_LOCATION_BYTES: Int = 1_024
const val MAX_CAPSULE_SENDER_LABEL_BYTES: Int = 64

enum class LocalWifiUrgency(val wireCode: Int) {
    ROUTINE(1),
    IMPORTANT(2),
    CRITICAL(3),
}

enum class LocalWifiVisibility(val wireCode: Int) {
    PUBLIC(1),
    PRIVATE(2),
}

data class LocalWifiCapsule(
    val senderLabel: String,
    val message: String,
    val location: String,
    val urgency: LocalWifiUrgency,
    val visibility: LocalWifiVisibility,
    val humanConfirmed: Boolean,
    val forwardingConsent: Boolean,
    val createdAtEpochSeconds: Long,
    val expiresAtEpochSeconds: Long,
)

data class DecodedLocalWifiCapsule(
    val capsuleId: String,
    val capsule: LocalWifiCapsule,
)

class LocalWifiProtocolException(
    val code: String,
) : IllegalArgumentException(code)

object LocalWifiCapsuleCodec {
    private const val MAGIC = 0x53484B54
    private const val TYPE_CAPSULE = 1
    private const val DIGEST_BYTES = 32

    fun encode(capsule: LocalWifiCapsule): ByteArray {
        requireTimestampRange(capsule.createdAtEpochSeconds, capsule.expiresAtEpochSeconds)
        val sender = encodeUtf8(
            capsule.senderLabel,
            MAX_CAPSULE_SENDER_LABEL_BYTES,
            "SENDER_LABEL",
        )
        val message = encodeUtf8(capsule.message, MAX_CAPSULE_MESSAGE_BYTES, "MESSAGE")
        val location = encodeUtf8(capsule.location, MAX_CAPSULE_LOCATION_BYTES, "LOCATION")
        val bodyBuffer = ByteArrayOutputStream()
        DataOutputStream(bodyBuffer).use { output ->
            output.writeInt(MAGIC)
            output.writeByte(LOCAL_WIFI_PROTOCOL_VERSION)
            output.writeByte(TYPE_CAPSULE)
            output.writeLong(capsule.createdAtEpochSeconds)
            output.writeLong(capsule.expiresAtEpochSeconds)
            output.writeByte(capsule.urgency.wireCode)
            output.writeByte(capsule.visibility.wireCode)
            output.writeBoolean(capsule.humanConfirmed)
            output.writeBoolean(capsule.forwardingConsent)
            writeSized(output, sender)
            writeSized(output, message)
            writeSized(output, location)
        }
        val body = bodyBuffer.toByteArray()
        val digest = sha256(body)
        val frame = body + digest
        if (frame.size > MAX_LOCAL_WIFI_FRAME_BYTES) {
            throw LocalWifiProtocolException("CAPSULE_TOO_LARGE")
        }
        return frame
    }

    fun decode(frame: ByteArray): DecodedLocalWifiCapsule {
        if (frame.size !in (MIN_CAPSULE_BYTES..MAX_LOCAL_WIFI_FRAME_BYTES)) {
            throw LocalWifiProtocolException("FRAME_SIZE_INVALID")
        }
        val body = frame.copyOfRange(0, frame.size - DIGEST_BYTES)
        val receivedDigest = frame.copyOfRange(frame.size - DIGEST_BYTES, frame.size)
        val expectedDigest = sha256(body)
        if (!MessageDigest.isEqual(receivedDigest, expectedDigest)) {
            throw LocalWifiProtocolException("INTEGRITY_MISMATCH")
        }

        val capsule = try {
            DataInputStream(ByteArrayInputStream(body)).use { input ->
                if (input.readInt() != MAGIC) fail("MAGIC_INVALID")
                if (input.readUnsignedByte() != LOCAL_WIFI_PROTOCOL_VERSION) {
                    fail("VERSION_UNSUPPORTED")
                }
                if (input.readUnsignedByte() != TYPE_CAPSULE) fail("TYPE_UNSUPPORTED")
                val createdAt = input.readLong()
                val expiresAt = input.readLong()
                requireTimestampRange(createdAt, expiresAt)
                val urgencyCode = input.readUnsignedByte()
                val visibilityCode = input.readUnsignedByte()
                val humanConfirmed = input.readBoolean()
                val forwardingConsent = input.readBoolean()
                val sender = readSized(
                    input,
                    MAX_CAPSULE_SENDER_LABEL_BYTES,
                    "SENDER_LABEL",
                )
                val message = readSized(input, MAX_CAPSULE_MESSAGE_BYTES, "MESSAGE")
                val location = readSized(input, MAX_CAPSULE_LOCATION_BYTES, "LOCATION")
                if (input.available() != 0) fail("TRAILING_BYTES")
                LocalWifiCapsule(
                    senderLabel = sender,
                    message = message,
                    location = location,
                    urgency = LocalWifiUrgency.entries
                        .singleOrNull { it.wireCode == urgencyCode }
                        ?: fail("URGENCY_INVALID"),
                    visibility = LocalWifiVisibility.entries
                        .singleOrNull { it.wireCode == visibilityCode }
                        ?: fail("VISIBILITY_INVALID"),
                    humanConfirmed = humanConfirmed,
                    forwardingConsent = forwardingConsent,
                    createdAtEpochSeconds = createdAt,
                    expiresAtEpochSeconds = expiresAt,
                )
            }
        } catch (error: LocalWifiProtocolException) {
            throw error
        } catch (_: Exception) {
            throw LocalWifiProtocolException("FRAME_MALFORMED")
        }
        return DecodedLocalWifiCapsule(expectedDigest.toHex(), capsule)
    }

    private fun requireTimestampRange(createdAt: Long, expiresAt: Long) {
        if (createdAt <= 0) fail("CREATED_AT_INVALID")
        if (expiresAt <= createdAt) fail("EXPIRY_INVALID")
        if (expiresAt - createdAt > MAX_LIFETIME_SECONDS) fail("EXPIRY_INVALID")
    }

    private fun encodeUtf8(value: String, maximum: Int, field: String): ByteArray {
        val bytes = value.toByteArray(StandardCharsets.UTF_8)
        if (bytes.isEmpty()) fail("${field}_REQUIRED")
        if (bytes.size > maximum) fail("${field}_TOO_LARGE")
        return bytes
    }

    private fun writeSized(output: DataOutputStream, value: ByteArray) {
        output.writeShort(value.size)
        output.write(value)
    }

    private fun readSized(
        input: DataInputStream,
        maximum: Int,
        field: String,
    ): String {
        val length = input.readUnsignedShort()
        if (length == 0) fail("${field}_REQUIRED")
        if (length > maximum || length > input.available()) fail("${field}_SIZE_INVALID")
        val bytes = ByteArray(length)
        input.readFully(bytes)
        return try {
            StandardCharsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(bytes))
                .toString()
        } catch (_: Exception) {
            fail("${field}_UTF8_INVALID")
        }
    }

    private fun fail(code: String): Nothing = throw LocalWifiProtocolException(code)

    private const val MIN_CAPSULE_BYTES = 62
    private const val MAX_LIFETIME_SECONDS = 7 * 24 * 60 * 60L
}

internal fun sha256(value: ByteArray): ByteArray =
    MessageDigest.getInstance("SHA-256").digest(value)

internal fun ByteArray.toHex(): String =
    joinToString(separator = "") { byte -> "%02x".format(byte.toInt() and 0xff) }
