package org.shongket.data.persistence

/**
 * Port implemented by the Android background/service layer in the transport
 * slice. Durable state does not assume that an Android service is immortal.
 */
fun interface BackgroundTransferPort {
    fun resume(plan: ResumePlan)
}

data class SavedUiIdentifiers(
    val activeTransferId: String?,
)

data class LifecycleRecovery(
    val activeTransferId: String?,
    val verifiedFragments: Int,
    val expectedFragments: Int,
    val missingIndexes: List<Int>,
)

class TransferLifecycleCoordinator(
    private val repository: DurableTransferRepository,
) {
    fun recover(
        savedUi: SavedUiIdentifiers,
        backgroundTransfer: BackgroundTransferPort,
    ): LifecycleRecovery {
        val snapshot = repository.currentSnapshot()
        val durableId = snapshot?.transferId
        val activeId = if (savedUi.activeTransferId == durableId) {
            savedUi.activeTransferId
        } else {
            durableId
        }
        repository.resumePlan()
            ?.takeIf { it.missingIndexes.isNotEmpty() }
            ?.let(backgroundTransfer::resume)
        return LifecycleRecovery(
            activeTransferId = activeId,
            verifiedFragments = snapshot?.fragments?.size ?: 0,
            expectedFragments = snapshot?.expectedFragments ?: 0,
            missingIndexes = snapshot?.missingIndexes ?: emptyList(),
        )
    }
}
