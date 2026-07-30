package org.shongket.media

interface RepresentationEncoder {
    fun encode(
        source: RawMediaItem,
        representationId: RepresentationId,
    ): EncodingResult
}

sealed interface EncodingResult {
    data class Produced(val bytes: ByteArray) : EncodingResult
    data class Unsupported(val reasonCode: String) : EncodingResult
}

/**
 * Deterministic, license-clean test encoder. It proves representation policy
 * without claiming a platform codec, camera, or microphone implementation.
 */
class DeterministicFixtureEncoder : RepresentationEncoder {
    override fun encode(
        source: RawMediaItem,
        representationId: RepresentationId,
    ): EncodingResult {
        val original = source.sourceBytes()
        if (representationId == RepresentationId.ORIGINAL) {
            return EncodingResult.Produced(original)
        }
        val supported = when (source.modality) {
            MediaModality.PHOTO, MediaModality.VIDEO, MediaModality.DOCUMENT -> true
            MediaModality.AUDIO -> representationId != RepresentationId.THUMB
            MediaModality.TEXT -> representationId == RepresentationId.PREVIEW
        }
        if (!supported) return EncodingResult.Unsupported("ENCODER_UNAVAILABLE")
        val target = when (representationId) {
            RepresentationId.THUMB -> 16
            RepresentationId.PREVIEW -> 64
            RepresentationId.STANDARD -> 256
            RepresentationId.ORIGINAL -> original.size
        }
        val header = "shongket-fixture-${representationId.name.lowercase()}:".toByteArray()
        return EncodingResult.Produced(header + original.copyOf(minOf(original.size, target)))
    }
}

class SourcePreservingMediaPipeline(
    private val encoder: RepresentationEncoder,
    private val chunkBytes: Int = DEFAULT_MEDIA_CHUNK_BYTES,
) {
    init {
        require(chunkBytes in 1..DEFAULT_MEDIA_CHUNK_BYTES) { "invalid chunk size" }
    }

    fun build(source: RawMediaItem): MediaManifest {
        val originalBefore = source.sourceBytes()
        val records = RepresentationId.entries.map { id ->
            when (val result = encoder.encode(source, id)) {
                is EncodingResult.Produced -> {
                    require(result.bytes.isNotEmpty()) { "empty representation" }
                    require(result.bytes.size <= MAX_SOURCE_BYTES) { "representation exceeds limit" }
                    val chunks = result.bytes.asList()
                        .chunked(chunkBytes)
                        .mapIndexed { index, values ->
                            val bytes = values.toByteArray()
                            MediaChunk(index, sha256(bytes), bytes)
                        }
                    RepresentationRecord(
                        id = id,
                        availability = Availability.AVAILABLE,
                        sha256 = sha256(result.bytes),
                        chunks = chunks,
                        reasonCode = null,
                    )
                }
                is EncodingResult.Unsupported -> RepresentationRecord(
                    id = id,
                    availability = Availability.UNAVAILABLE,
                    sha256 = null,
                    chunks = emptyList(),
                    reasonCode = result.reasonCode,
                )
            }
        }
        require(originalBefore.contentEquals(source.sourceBytes())) {
            "encoder mutated source evidence"
        }
        val original = records.single { it.id == RepresentationId.ORIGINAL }
        require(reconstruct(original).contentEquals(originalBefore)) {
            "original representation did not preserve source"
        }
        return MediaManifest(source.objectId, source.modality, records).also { it.validate() }
    }

    fun reconstruct(record: RepresentationRecord): ByteArray {
        record.validate()
        require(record.availability == Availability.AVAILABLE)
        require(record.chunks.map { it.index } == record.chunks.indices.toList()) {
            "fragment sequence is incomplete"
        }
        val bytes = record.chunks.flatMap { it.verifiedCopy().asList() }.toByteArray()
        require(sha256(bytes) == record.sha256) { "representation integrity mismatch" }
        return bytes
    }
}

enum class DeliveryItem {
    CAPSULE,
    MANIFEST,
    THUMB,
    PREVIEW,
    STANDARD,
    ORIGINAL,
}

object ProgressiveDeliveryPlanner {
    fun orderedItems(manifest: MediaManifest): List<DeliveryItem> {
        manifest.validate()
        return listOf(DeliveryItem.CAPSULE, DeliveryItem.MANIFEST) +
            manifest.representations
                .filter { it.availability == Availability.AVAILABLE }
                .map { DeliveryItem.valueOf(it.id.name) }
    }
}
