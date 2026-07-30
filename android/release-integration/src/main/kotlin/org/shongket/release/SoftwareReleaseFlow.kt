package org.shongket.release

import java.nio.file.Path
import org.shongket.data.persistence.AppPrivateStateStore
import org.shongket.data.persistence.DurableTransferRepository
import org.shongket.data.persistence.IngestResult
import org.shongket.data.persistence.VerifiedFragment
import org.shongket.data.transport.BackgroundTransferCoordinator
import org.shongket.data.transport.SimulatedTransportAdapter
import org.shongket.data.transport.TransportCapabilities
import org.shongket.data.transport.TransportResult
import org.shongket.diagnostics.DiagnosticComponent
import org.shongket.diagnostics.DiagnosticEvent
import org.shongket.diagnostics.ExportResult
import org.shongket.diagnostics.RedactedDiagnosticRecorder
import org.shongket.media.Availability
import org.shongket.media.DeliveryItem
import org.shongket.media.DeterministicFixtureEncoder
import org.shongket.media.MediaModality
import org.shongket.media.ProgressiveDeliveryPlanner
import org.shongket.media.RawMediaItem
import org.shongket.media.RepresentationId
import org.shongket.media.SourcePreservingMediaPipeline
import org.shongket.security.ConsentDecision
import org.shongket.security.PrivateForwardConsentGate
import org.shongket.semantic.ManualCapsuleWorkflow
import org.shongket.semantic.PublishResult
import org.shongket.semantic.SemanticSource
import org.shongket.semantic.Urgency

data class SoftwareReleaseEvidence(
    val objectId: String,
    val sourceBytesAfterFlow: ByteArray,
    val orderedDelivery: List<DeliveryItem>,
    val restartMissingIndexes: List<Int>,
    val storedFragments: Int,
    val humanConfirmed: Boolean,
    val diagnosticJson: String,
) {
    override fun equals(other: Any?): Boolean =
        other is SoftwareReleaseEvidence &&
            objectId == other.objectId &&
            sourceBytesAfterFlow.contentEquals(other.sourceBytesAfterFlow) &&
            orderedDelivery == other.orderedDelivery &&
            restartMissingIndexes == other.restartMissingIndexes &&
            storedFragments == other.storedFragments &&
            humanConfirmed == other.humanConfirmed &&
            diagnosticJson == other.diagnosticJson

    override fun hashCode(): Int = objectId.hashCode()
}

class SoftwareReleaseFlow {
    fun runDeterministicFixture(
        stateDirectory: Path,
        sourceBytes: ByteArray,
        explicitPrivateForwardConsent: Boolean,
    ): SoftwareReleaseEvidence {
        val source = RawMediaItem(MediaModality.DOCUMENT, sourceBytes)
        val pipeline = SourcePreservingMediaPipeline(DeterministicFixtureEncoder())
        val manifest = pipeline.build(source)
        val original = manifest.representations.single {
            it.id == RepresentationId.ORIGINAL && it.availability == Availability.AVAILABLE
        }

        val semanticSource = SemanticSource(source.objectId, source.modality.name)
        val semantic = ManualCapsuleWorkflow()
        val capsule = semantic.manualDraft(
            semanticSource,
            eventType = "needs_assessment",
            locationText = "operator supplied location",
            urgency = Urgency.IMPORTANT,
            requiredAction = "review and assist",
            summaryBn = "মানুষের সহায়তা প্রয়োজন",
        ).confirmed()
        check(semantic.publish(capsule) is PublishResult.Scheduled)
        check(
            PrivateForwardConsentGate.evaluate(
                isPrivate = true,
                explicitlyConfirmed = explicitPrivateForwardConsent,
                peerAcceptsPrivate = true,
            ) is ConsentDecision.Allowed,
        ) { "private forward consent is required" }

        val repository = DurableTransferRepository(AppPrivateStateStore(stateDirectory))
        repository.begin(
            transferId = "software-release-flow",
            objectId = source.objectId,
            representationId = "original",
            expectedFragments = original.chunks.size,
            capacityBytes = sourceBytes.size.toLong(),
        )
        val first = original.chunks.first()
        check(
            repository.ingest(
                VerifiedFragment.fromBytes(
                    source.objectId,
                    "original",
                    first.index,
                    first.verifiedCopy(),
                ),
            ) is IngestResult.Accepted,
        )

        val restarted = DurableTransferRepository(AppPrivateStateStore(stateDirectory))
        val missing = restarted.resumePlan()?.missingIndexes ?: emptyList()
        val adapter = SimulatedTransportAdapter(TransportCapabilities(setOf(1), 1_048_576))
        BackgroundTransferCoordinator(adapter).resume(
            checkNotNull(restarted.resumePlan()),
        )
        original.chunks.drop(1).forEach { chunk ->
            check(adapter.sendAfterSoftwareConnect(chunk.verifiedCopy()) is TransportResult.Accepted)
            check(
                restarted.ingest(
                    VerifiedFragment.fromBytes(
                        source.objectId,
                        "original",
                        chunk.index,
                        chunk.verifiedCopy(),
                    ),
                ) is IngestResult.Accepted,
            )
        }

        val diagnostics = RedactedDiagnosticRecorder()
        diagnostics.record(
            DiagnosticEvent(
                tick = 1,
                component = DiagnosticComponent.APPLICATION,
                code = "FLOW_COMPLETE",
                counter = restarted.currentSnapshot()?.fragments?.size?.toLong() ?: 0,
            ),
        )
        val exported = diagnostics.export(userInitiated = true) as ExportResult.Exported
        check(pipeline.reconstruct(original).contentEquals(sourceBytes))
        return SoftwareReleaseEvidence(
            objectId = source.objectId,
            sourceBytesAfterFlow = source.sourceBytes(),
            orderedDelivery = ProgressiveDeliveryPlanner.orderedItems(manifest),
            restartMissingIndexes = missing,
            storedFragments = restarted.currentSnapshot()?.fragments?.size ?: 0,
            humanConfirmed = capsule.humanConfirmed,
            diagnosticJson = exported.canonicalJson,
        )
    }

    private fun SimulatedTransportAdapter.sendAfterSoftwareConnect(
        frame: ByteArray,
    ): TransportResult {
        discover()
        connect("release-peer", TransportCapabilities(setOf(1), 1_048_576))
        return send(frame)
    }
}
