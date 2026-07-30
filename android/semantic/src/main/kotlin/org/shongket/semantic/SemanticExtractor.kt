package org.shongket.semantic

fun interface CancellationSignal {
    fun isCancelled(): Boolean
}

sealed interface ExtractionResult {
    data class Suggested(val draft: CapsuleDraft) : ExtractionResult
    data class Unavailable(val reasonCode: String) : ExtractionResult
    data object Cancelled : ExtractionResult
}

interface SemanticExtractor {
    fun extract(
        source: SemanticSource,
        cancellation: CancellationSignal = CancellationSignal { false },
    ): ExtractionResult
}

class UnavailableSemanticExtractor : SemanticExtractor {
    override fun extract(
        source: SemanticSource,
        cancellation: CancellationSignal,
    ): ExtractionResult {
        source.validate()
        return if (cancellation.isCancelled()) {
            ExtractionResult.Cancelled
        } else {
            ExtractionResult.Unavailable("MODEL_NOT_INSTALLED")
        }
    }
}

/**
 * Pure deterministic double. It accepts metadata only and has no network,
 * download, filesystem, or model-runtime dependency.
 */
class DeterministicSemanticTestDouble : SemanticExtractor {
    override fun extract(
        source: SemanticSource,
        cancellation: CancellationSignal,
    ): ExtractionResult {
        source.validate()
        if (cancellation.isCancelled()) return ExtractionResult.Cancelled
        return ExtractionResult.Suggested(
            CapsuleDraft(
                eventType = "needs_assessment",
                locationText = "location needs confirmation",
                urgency = Urgency.IMPORTANT,
                affectedPeople = null,
                requiredAction = "review source evidence",
                requiredResource = "",
                summaryBn = "মানুষের যাচাই প্রয়োজন",
                summaryMixed = "Human review required",
                sourceObjectId = source.objectId,
                provenance = CapsuleProvenance.MODEL_SUGGESTION,
                uncertainFields = setOf("event_type", "location_text"),
            ).also { it.validate() },
        )
    }
}
