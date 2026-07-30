package org.shongket.media

import java.security.MessageDigest

const val MAX_SOURCE_BYTES: Int = 8 * 1024 * 1024
const val DEFAULT_MEDIA_CHUNK_BYTES: Int = 64 * 1024
const val MAX_MEDIA_METADATA_ENTRIES: Int = 32

enum class MediaModality {
    PHOTO,
    VIDEO,
    AUDIO,
    TEXT,
    DOCUMENT,
}

enum class RepresentationId {
    THUMB,
    PREVIEW,
    STANDARD,
    ORIGINAL,
}

enum class Availability {
    AVAILABLE,
    UNAVAILABLE,
    INCOMPLETE,
}

class RawMediaItem(
    val modality: MediaModality,
    sourceBytes: ByteArray,
    val metadata: Map<String, String> = emptyMap(),
) {
    private val preservedSource = sourceBytes.copyOf()

    init {
        require(sourceBytes.size in 1..MAX_SOURCE_BYTES) { "source is outside the size limit" }
        require(metadata.size <= MAX_MEDIA_METADATA_ENTRIES) { "too many metadata entries" }
        require(metadata.all { (key, value) ->
            key.matches(Regex("[a-z][a-z0-9_]{0,31}")) && value.length <= 256
        }) { "invalid metadata" }
    }

    val objectId: String = sha256(preservedSource)

    fun sourceBytes(): ByteArray = preservedSource.copyOf()
}

data class MediaChunk(
    val index: Int,
    val sha256: String,
    val bytes: ByteArray,
) {
    fun verifiedCopy(): ByteArray {
        require(index >= 0) { "negative chunk index" }
        require(bytes.size in 1..DEFAULT_MEDIA_CHUNK_BYTES) { "invalid chunk size" }
        require(sha256(bytes) == sha256) { "chunk integrity mismatch" }
        return bytes.copyOf()
    }

    override fun equals(other: Any?): Boolean =
        other is MediaChunk &&
            index == other.index &&
            sha256 == other.sha256 &&
            bytes.contentEquals(other.bytes)

    override fun hashCode(): Int = 31 * (31 * index + sha256.hashCode()) + bytes.contentHashCode()
}

data class RepresentationRecord(
    val id: RepresentationId,
    val availability: Availability,
    val sha256: String?,
    val chunks: List<MediaChunk>,
    val reasonCode: String?,
) {
    fun validate() {
        if (availability == Availability.AVAILABLE) {
            require(sha256?.matches(Regex("[0-9a-f]{64}")) == true)
            require(chunks.isNotEmpty())
            require(reasonCode == null)
        } else {
            require(chunks.isEmpty())
            require(sha256 == null)
            require(!reasonCode.isNullOrBlank())
        }
    }
}

data class MediaManifest(
    val objectId: String,
    val modality: MediaModality,
    val representations: List<RepresentationRecord>,
) {
    fun validate() {
        require(objectId.matches(Regex("[0-9a-f]{64}")))
        require(representations.map { it.id } == RepresentationId.entries)
        representations.forEach(RepresentationRecord::validate)
    }
}

internal fun sha256(bytes: ByteArray): String =
    MessageDigest.getInstance("SHA-256")
        .digest(bytes)
        .joinToString("") { "%02x".format(it.toInt() and 0xff) }
