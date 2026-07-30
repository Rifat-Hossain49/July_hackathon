package org.shongket.data.transport

const val MAX_TRANSPORT_FRAME_BYTES: Int = 1_048_576
const val MAX_EVENT_COUNT: Int = 4_096

data class TransportCapabilities(
    val protocolVersions: Set<Int>,
    val maxPayloadBytes: Int,
) {
    fun validate() {
        require(protocolVersions.isNotEmpty()) { "at least one protocol version is required" }
        require(protocolVersions.size <= 16) { "too many protocol versions" }
        require(protocolVersions.all { it in 1..255 }) { "invalid protocol version" }
        require(maxPayloadBytes in 1..MAX_TRANSPORT_FRAME_BYTES) {
            "payload limit is outside the transport boundary"
        }
    }
}

data class NegotiatedCapabilities(
    val protocolVersion: Int,
    val maxPayloadBytes: Int,
)

enum class TransportEventType {
    DISCOVERY_STARTED,
    PEER_FOUND,
    CONNECTED,
    CAPABILITIES_EXCHANGED,
    FRAME_SENT,
    FRAME_RECEIVED,
    INTERRUPTED,
    RESUMED,
    CLOSED,
    REFUSED,
}

data class TransportEvent(
    val type: TransportEventType,
    val code: String,
)

sealed interface TransportResult {
    data object Accepted : TransportResult
    data class Refused(val code: String) : TransportResult
}

sealed interface NegotiationResult {
    data class Accepted(val capabilities: NegotiatedCapabilities) : NegotiationResult
    data class Refused(val code: String) : NegotiationResult
}

interface TransportAdapter {
    val adapterId: String
    val capabilities: TransportCapabilities

    fun discover(): TransportResult
    fun connect(peerId: String, peerCapabilities: TransportCapabilities): NegotiationResult
    fun send(frame: ByteArray): TransportResult
    fun receive(frame: ByteArray): TransportResult
    fun interrupt(): TransportResult
    fun resume(missingIndexes: List<Int>): TransportResult
    fun close(): TransportResult
    fun events(): List<TransportEvent>
}
