package org.shongket.media

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MediaPipelineTest {
    private val pipeline = SourcePreservingMediaPipeline(
        DeterministicFixtureEncoder(),
        chunkBytes = 7,
    )

    @Test
    fun photoProducesCanonicalRepresentationSetAndVerifiedChunks() {
        val manifest = pipeline.build(item(MediaModality.PHOTO))
        assertEquals(RepresentationId.entries, manifest.representations.map { it.id })
        assertTrue(manifest.representations.all { it.availability == Availability.AVAILABLE })
        manifest.representations.forEach {
            assertTrue(it.chunks.isNotEmpty())
            it.chunks.forEach(MediaChunk::verifiedCopy)
        }
    }

    @Test
    fun unsupportedRepresentationIsExplicitInsteadOfOmitted() {
        val manifest = pipeline.build(item(MediaModality.TEXT))
        val thumb = manifest.representations.single { it.id == RepresentationId.THUMB }
        assertEquals(Availability.UNAVAILABLE, thumb.availability)
        assertEquals("ENCODER_UNAVAILABLE", thumb.reasonCode)
    }

    @Test
    fun progressiveOrderStartsWithSignalThenIncreasingMediaQuality() {
        val manifest = pipeline.build(item(MediaModality.PHOTO))
        assertEquals(
            DeliveryItem.entries,
            ProgressiveDeliveryPlanner.orderedItems(manifest),
        )
    }

    @Test
    fun previewCanBeActionableWhileOriginalRemainsIncomplete() {
        val states = PlaybackStateResolver.resolve(
            pipeline.build(item(MediaModality.PHOTO)),
            setOf(RepresentationId.THUMB, RepresentationId.PREVIEW),
        )
        assertTrue(states.single { it.id == RepresentationId.PREVIEW }.actionable)
        val original = states.single { it.id == RepresentationId.ORIGINAL }
        assertEquals(Availability.INCOMPLETE, original.availability)
        assertFalse(original.actionable)
    }

    @Test
    fun originalBytesAndObjectIdentityNeverChange() {
        val sourceBytes = "source-evidence-bangla-সংকেত".toByteArray()
        val source = RawMediaItem(MediaModality.DOCUMENT, sourceBytes)
        val before = source.sourceBytes()
        val manifest = pipeline.build(source)
        val original = manifest.representations.single { it.id == RepresentationId.ORIGINAL }
        assertArrayEquals(before, source.sourceBytes())
        assertArrayEquals(before, pipeline.reconstruct(original))
        assertEquals(sha256(before), manifest.objectId)
    }

    @Test(expected = IllegalArgumentException::class)
    fun corruptedChunkIsRejectedBeforePlayback() {
        val record = pipeline.build(item(MediaModality.PHOTO))
            .representations.single { it.id == RepresentationId.PREVIEW }
        record.chunks.first().bytes[0] = (record.chunks.first().bytes[0] + 1).toByte()
        pipeline.reconstruct(record)
    }

    private fun item(modality: MediaModality): RawMediaItem =
        RawMediaItem(modality, ByteArray(300) { (it % 251).toByte() })
}
