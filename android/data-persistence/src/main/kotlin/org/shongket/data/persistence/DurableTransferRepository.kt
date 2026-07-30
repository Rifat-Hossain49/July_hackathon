package org.shongket.data.persistence

class DurableTransferRepository(
    private val stateStore: AppPrivateStateStore,
) {
    private var snapshot: TransferSnapshot? = stateStore.load().snapshot

    @Synchronized
    fun currentSnapshot(): TransferSnapshot? = snapshot

    @Synchronized
    fun begin(
        transferId: String,
        objectId: String,
        representationId: String,
        expectedFragments: Int,
        capacityBytes: Long,
    ): TransferSnapshot {
        val candidate = TransferSnapshot(
            transferId = transferId,
            objectId = objectId,
            representationId = representationId,
            expectedFragments = expectedFragments,
            capacityBytes = capacityBytes,
            fragments = emptyList(),
        ).also { it.validate() }
        stateStore.save(candidate)
        snapshot = candidate
        return candidate
    }

    @Synchronized
    fun ingest(fragment: VerifiedFragment): IngestResult {
        val current = snapshot ?: return IngestResult.NoActiveTransfer
        if (
            fragment.objectId != current.objectId ||
            fragment.representationId != current.representationId ||
            fragment.chunkIndex !in 0 until current.expectedFragments
        ) {
            return IngestResult.TransferMismatch
        }
        try {
            fragment.validate(current.expectedFragments)
        } catch (_: IllegalArgumentException) {
            return IngestResult.IntegrityRejected
        }

        val existing = current.fragments.firstOrNull {
            it.chunkIndex == fragment.chunkIndex
        }
        if (existing != null) {
            return if (
                existing.sha256 == fragment.sha256 &&
                existing.payloadBase64 == fragment.payloadBase64
            ) {
                IngestResult.Duplicate
            } else {
                IngestResult.IntegrityRejected
            }
        }

        val prospectiveBytes = current.usedBytes + fragment.byteLength
        if (prospectiveBytes > current.capacityBytes) {
            return IngestResult.OutOfBudget(
                usedBytes = current.usedBytes,
                capacityBytes = current.capacityBytes,
                incomingBytes = fragment.byteLength.toLong(),
            )
        }
        val candidate = current.copy(
            fragments = (current.fragments + fragment).sortedBy { it.chunkIndex },
        ).also { it.validate() }
        stateStore.save(candidate)
        snapshot = candidate
        return IngestResult.Accepted(candidate)
    }

    @Synchronized
    fun resumePlan(): ResumePlan? = snapshot?.let {
        ResumePlan(
            transferId = it.transferId,
            objectId = it.objectId,
            representationId = it.representationId,
            missingIndexes = it.missingIndexes,
        )
    }
}

sealed interface IngestResult {
    data class Accepted(val snapshot: TransferSnapshot) : IngestResult
    data object Duplicate : IngestResult
    data object NoActiveTransfer : IngestResult
    data object TransferMismatch : IngestResult
    data object IntegrityRejected : IngestResult

    data class OutOfBudget(
        val usedBytes: Long,
        val capacityBytes: Long,
        val incomingBytes: Long,
    ) : IngestResult
}
