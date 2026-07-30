package org.shongket.release

import java.nio.file.Path
import org.shongket.data.persistence.AppPrivateStateStore
import org.shongket.data.persistence.DurableTransferRepository
import org.shongket.data.persistence.IngestResult
import org.shongket.data.persistence.VerifiedFragment
import org.shongket.data.transport.SimulatedTransportAdapter
import org.shongket.data.transport.TransportCapabilities
import org.shongket.data.transport.TransportResult
import org.shongket.diagnostics.DiagnosticComponent
import org.shongket.diagnostics.DiagnosticEvent
import org.shongket.diagnostics.ExportResult
import org.shongket.diagnostics.RedactedDiagnosticRecorder
import org.shongket.media.DeterministicFixtureEncoder
import org.shongket.media.MediaModality
import org.shongket.media.RawMediaItem
import org.shongket.media.RepresentationId
import org.shongket.media.SourcePreservingMediaPipeline
import org.shongket.security.ConsentDecision
import org.shongket.security.PrivateForwardConsentGate
import org.shongket.semantic.ManualCapsuleWorkflow
import org.shongket.semantic.PublishResult
import org.shongket.semantic.SemanticSource
import org.shongket.semantic.Urgency

enum class DemoStage {
    READY,
    MEDIA_CREATED,
    CAPSULE_CONFIRMED,
    PEER_SELECTED,
    TRANSFERRING,
    INTERRUPTED,
    RECEIVED,
}

data class DemoState(
    val stage: DemoStage,
    val progressPercent: Int,
    val objectId: String?,
    val simulatedPeer: String?,
    val isPrivate: Boolean,
    val sourceBytes: Int,
    val verifiedFragments: Int,
    val expectedFragments: Int,
    val receivedVerified: Boolean,
    val lastErrorCode: String?,
    val diagnosticJson: String?,
)

class DemoController(stateDirectory: Path) {
    private val repository = DurableTransferRepository(AppPrivateStateStore(stateDirectory))
    private val mediaPipeline = SourcePreservingMediaPipeline(DeterministicFixtureEncoder())
    private val diagnostics = RedactedDiagnosticRecorder()
    private var adapter = newAdapter()
    private var stage = recoveredStage()
    private var peer: String? = null
    private var privateContent = false
    private var receivedVerified = stage == DemoStage.RECEIVED
    private var errorCode: String? = null
    private var diagnosticJson: String? = null
    private var tick = 0L

    fun state(): DemoState {
        val snapshot = repository.currentSnapshot()
        val verified = snapshot?.fragments?.size ?: 0
        val expected = snapshot?.expectedFragments ?: FIXTURE_CHUNKS
        return DemoState(
            stage = stage,
            progressPercent = if (expected == 0) 0 else verified * 100 / expected,
            objectId = snapshot?.objectId,
            simulatedPeer = peer,
            isPrivate = privateContent,
            sourceBytes = if (snapshot == null) 0 else FIXTURE_BYTES,
            verifiedFragments = verified,
            expectedFragments = expected,
            receivedVerified = receivedVerified,
            lastErrorCode = errorCode,
            diagnosticJson = diagnosticJson,
        )
    }

    fun createFixture() {
        if (repository.currentSnapshot() == null) {
            val source = fixtureSource()
            repository.begin(
                transferId = "hackathon-demo",
                objectId = source.objectId,
                representationId = "original",
                expectedFragments = FIXTURE_CHUNKS,
                capacityBytes = FIXTURE_BYTES.toLong(),
            )
        }
        stage = DemoStage.MEDIA_CREATED
        record("MEDIA_CREATED")
        clearError()
    }

    fun confirmCapsule(
        message: String,
        location: String,
        isPrivate: Boolean,
        explicitConsent: Boolean,
    ) {
        val snapshot = repository.currentSnapshot() ?: return fail("CREATE_MEDIA_FIRST")
        if (message.isBlank()) return fail("MESSAGE_REQUIRED")
        if (location.isBlank()) return fail("LOCATION_REQUIRED")
        val consent = PrivateForwardConsentGate.evaluate(
            isPrivate = isPrivate,
            explicitlyConfirmed = explicitConsent,
            peerAcceptsPrivate = true,
        )
        if (consent !is ConsentDecision.Allowed) {
            return fail((consent as ConsentDecision.Refused).code)
        }
        val workflow = ManualCapsuleWorkflow()
        val draft = workflow.manualDraft(
            source = SemanticSource(snapshot.objectId, MediaModality.DOCUMENT.name),
            eventType = "manual_report",
            locationText = location,
            urgency = Urgency.IMPORTANT,
            requiredAction = "review and assist",
            summaryBn = message,
        ).confirmed()
        check(workflow.publish(draft) is PublishResult.Scheduled)
        privateContent = isPrivate
        stage = DemoStage.CAPSULE_CONFIRMED
        record("CAPSULE_SCHEDULED")
        clearError()
    }

    fun selectSimulatedPeer() {
        if (stage != DemoStage.CAPSULE_CONFIRMED) return fail("CONFIRM_CAPSULE_FIRST")
        adapter.discover()
        check(
            adapter.connect(SIMULATED_PEER, TransportCapabilities(setOf(1), 1_048_576))
                !is org.shongket.data.transport.NegotiationResult.Refused,
        )
        peer = SIMULATED_PEER
        stage = DemoStage.PEER_SELECTED
        record("SIMULATED_PEER_SELECTED")
        clearError()
    }

    fun startTransfer() {
        if (stage != DemoStage.PEER_SELECTED) return fail("SELECT_PEER_FIRST")
        val source = fixtureSource()
        val original = mediaPipeline.build(source)
            .representations.single { it.id == RepresentationId.ORIGINAL }
        val first = original.chunks.first()
        check(adapter.send(first.verifiedCopy()) is TransportResult.Accepted)
        when (
            repository.ingest(
                VerifiedFragment.fromBytes(
                    source.objectId,
                    "original",
                    first.index,
                    first.verifiedCopy(),
                ),
            )
        ) {
            is IngestResult.Accepted, IngestResult.Duplicate -> Unit
            else -> return fail("TRANSFER_REFUSED")
        }
        stage = DemoStage.TRANSFERRING
        record("TRANSFER_STARTED")
        clearError()
    }

    fun interruptTransfer() {
        if (stage != DemoStage.TRANSFERRING) return fail("TRANSFER_NOT_RUNNING")
        adapter.interrupt()
        stage = DemoStage.INTERRUPTED
        record("TRANSFER_INTERRUPTED")
        clearError()
    }

    fun resumeTransfer() {
        if (stage != DemoStage.INTERRUPTED && stage != DemoStage.TRANSFERRING) {
            return fail("NOTHING_TO_RESUME")
        }
        adapter = newAdapter()
        adapter.discover()
        adapter.connect(SIMULATED_PEER, TransportCapabilities(setOf(1), 1_048_576))
        val source = fixtureSource()
        val original = mediaPipeline.build(source)
            .representations.single { it.id == RepresentationId.ORIGINAL }
        val missing = repository.resumePlan()?.missingIndexes ?: emptyList()
        missing.forEach { index ->
            val chunk = original.chunks.single { it.index == index }
            check(adapter.send(chunk.verifiedCopy()) is TransportResult.Accepted)
            check(
                repository.ingest(
                    VerifiedFragment.fromBytes(
                        source.objectId,
                        "original",
                        chunk.index,
                        chunk.verifiedCopy(),
                    ),
                ) is IngestResult.Accepted,
            )
        }
        val reconstructed = repository.currentSnapshot()
            ?.fragments
            ?.sortedBy { it.chunkIndex }
            ?.flatMap { it.payload.asList() }
            ?.toByteArray()
            ?: return fail("RECONSTRUCTION_FAILED")
        if (!reconstructed.contentEquals(source.sourceBytes())) {
            return fail("INTEGRITY_MISMATCH")
        }
        receivedVerified = true
        stage = DemoStage.RECEIVED
        record("RECONSTRUCTION_VERIFIED")
        clearError()
    }

    fun exportDiagnostics() {
        val exported = diagnostics.export(userInitiated = true)
        diagnosticJson = (exported as? ExportResult.Exported)?.canonicalJson
        if (diagnosticJson == null) fail("DIAGNOSTIC_EXPORT_REFUSED") else clearError()
    }

    private fun recoveredStage(): DemoStage {
        val snapshot = repository.currentSnapshot() ?: return DemoStage.READY
        return if (snapshot.missingIndexes.isEmpty()) DemoStage.RECEIVED else DemoStage.INTERRUPTED
    }

    private fun fixtureSource(): RawMediaItem =
        RawMediaItem(
            MediaModality.DOCUMENT,
            ByteArray(FIXTURE_BYTES) { (it % 251).toByte() },
            mapOf("fixture" to "hackathon_demo"),
        )

    private fun newAdapter(): SimulatedTransportAdapter =
        SimulatedTransportAdapter(TransportCapabilities(setOf(1), 1_048_576))

    private fun record(code: String) {
        tick += 1
        diagnostics.record(
            DiagnosticEvent(tick, DiagnosticComponent.APPLICATION, code, 1),
        )
    }

    private fun fail(code: String) {
        errorCode = code
        record(code)
    }

    private fun clearError() {
        errorCode = null
    }

    private companion object {
        const val FIXTURE_BYTES = 70_000
        const val FIXTURE_CHUNKS = 2
        const val SIMULATED_PEER = "simulated-peer"
    }
}
