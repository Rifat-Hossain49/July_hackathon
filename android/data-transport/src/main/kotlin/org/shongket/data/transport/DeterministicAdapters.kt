package org.shongket.data.transport

private val PEER_ID = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,63}")

abstract class DeterministicTransportAdapter(
    final override val adapterId: String,
    final override val capabilities: TransportCapabilities,
) : TransportAdapter {
    private val eventLog = mutableListOf<TransportEvent>()
    private var negotiated: NegotiatedCapabilities? = null
    private var connected = false

    init {
        require(PEER_ID.matches(adapterId)) { "invalid adapter id" }
        capabilities.validate()
    }

    final override fun discover(): TransportResult {
        record(TransportEventType.DISCOVERY_STARTED, "DISCOVERY")
        record(TransportEventType.PEER_FOUND, "DETERMINISTIC_PEER")
        return TransportResult.Accepted
    }

    final override fun connect(
        peerId: String,
        peerCapabilities: TransportCapabilities,
    ): NegotiationResult {
        if (!PEER_ID.matches(peerId)) {
            return refuseNegotiation("INVALID_PEER")
        }
        try {
            peerCapabilities.validate()
        } catch (_: IllegalArgumentException) {
            return refuseNegotiation("INVALID_CAPABILITIES")
        }
        val version = capabilities.protocolVersions
            .intersect(peerCapabilities.protocolVersions)
            .maxOrNull()
            ?: return refuseNegotiation("INCOMPATIBLE_PROTOCOL")
        val result = NegotiatedCapabilities(
            protocolVersion = version,
            maxPayloadBytes = minOf(
                capabilities.maxPayloadBytes,
                peerCapabilities.maxPayloadBytes,
            ),
        )
        connected = true
        negotiated = result
        record(TransportEventType.CONNECTED, "CONNECTED")
        record(TransportEventType.CAPABILITIES_EXCHANGED, "NEGOTIATED")
        return NegotiationResult.Accepted(result)
    }

    final override fun send(frame: ByteArray): TransportResult =
        acceptFrame(frame, TransportEventType.FRAME_SENT)

    final override fun receive(frame: ByteArray): TransportResult =
        acceptFrame(frame, TransportEventType.FRAME_RECEIVED)

    final override fun interrupt(): TransportResult {
        if (!connected) return refuse("NOT_CONNECTED")
        connected = false
        record(TransportEventType.INTERRUPTED, "INTERRUPTED")
        return TransportResult.Accepted
    }

    final override fun resume(missingIndexes: List<Int>): TransportResult {
        if (
            missingIndexes.size > 65_536 ||
            missingIndexes.any { it < 0 } ||
            missingIndexes.toSet().size != missingIndexes.size
        ) {
            return refuse("INVALID_RESUME_PLAN")
        }
        connected = true
        record(TransportEventType.RESUMED, "MISSING_${missingIndexes.size}")
        return TransportResult.Accepted
    }

    final override fun close(): TransportResult {
        connected = false
        negotiated = null
        record(TransportEventType.CLOSED, "CLOSED")
        return TransportResult.Accepted
    }

    final override fun events(): List<TransportEvent> = eventLog.toList()

    private fun acceptFrame(
        frame: ByteArray,
        eventType: TransportEventType,
    ): TransportResult {
        val session = negotiated ?: return refuse("NOT_NEGOTIATED")
        if (frame.isEmpty()) return refuse("EMPTY_FRAME")
        if (frame.size > session.maxPayloadBytes) return refuse("PAYLOAD_TOO_LARGE")
        record(eventType, "BYTES_${frame.size}")
        return TransportResult.Accepted
    }

    private fun refuse(code: String): TransportResult {
        record(TransportEventType.REFUSED, code)
        return TransportResult.Refused(code)
    }

    private fun refuseNegotiation(code: String): NegotiationResult {
        record(TransportEventType.REFUSED, code)
        return NegotiationResult.Refused(code)
    }

    private fun record(type: TransportEventType, code: String) {
        require(eventLog.size < MAX_EVENT_COUNT) { "transport event limit reached" }
        eventLog += TransportEvent(type, code)
    }
}

class SimulatedTransportAdapter(
    capabilities: TransportCapabilities,
) : DeterministicTransportAdapter("simulated", capabilities)

class InProcessAndroidTransportAdapter(
    capabilities: TransportCapabilities,
) : DeterministicTransportAdapter("android-software", capabilities)
