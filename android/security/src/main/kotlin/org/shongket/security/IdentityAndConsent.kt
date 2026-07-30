package org.shongket.security

import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

interface PlatformKeyStorePort {
    fun sign(alias: String, payload: ByteArray): ByteArray
    fun verify(alias: String, payload: ByteArray, signature: ByteArray): Boolean
}

class UnavailablePlatformKeyStore : PlatformKeyStorePort {
    override fun sign(alias: String, payload: ByteArray): ByteArray =
        error("platform key store is unavailable")

    override fun verify(alias: String, payload: ByteArray, signature: ByteArray): Boolean = false
}

/**
 * Test-only identity implementation. Key bytes are injected by the test and
 * are never loaded from source, assets, preferences, or diagnostics.
 */
class InjectedDevelopmentIdentity(
    private val keyByAlias: Map<String, ByteArray>,
) : PlatformKeyStorePort {
    override fun sign(alias: String, payload: ByteArray): ByteArray =
        hmac(keyByAlias[alias] ?: error("unknown development alias"), payload)

    override fun verify(
        alias: String,
        payload: ByteArray,
        signature: ByteArray,
    ): Boolean {
        val key = keyByAlias[alias] ?: return false
        return MessageDigest.isEqual(hmac(key, payload), signature)
    }

    private fun hmac(key: ByteArray, payload: ByteArray): ByteArray {
        require(key.size >= 16) { "development key is too short" }
        require(payload.size <= MAX_APPLICATION_PAYLOAD_BYTES) { "payload exceeds limit" }
        return Mac.getInstance("HmacSHA256").run {
            init(SecretKeySpec(key, "HmacSHA256"))
            doFinal(payload)
        }
    }
}

object SignedMetadataGate {
    fun verify(
        keyStore: PlatformKeyStorePort,
        expectedAlias: String,
        claimedAlias: String,
        canonicalPayload: ByteArray,
        signature: ByteArray,
    ): String? {
        if (claimedAlias != expectedAlias) return "SIGNATURE_INVALID"
        if (!keyStore.verify(expectedAlias, canonicalPayload, signature)) {
            return "SIGNATURE_INVALID"
        }
        return null
    }
}

sealed interface ConsentDecision {
    data object Allowed : ConsentDecision
    data class Refused(val code: String) : ConsentDecision
}

object PrivateForwardConsentGate {
    fun evaluate(
        isPrivate: Boolean,
        explicitlyConfirmed: Boolean,
        peerAcceptsPrivate: Boolean,
    ): ConsentDecision {
        if (!isPrivate) return ConsentDecision.Allowed
        if (!explicitlyConfirmed) return ConsentDecision.Refused("CONSENT_REQUIRED")
        if (!peerAcceptsPrivate) return ConsentDecision.Refused("PEER_PUBLIC_ONLY")
        return ConsentDecision.Allowed
    }
}
