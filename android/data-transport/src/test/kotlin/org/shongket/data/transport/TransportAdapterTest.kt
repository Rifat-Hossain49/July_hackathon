package org.shongket.data.transport

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.shongket.data.persistence.ResumePlan

class TransportAdapterTest {
    private val local = TransportCapabilities(setOf(1, 2), 1_024)
    private val remote = TransportCapabilities(setOf(2, 3), 512)

    @Test
    fun softwareAdaptersProduceTheSameObservableSequence() {
        val adapters = listOf(
            SimulatedTransportAdapter(local),
            InProcessAndroidTransportAdapter(local),
        )
        adapters.forEach { exercise(it) }
        assertEquals(adapters[0].events(), adapters[1].events())
    }

    @Test
    fun negotiationUsesHighestCommonVersionAndLowerPayloadLimit() {
        val adapter = SimulatedTransportAdapter(local)
        val result = adapter.connect("peer-1", remote)
        assertEquals(
            NegotiationResult.Accepted(NegotiatedCapabilities(2, 512)),
            result,
        )
    }

    @Test
    fun oversizedPayloadIsRefusedBeforeTransmission() {
        val adapter = SimulatedTransportAdapter(local)
        adapter.connect("peer-1", remote)
        assertEquals(
            TransportResult.Refused("PAYLOAD_TOO_LARGE"),
            adapter.send(ByteArray(513)),
        )
        assertTrue(adapter.events().none { it.type == TransportEventType.FRAME_SENT })
    }

    @Test
    fun incompatibleProtocolDeclinesWithoutCrash() {
        val adapter = SimulatedTransportAdapter(local)
        assertEquals(
            NegotiationResult.Refused("INCOMPATIBLE_PROTOCOL"),
            adapter.connect("peer-1", TransportCapabilities(setOf(7), 128)),
        )
    }

    @Test
    fun eachPermissionCanBeRefusedWithoutRetry() {
        DevicePermission.entries.forEach { denied ->
            val states = DevicePermission.entries.associateWith {
                if (it == denied) PermissionState.DENIED else PermissionState.GRANTED
            }
            assertEquals(
                PermissionDecision.Blocked(denied, "PERMISSION_DENIED"),
                PermissionGate.evaluate(DevicePermission.entries.toSet(), states),
            )
        }
    }

    @Test
    fun provisionalAdapterNeverClaimsRadioReadiness() {
        val states = DevicePermission.entries.associateWith { PermissionState.GRANTED }
        assertEquals(
            AdapterAvailability.Unavailable("FIELD_VALIDATION_REQUIRED"),
            ProvisionalNearbyAdapter().availability(DevicePermission.entries.toSet(), states),
        )
    }

    @Test
    fun backgroundCoordinatorRequestsOnlyPersistedMissingIndexes() {
        val adapter = SimulatedTransportAdapter(local)
        BackgroundTransferCoordinator(adapter).resume(
            ResumePlan(
                transferId = "transfer-1",
                objectId = "0".repeat(64),
                representationId = "source",
                missingIndexes = listOf(1, 3),
            ),
        )
        assertTrue(
            adapter.events().contains(
                TransportEvent(TransportEventType.RESUMED, "MISSING_2"),
            ),
        )
    }

    private fun exercise(adapter: TransportAdapter) {
        adapter.discover()
        adapter.connect("peer-1", remote)
        adapter.send(byteArrayOf(1))
        adapter.receive(byteArrayOf(2))
        adapter.interrupt()
        adapter.resume(listOf(1, 3))
        adapter.close()
    }
}
