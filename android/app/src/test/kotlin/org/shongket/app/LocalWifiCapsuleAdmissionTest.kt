package org.shongket.app

import org.junit.Assert.assertEquals
import org.junit.Test
import org.shongket.data.transport.LocalWifiCapsule
import org.shongket.data.transport.LocalWifiUrgency
import org.shongket.data.transport.LocalWifiVisibility

class LocalWifiCapsuleAdmissionTest {
    @Test
    fun validHumanConfirmedCapsuleIsAccepted() {
        assertEquals(
            LocalWifiAdmissionDecision.Allowed,
            LocalWifiCapsuleAdmission.evaluate(fixture(), NOW),
        )
    }

    @Test
    fun unconfirmedPrivateAndExpiredCapsulesAreRefused() {
        assertEquals(
            LocalWifiAdmissionDecision.Refused("HUMAN_CONFIRMATION_REQUIRED"),
            LocalWifiCapsuleAdmission.evaluate(fixture().copy(humanConfirmed = false), NOW),
        )
        assertEquals(
            LocalWifiAdmissionDecision.Refused("CONSENT_REQUIRED"),
            LocalWifiCapsuleAdmission.evaluate(
                fixture().copy(
                    visibility = LocalWifiVisibility.PRIVATE,
                    forwardingConsent = false,
                ),
                NOW,
            ),
        )
        assertEquals(
            LocalWifiAdmissionDecision.Refused("CAPSULE_EXPIRED"),
            LocalWifiCapsuleAdmission.evaluate(fixture().copy(expiresAtEpochSeconds = NOW), NOW),
        )
    }

    @Test
    fun blankAndImplausiblyFutureCapsulesAreRefused() {
        assertEquals(
            LocalWifiAdmissionDecision.Refused("MESSAGE_REQUIRED"),
            LocalWifiCapsuleAdmission.evaluate(fixture().copy(message = " "), NOW),
        )
        assertEquals(
            LocalWifiAdmissionDecision.Refused("LOCATION_REQUIRED"),
            LocalWifiCapsuleAdmission.evaluate(fixture().copy(location = ""), NOW),
        )
        assertEquals(
            LocalWifiAdmissionDecision.Refused("CREATED_AT_IN_FUTURE"),
            LocalWifiCapsuleAdmission.evaluate(
                fixture().copy(createdAtEpochSeconds = NOW + 301),
                NOW,
            ),
        )
    }

    private fun fixture(): LocalWifiCapsule =
        LocalWifiCapsule(
            senderLabel = "Shongket-test",
            message = "water needed",
            location = "east bank",
            urgency = LocalWifiUrgency.IMPORTANT,
            visibility = LocalWifiVisibility.PUBLIC,
            humanConfirmed = true,
            forwardingConsent = false,
            createdAtEpochSeconds = NOW - 10,
            expiresAtEpochSeconds = NOW + 3_600,
        )

    private companion object {
        const val NOW = 1_800_000_000L
    }
}
