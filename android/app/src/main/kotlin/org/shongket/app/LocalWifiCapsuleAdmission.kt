package org.shongket.app

sealed interface LocalWifiAdmissionDecision {
    data object Allowed : LocalWifiAdmissionDecision
    data class Refused(val code: String) : LocalWifiAdmissionDecision
}

object LocalWifiCapsuleAdmission {
    fun evaluate(
        capsule: LocalWifiCapsule,
        nowEpochSeconds: Long,
    ): LocalWifiAdmissionDecision {
        if (!capsule.humanConfirmed) return refused("HUMAN_CONFIRMATION_REQUIRED")
        if (capsule.message.isBlank()) return refused("MESSAGE_REQUIRED")
        if (capsule.location.isBlank()) return refused("LOCATION_REQUIRED")
        if (
            capsule.visibility == LocalWifiVisibility.PRIVATE &&
            !capsule.forwardingConsent
        ) {
            return refused("CONSENT_REQUIRED")
        }
        if (capsule.createdAtEpochSeconds > nowEpochSeconds + FUTURE_TOLERANCE_SECONDS) {
            return refused("CREATED_AT_IN_FUTURE")
        }
        if (capsule.expiresAtEpochSeconds <= nowEpochSeconds) {
            return refused("CAPSULE_EXPIRED")
        }
        return LocalWifiAdmissionDecision.Allowed
    }

    private fun refused(code: String): LocalWifiAdmissionDecision =
        LocalWifiAdmissionDecision.Refused(code)

    private const val FUTURE_TOLERANCE_SECONDS = 5 * 60L
}
