package org.shongket.security

const val MAX_REPLAY_ENTRIES_PER_PEER: Int = 1_024
const val MAX_DUPLICATES_PER_SESSION: Int = 4_096

sealed interface ReplayDecision {
    data object Accepted : ReplayDecision
    data class Refused(val code: String) : ReplayDecision
}

class ReplayGuard {
    private val seenByPeer = mutableMapOf<String, LinkedHashSet<String>>()
    private var duplicateCount = 0

    fun evaluate(
        peerTag: String,
        objectId: String,
        expiresTick: Long,
        currentTick: Long,
    ): ReplayDecision {
        require(peerTag.matches(Regex("[0-9a-f]{16}"))) { "peer tag must be redacted" }
        require(objectId.matches(Regex("[0-9a-f]{64}"))) { "invalid object id" }
        if (expiresTick < currentTick) return ReplayDecision.Refused("EXPIRED")
        val seen = seenByPeer.getOrPut(peerTag) { linkedSetOf() }
        if (objectId in seen) {
            duplicateCount += 1
            if (duplicateCount > MAX_DUPLICATES_PER_SESSION) {
                return ReplayDecision.Refused("RESOURCE_LIMIT")
            }
            return ReplayDecision.Refused("DUPLICATE")
        }
        if (seen.size >= MAX_REPLAY_ENTRIES_PER_PEER) {
            return ReplayDecision.Refused("RESOURCE_LIMIT")
        }
        seen += objectId
        return ReplayDecision.Accepted
    }

    fun storedEntries(): Int = seenByPeer.values.sumOf { it.size }
}
