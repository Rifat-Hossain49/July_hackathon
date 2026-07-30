package org.shongket.semantic

enum class SemanticEvent {
    MANUAL_FORM_OPENED,
    SUGGESTION_PRESENTED,
    HUMAN_CONFIRMED,
    PUBLISH_SCHEDULED,
    PUBLISH_REFUSED,
}

data class SemanticFlow(
    val draft: CapsuleDraft?,
    val manualFormVisible: Boolean,
    val events: List<SemanticEvent>,
)

class ManualCapsuleWorkflow(
    private val extractor: SemanticExtractor = UnavailableSemanticExtractor(),
) {
    fun start(source: SemanticSource): SemanticFlow =
        when (val result = extractor.extract(source)) {
            is ExtractionResult.Suggested -> SemanticFlow(
                draft = result.draft,
                manualFormVisible = true,
                events = listOf(SemanticEvent.SUGGESTION_PRESENTED),
            )
            is ExtractionResult.Unavailable, ExtractionResult.Cancelled -> SemanticFlow(
                draft = null,
                manualFormVisible = true,
                events = listOf(SemanticEvent.MANUAL_FORM_OPENED),
            )
        }

    fun manualDraft(
        source: SemanticSource,
        eventType: String,
        locationText: String,
        urgency: Urgency,
        requiredAction: String,
        summaryBn: String,
    ): CapsuleDraft {
        source.validate()
        return CapsuleDraft(
            eventType = eventType,
            locationText = locationText,
            urgency = urgency,
            affectedPeople = null,
            requiredAction = requiredAction,
            requiredResource = "",
            summaryBn = summaryBn,
            summaryMixed = "",
            sourceObjectId = source.objectId,
            provenance = CapsuleProvenance.MANUAL,
            uncertainFields = emptySet(),
        ).also { it.validate() }
    }

    fun publish(draft: CapsuleDraft): PublishResult {
        draft.validate()
        return if (draft.humanConfirmed) {
            PublishResult.Scheduled(draft)
        } else {
            PublishResult.Refused("HUMAN_CONFIRMATION_REQUIRED")
        }
    }
}
