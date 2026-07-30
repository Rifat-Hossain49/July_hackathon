package org.shongket.semantic

enum class Urgency {
    NORMAL,
    IMPORTANT,
    CRITICAL,
}

enum class CapsuleProvenance {
    MANUAL,
    MODEL_SUGGESTION,
}

data class CapsuleDraft(
    val eventType: String,
    val locationText: String,
    val urgency: Urgency,
    val affectedPeople: Int?,
    val requiredAction: String,
    val requiredResource: String,
    val summaryBn: String,
    val summaryMixed: String,
    val sourceObjectId: String,
    val provenance: CapsuleProvenance,
    val uncertainFields: Set<String>,
    val humanConfirmed: Boolean = false,
) {
    fun validate() {
        require(eventType.length in 1..64)
        require(locationText.length in 1..256)
        require(affectedPeople == null || affectedPeople in 0..1_000_000)
        require(requiredAction.length <= 512)
        require(requiredResource.length <= 256)
        require(summaryBn.length in 1..1_024)
        require(summaryMixed.length <= 1_024)
        require(sourceObjectId.matches(Regex("[0-9a-f]{64}")))
        require(uncertainFields.size <= 16)
        require(uncertainFields.all { it.matches(Regex("[a-z][a-z_]{0,31}")) })
    }

    fun confirmed(): CapsuleDraft = copy(humanConfirmed = true).also { it.validate() }
}

data class SemanticSource(
    val objectId: String,
    val modality: String,
) {
    fun validate() {
        require(objectId.matches(Regex("[0-9a-f]{64}")))
        require(modality.matches(Regex("[A-Z]{3,16}")))
    }
}

sealed interface PublishResult {
    data class Scheduled(val capsule: CapsuleDraft) : PublishResult
    data class Refused(val reasonCode: String) : PublishResult
}
