package org.shongket.data.transport

import java.security.MessageDigest

const val LOCAL_WIFI_PROTOCOL_VERSION: Int = 1
const val MAX_LOCAL_WIFI_FRAME_BYTES: Int = 8_192

class LocalWifiTransportException(
    val code: String,
) : IllegalArgumentException(code)

internal fun sha256(value: ByteArray): ByteArray =
    MessageDigest.getInstance("SHA-256").digest(value)

internal fun ByteArray.toHex(): String =
    joinToString(separator = "") { byte -> "%02x".format(byte.toInt() and 0xff) }
