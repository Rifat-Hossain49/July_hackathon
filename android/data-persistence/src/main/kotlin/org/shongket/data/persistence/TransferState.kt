package org.shongket.data.persistence

import java.security.MessageDigest
import java.util.Base64

const val MAX_FRAGMENT_BYTES: Int = 1_048_576
const val MAX_EXPECTED_FRAGMENTS: Int = 65_536
const val MAX_STORE_CAPACITY_BYTES: Long = 32L * 1024L * 1024L
const val MAX_STATE_DOCUMENT_BYTES: Long = 64L * 1024L * 1024L

data class VerifiedFragment(
    val objectId: String,
    val representationId: String,
    val chunkIndex: Int,
    val sha256: String,
    val payloadBase64: String,
) {
    val payload: ByteArray
        get() = Base64.getDecoder().decode(payloadBase64)

    val byteLength: Int
        get() = payload.size

    fun validate(expectedFragments: Int? = null) {
        require(OBJECT_ID.matches(objectId)) { "invalid object id" }
        require(REPRESENTATION_ID.matches(representationId)) {
            "invalid representation id"
        }
        require(chunkIndex >= 0) { "negative chunk index" }
        expectedFragments?.let {
            require(chunkIndex < it) { "chunk index outside transfer" }
        }
        require(SHA256.matches(sha256)) { "invalid fragment digest" }
        val decoded = try {
            payload
        } catch (error: IllegalArgumentException) {
            throw IllegalArgumentException("invalid fragment base64", error)
        }
        require(decoded.isNotEmpty()) { "empty fragment" }
        require(decoded.size <= MAX_FRAGMENT_BYTES) { "fragment exceeds size limit" }
        require(digest(decoded) == sha256) { "fragment integrity mismatch" }
    }

    companion object {
        private val OBJECT_ID = Regex("[0-9a-f]{64}")
        private val SHA256 = Regex("[0-9a-f]{64}")
        private val REPRESENTATION_ID = Regex("[a-z][a-z0-9._-]{0,63}")

        fun fromBytes(
            objectId: String,
            representationId: String,
            chunkIndex: Int,
            payload: ByteArray,
        ): VerifiedFragment {
            require(payload.size in 1..MAX_FRAGMENT_BYTES) {
                "fragment payload is outside the supported size"
            }
            return VerifiedFragment(
                objectId = objectId,
                representationId = representationId,
                chunkIndex = chunkIndex,
                sha256 = digest(payload),
                payloadBase64 = Base64.getEncoder().encodeToString(payload),
            ).also { it.validate() }
        }

        private fun digest(payload: ByteArray): String =
            MessageDigest.getInstance("SHA-256")
                .digest(payload)
                .joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }
}

data class TransferSnapshot(
    val transferId: String,
    val objectId: String,
    val representationId: String,
    val expectedFragments: Int,
    val capacityBytes: Long,
    val fragments: List<VerifiedFragment>,
) {
    val usedBytes: Long
        get() = fragments.sumOf { it.byteLength.toLong() }

    val missingIndexes: List<Int>
        get() {
            val present = fragments.asSequence().map { it.chunkIndex }.toHashSet()
            return (0 until expectedFragments).filterNot(present::contains)
        }

    fun validate() {
        require(TRANSFER_ID.matches(transferId)) { "invalid transfer id" }
        require(expectedFragments in 1..MAX_EXPECTED_FRAGMENTS) {
            "expected fragment count is outside the supported range"
        }
        require(capacityBytes in 1..MAX_STORE_CAPACITY_BYTES) {
            "capacity is outside the supported range"
        }
        require(fragments.size <= expectedFragments) { "too many fragments" }
        require(fragments.map { it.chunkIndex }.toSet().size == fragments.size) {
            "duplicate fragment index"
        }
        fragments.forEach {
            require(it.objectId == objectId) { "fragment object mismatch" }
            require(it.representationId == representationId) {
                "fragment representation mismatch"
            }
            it.validate(expectedFragments)
        }
        require(usedBytes <= capacityBytes) { "snapshot exceeds its byte budget" }
    }

    companion object {
        private val TRANSFER_ID = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
    }
}

data class ResumePlan(
    val transferId: String,
    val objectId: String,
    val representationId: String,
    val missingIndexes: List<Int>,
)

enum class RecoveryEvent {
    DISCARDED_TRUNCATED_TEMP,
    QUARANTINED_PRIMARY,
    LOADED_LAST_GOOD,
    LAST_GOOD_UNREADABLE,
    DROPPED_CORRUPT_FRAGMENT,
}

data class LoadResult(
    val snapshot: TransferSnapshot?,
    val events: List<RecoveryEvent> = emptyList(),
)
