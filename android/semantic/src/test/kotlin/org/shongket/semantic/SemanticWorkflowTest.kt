package org.shongket.semantic

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SemanticWorkflowTest {
    private val source = SemanticSource("a".repeat(64), "PHOTO")

    @Test
    fun deterministicDoubleReturnsIdenticalSuggestionsWithoutRuntimeIo() {
        val extractor = DeterministicSemanticTestDouble()
        assertEquals(extractor.extract(source), extractor.extract(source))
    }

    @Test
    fun unavailableDefaultOpensManualFormAsNormalFlow() {
        val flow = ManualCapsuleWorkflow().start(source)
        assertTrue(flow.manualFormVisible)
        assertEquals(null, flow.draft)
        assertEquals(listOf(SemanticEvent.MANUAL_FORM_OPENED), flow.events)
    }

    @Test
    fun manualCapsuleCanBeConfirmedAndScheduledWithoutModel() {
        val workflow = ManualCapsuleWorkflow()
        val draft = workflow.manualDraft(
            source,
            eventType = "flood",
            locationText = "নদীর পাশের গ্রাম",
            urgency = Urgency.CRITICAL,
            requiredAction = "send clean water",
            summaryBn = "পানি প্রয়োজন",
        )
        val result = workflow.publish(draft.confirmed())
        assertTrue(result is PublishResult.Scheduled)
    }

    @Test
    fun unconfirmedSuggestionCanNeverBePublished() {
        val draft = (
            DeterministicSemanticTestDouble().extract(source) as ExtractionResult.Suggested
        ).draft
        assertEquals(
            PublishResult.Refused("HUMAN_CONFIRMATION_REQUIRED"),
            ManualCapsuleWorkflow().publish(draft),
        )
        assertFalse(draft.humanConfirmed)
    }

    @Test
    fun suggestionRetainsSourceLinkAndGeneratedProvenance() {
        val draft = (
            DeterministicSemanticTestDouble().extract(source) as ExtractionResult.Suggested
        ).draft
        assertEquals(source.objectId, draft.sourceObjectId)
        assertEquals(CapsuleProvenance.MODEL_SUGGESTION, draft.provenance)
        assertTrue(draft.uncertainFields.isNotEmpty())
    }

    @Test
    fun cancellationReturnsWithoutPartialSuggestion() {
        assertEquals(
            ExtractionResult.Cancelled,
            DeterministicSemanticTestDouble().extract(source) { true },
        )
    }
}
