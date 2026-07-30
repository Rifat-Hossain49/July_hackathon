package org.shongket.data.transport

import org.shongket.data.persistence.BackgroundTransferPort
import org.shongket.data.persistence.ResumePlan

class BackgroundTransferCoordinator(
    private val adapter: TransportAdapter,
) : BackgroundTransferPort {
    override fun resume(plan: ResumePlan) {
        require(plan.missingIndexes.size <= 65_536) { "resume plan exceeds limit" }
        val result = adapter.resume(plan.missingIndexes)
        check(result is TransportResult.Accepted) { "background resume was refused" }
    }
}
