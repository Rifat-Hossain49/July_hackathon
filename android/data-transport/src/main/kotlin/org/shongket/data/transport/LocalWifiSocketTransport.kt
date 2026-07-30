package org.shongket.data.transport

import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.Closeable
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.EOFException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.RejectedExecutionException
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

data class LocalWifiPeerEndpoint(
    val serviceName: String,
    val address: InetAddress,
    val port: Int,
    val protocolVersion: Int = LOCAL_WIFI_PROTOCOL_VERSION,
    val maxPayloadBytes: Int = MAX_LOCAL_WIFI_FRAME_BYTES,
) {
    init {
        require(
            serviceName.length in 1..64 &&
                serviceName.all { character -> !character.isISOControl() },
        ) {
            "invalid service name"
        }
        require(port in 1..65_535) { "invalid port" }
        require(protocolVersion in 1..255) { "invalid protocol version" }
        require(maxPayloadBytes in 1..MAX_LOCAL_WIFI_FRAME_BYTES) {
            "invalid payload boundary"
        }
    }
}

sealed interface LocalWifiReceiveDecision {
    data object Accepted : LocalWifiReceiveDecision
    data class Refused(val code: String) : LocalWifiReceiveDecision
}

sealed interface LocalWifiSendResult {
    data class Accepted(
        val frameId: String,
        val duplicate: Boolean,
    ) : LocalWifiSendResult

    data class Refused(val code: String) : LocalWifiSendResult
}

fun interface LocalWifiFrameReceiver {
    fun receive(frame: ByteArray, remoteAddress: InetAddress): LocalWifiReceiveDecision
}

object LocalNetworkAddress {
    fun isAllowed(address: InetAddress): Boolean {
        if (address.isLoopbackAddress || address.isLinkLocalAddress || address.isSiteLocalAddress) {
            return true
        }
        val bytes = address.address
        return bytes.size == 16 && (bytes[0].toInt() and 0xfe) == 0xfc
    }
}

class LocalWifiSocketServer(
    private val receiver: LocalWifiFrameReceiver,
) : Closeable {
    private val running = AtomicBoolean(false)
    private val recentFrameIds = LinkedHashSet<String>()
    private var serverSocket: ServerSocket? = null
    private var acceptExecutor: ThreadPoolExecutor? = null
    private var workerExecutor: ThreadPoolExecutor? = null

    @Synchronized
    fun start(requestedPort: Int = 0): Int {
        check(!running.get()) { "server already started" }
        require(requestedPort in 0..65_535) { "invalid requested port" }
        val socket = ServerSocket()
        socket.reuseAddress = true
        socket.bind(InetSocketAddress(requestedPort), SERVER_BACKLOG)
        serverSocket = socket
        acceptExecutor = boundedExecutor(1, 1, "shongket-wifi-accept")
        workerExecutor = boundedExecutor(2, WORK_QUEUE_CAPACITY, "shongket-wifi-worker")
        running.set(true)
        acceptExecutor?.execute(::acceptLoop)
        return socket.localPort
    }

    override fun close() {
        running.set(false)
        runCatching { serverSocket?.close() }
        acceptExecutor?.shutdownNow()
        workerExecutor?.shutdownNow()
        serverSocket = null
        acceptExecutor = null
        workerExecutor = null
        synchronized(recentFrameIds) { recentFrameIds.clear() }
    }

    private fun acceptLoop() {
        while (running.get()) {
            val socket = try {
                serverSocket?.accept() ?: return
            } catch (_: Exception) {
                if (!running.get()) return
                continue
            }
            try {
                workerExecutor?.execute { handle(socket) } ?: socket.close()
            } catch (_: RejectedExecutionException) {
                runCatching { socket.close() }
            }
        }
    }

    private fun handle(socket: Socket) {
        socket.use { active ->
            active.soTimeout = SOCKET_TIMEOUT_MILLIS
            val remote = active.inetAddress
            if (!LocalNetworkAddress.isAllowed(remote)) return
            val input = BufferedInputStream(active.getInputStream())
            val output = BufferedOutputStream(active.getOutputStream())
            val frame = try {
                LocalWifiFraming.read(input)
            } catch (_: Exception) {
                return
            }
            val frameId = sha256(frame).toHex()
            if (isDuplicate(frameId)) {
                LocalWifiFraming.writeAck(output, frameId, AckStatus.DUPLICATE)
                return
            }
            when (receiver.receive(frame.copyOf(), remote)) {
                LocalWifiReceiveDecision.Accepted -> {
                    remember(frameId)
                    LocalWifiFraming.writeAck(output, frameId, AckStatus.ACCEPTED)
                }
                is LocalWifiReceiveDecision.Refused -> {
                    LocalWifiFraming.writeAck(output, frameId, AckStatus.REFUSED)
                }
            }
        }
    }

    private fun isDuplicate(frameId: String): Boolean =
        synchronized(recentFrameIds) { frameId in recentFrameIds }

    private fun remember(frameId: String) {
        synchronized(recentFrameIds) {
            recentFrameIds += frameId
            while (recentFrameIds.size > DUPLICATE_HISTORY_LIMIT) {
                val oldest = recentFrameIds.iterator()
                oldest.next()
                oldest.remove()
            }
        }
    }

    private fun boundedExecutor(
        threads: Int,
        queueCapacity: Int,
        threadName: String,
    ): ThreadPoolExecutor =
        ThreadPoolExecutor(
            threads,
            threads,
            0,
            TimeUnit.MILLISECONDS,
            ArrayBlockingQueue(queueCapacity),
            { runnable ->
                Thread(runnable, threadName).apply { isDaemon = true }
            },
            ThreadPoolExecutor.AbortPolicy(),
        )

    private companion object {
        const val SERVER_BACKLOG = 8
        const val WORK_QUEUE_CAPACITY = 8
        const val DUPLICATE_HISTORY_LIMIT = 256
        const val SOCKET_TIMEOUT_MILLIS = 5_000
    }
}

object LocalWifiSocketClient {
    fun send(
        endpoint: LocalWifiPeerEndpoint,
        frame: ByteArray,
    ): LocalWifiSendResult {
        if (!LocalNetworkAddress.isAllowed(endpoint.address)) {
            return LocalWifiSendResult.Refused("NON_LOCAL_ADDRESS")
        }
        if (endpoint.protocolVersion != LOCAL_WIFI_PROTOCOL_VERSION) {
            return LocalWifiSendResult.Refused("VERSION_UNSUPPORTED")
        }
        if (frame.isEmpty()) return LocalWifiSendResult.Refused("EMPTY_FRAME")
        if (frame.size > minOf(endpoint.maxPayloadBytes, MAX_LOCAL_WIFI_FRAME_BYTES)) {
            return LocalWifiSendResult.Refused("PAYLOAD_TOO_LARGE")
        }
        val frameId = sha256(frame).toHex()
        return try {
            Socket().use { socket ->
                socket.connect(
                    InetSocketAddress(endpoint.address, endpoint.port),
                    CONNECT_TIMEOUT_MILLIS,
                )
                socket.soTimeout = SOCKET_TIMEOUT_MILLIS
                val output = BufferedOutputStream(socket.getOutputStream())
                LocalWifiFraming.write(output, frame)
                val input = BufferedInputStream(socket.getInputStream())
                when (LocalWifiFraming.readAck(input, frameId)) {
                    AckStatus.ACCEPTED -> LocalWifiSendResult.Accepted(frameId, duplicate = false)
                    AckStatus.DUPLICATE -> LocalWifiSendResult.Accepted(frameId, duplicate = true)
                    AckStatus.REFUSED -> LocalWifiSendResult.Refused("PEER_REFUSED")
                }
            }
        } catch (error: LocalWifiProtocolException) {
            LocalWifiSendResult.Refused(error.code)
        } catch (_: SocketTimeoutException) {
            LocalWifiSendResult.Refused("SOCKET_TIMEOUT")
        } catch (_: Exception) {
            LocalWifiSendResult.Refused("SOCKET_IO_ERROR")
        }
    }

    private const val CONNECT_TIMEOUT_MILLIS = 4_000
    private const val SOCKET_TIMEOUT_MILLIS = 5_000
}

private enum class AckStatus(val wireCode: Int) {
    ACCEPTED(1),
    DUPLICATE(2),
    REFUSED(3),
}

private object LocalWifiFraming {
    private const val ACK_MAGIC = 0x53484B41
    private const val ACK_BYTES = 4 + 1 + 1 + 32

    fun write(output: BufferedOutputStream, frame: ByteArray) {
        if (frame.isEmpty() || frame.size > MAX_LOCAL_WIFI_FRAME_BYTES) {
            throw LocalWifiProtocolException("FRAME_SIZE_INVALID")
        }
        val data = DataOutputStream(output)
        data.writeInt(frame.size)
        data.write(frame)
        data.flush()
    }

    fun read(input: BufferedInputStream): ByteArray {
        val data = DataInputStream(input)
        val size = try {
            data.readInt()
        } catch (_: EOFException) {
            throw LocalWifiProtocolException("FRAME_TRUNCATED")
        }
        if (size !in 1..MAX_LOCAL_WIFI_FRAME_BYTES) {
            throw LocalWifiProtocolException("FRAME_SIZE_INVALID")
        }
        return ByteArray(size).also(data::readFully)
    }

    fun writeAck(
        output: BufferedOutputStream,
        frameId: String,
        status: AckStatus,
    ) {
        val identifier = frameId.hexToBytes()
        val data = DataOutputStream(output)
        data.writeInt(ACK_BYTES)
        data.writeInt(ACK_MAGIC)
        data.writeByte(LOCAL_WIFI_PROTOCOL_VERSION)
        data.writeByte(status.wireCode)
        data.write(identifier)
        data.flush()
    }

    fun readAck(input: BufferedInputStream, expectedFrameId: String): AckStatus {
        val data = DataInputStream(input)
        if (data.readInt() != ACK_BYTES) throw LocalWifiProtocolException("ACK_SIZE_INVALID")
        if (data.readInt() != ACK_MAGIC) throw LocalWifiProtocolException("ACK_MAGIC_INVALID")
        if (data.readUnsignedByte() != LOCAL_WIFI_PROTOCOL_VERSION) {
            throw LocalWifiProtocolException("ACK_VERSION_UNSUPPORTED")
        }
        val status = data.readUnsignedByte()
        val identifier = ByteArray(32).also(data::readFully).toHex()
        if (identifier != expectedFrameId) throw LocalWifiProtocolException("ACK_ID_MISMATCH")
        return AckStatus.entries.singleOrNull { it.wireCode == status }
            ?: throw LocalWifiProtocolException("ACK_STATUS_INVALID")
    }
}

private fun String.hexToBytes(): ByteArray {
    if (length != 64 || any { it.digitToIntOrNull(16) == null }) {
        throw LocalWifiProtocolException("IDENTIFIER_INVALID")
    }
    return ByteArray(32) { index ->
        substring(index * 2, index * 2 + 2).toInt(16).toByte()
    }
}
