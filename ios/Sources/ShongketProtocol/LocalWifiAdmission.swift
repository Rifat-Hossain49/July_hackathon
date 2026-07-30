import Foundation

public enum LocalWifiAdmissionDecision: Equatable {
    case allowed
    case refused(String)
}

public enum LocalWifiCapsuleAdmission {
    private static let futureToleranceSeconds: Int64 = 5 * 60

    public static func evaluate(
        _ capsule: LocalWifiCapsule,
        nowEpochSeconds: Int64
    ) -> LocalWifiAdmissionDecision {
        guard capsule.humanConfirmed else {
            return .refused("HUMAN_CONFIRMATION_REQUIRED")
        }
        guard !capsule.message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return .refused("MESSAGE_REQUIRED")
        }
        guard !capsule.location.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return .refused("LOCATION_REQUIRED")
        }
        if capsule.visibility == .private && !capsule.forwardingConsent {
            return .refused("CONSENT_REQUIRED")
        }
        guard capsule.createdAtEpochSeconds <= nowEpochSeconds + futureToleranceSeconds else {
            return .refused("CREATED_AT_IN_FUTURE")
        }
        guard capsule.expiresAtEpochSeconds > nowEpochSeconds else {
            return .refused("CAPSULE_EXPIRED")
        }
        return .allowed
    }
}
