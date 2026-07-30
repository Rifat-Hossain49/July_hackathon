package org.shongket.data.transport

enum class DevicePermission {
    NEARBY_DEVICES,
    LOCATION_COMPATIBILITY,
}

enum class PermissionState {
    GRANTED,
    DENIED,
    NOT_REQUESTED,
}

sealed interface PermissionDecision {
    data object Allowed : PermissionDecision
    data class Blocked(
        val permission: DevicePermission,
        val reasonCode: String,
    ) : PermissionDecision
}

object PermissionGate {
    fun evaluate(
        required: Set<DevicePermission>,
        states: Map<DevicePermission, PermissionState>,
    ): PermissionDecision {
        for (permission in required.sortedBy { it.name }) {
            when (states[permission] ?: PermissionState.NOT_REQUESTED) {
                PermissionState.GRANTED -> Unit
                PermissionState.DENIED -> {
                    return PermissionDecision.Blocked(permission, "PERMISSION_DENIED")
                }
                PermissionState.NOT_REQUESTED -> {
                    return PermissionDecision.Blocked(permission, "PERMISSION_NOT_REQUESTED")
                }
            }
        }
        return PermissionDecision.Allowed
    }
}

sealed interface AdapterAvailability {
    data object Ready : AdapterAvailability
    data class Unavailable(val reasonCode: String) : AdapterAvailability
}

/**
 * Compilation boundary for a possible Nearby implementation. It performs no
 * radio operation and remains unavailable until the separately approved
 * physical smoke-test gate is completed.
 */
class ProvisionalNearbyAdapter {
    fun availability(
        required: Set<DevicePermission>,
        states: Map<DevicePermission, PermissionState>,
    ): AdapterAvailability =
        when (val decision = PermissionGate.evaluate(required, states)) {
            PermissionDecision.Allowed ->
                AdapterAvailability.Unavailable("FIELD_VALIDATION_REQUIRED")
            is PermissionDecision.Blocked ->
                AdapterAvailability.Unavailable(decision.reasonCode)
        }
}
