package org.shongket.data.transport

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Handler
import android.os.Looper
import java.io.Closeable
import java.net.InetAddress
import java.net.NetworkInterface
import java.nio.charset.StandardCharsets
import java.util.Collections
import java.util.UUID
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.RejectedExecutionException
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

enum class LocalWifiNodeState {
    STOPPED,
    STARTING,
    ADVERTISING,
    DISCOVERING,
    READY,
    DEGRADED,
    ERROR,
}

data class LocalWifiNodeStatus(
    val state: LocalWifiNodeState,
    val reasonCode: String? = null,
    val localLabel: String,
    val listeningPort: Int? = null,
    val localAddresses: List<String> = emptyList(),
)

interface LocalWifiNodeListener {
    fun onStatusChanged(status: LocalWifiNodeStatus)
    fun onPeersChanged(peers: List<LocalWifiPeerEndpoint>)
    fun onSendCompleted(peer: LocalWifiPeerEndpoint, result: LocalWifiSendResult)
}

/**
 * Android platform adapter for foreground local-Wi-Fi discovery and raw frame
 * exchange. It performs no capsule admission, consent or expiry decision.
 */
@Suppress("DEPRECATION")
class AndroidLocalWifiTransportAdapter(
    context: Context,
    private val receiver: LocalWifiFrameReceiver,
    private val listener: LocalWifiNodeListener,
) : Closeable {
    private val applicationContext = context.applicationContext
    private val nsdManager =
        applicationContext.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val wifiManager =
        applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
    private val mainHandler = Handler(Looper.getMainLooper())
    private val active = AtomicBoolean(false)
    private val socketServer = LocalWifiSocketServer(receiver)
    private val localLabel = "Shongket-${UUID.randomUUID().toString().take(6).uppercase()}"
    private val peers = LinkedHashMap<String, LocalWifiPeerEndpoint>()
    private val resolving = mutableSetOf<String>()
    private var registeredServiceName: String? = null
    private var serviceRegistered = false
    private var discoveryStarted = false
    private var sendExecutor: ThreadPoolExecutor? = null
    private var multicastLock: WifiManager.MulticastLock? = null
    private var listeningPort: Int? = null

    private val registrationListener = object : NsdManager.RegistrationListener {
        override fun onRegistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
            if (!active.get()) return
            serviceRegistered = false
            emitStatus(LocalWifiNodeState.ERROR, "NSD_REGISTRATION_FAILED_$errorCode")
            stopInternal(emitStopped = false)
        }

        override fun onUnregistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
            if (active.get()) {
                emitStatus(LocalWifiNodeState.DEGRADED, "NSD_UNREGISTER_FAILED_$errorCode")
            }
        }

        override fun onServiceRegistered(serviceInfo: NsdServiceInfo) {
            if (!active.get()) return
            serviceRegistered = true
            registeredServiceName = serviceInfo.serviceName
            emitStatus(LocalWifiNodeState.ADVERTISING)
            startDiscovery()
        }

        override fun onServiceUnregistered(serviceInfo: NsdServiceInfo) = Unit
    }

    private val discoveryListener = object : NsdManager.DiscoveryListener {
        override fun onDiscoveryStarted(serviceType: String) {
            if (!active.get()) return
            discoveryStarted = true
            emitStatus(LocalWifiNodeState.READY)
        }

        override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
            if (!active.get()) return
            discoveryStarted = false
            emitStatus(LocalWifiNodeState.DEGRADED, "NSD_DISCOVERY_FAILED_$errorCode")
        }

        override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
            if (active.get()) {
                emitStatus(LocalWifiNodeState.DEGRADED, "NSD_STOP_FAILED_$errorCode")
            }
        }

        override fun onDiscoveryStopped(serviceType: String) {
            discoveryStarted = false
        }

        override fun onServiceFound(serviceInfo: NsdServiceInfo) {
            if (!active.get()) return
            if (!serviceInfo.serviceType.startsWith(SERVICE_TYPE.removeSuffix("."))) return
            if (serviceInfo.serviceName == registeredServiceName) return
            val shouldResolve = synchronized(resolving) {
                resolving.add(serviceInfo.serviceName)
            }
            if (!shouldResolve) return
            try {
                nsdManager.resolveService(
                    serviceInfo,
                    object : NsdManager.ResolveListener {
                        override fun onResolveFailed(
                            unresolved: NsdServiceInfo,
                            errorCode: Int,
                        ) {
                            synchronized(resolving) {
                                resolving.remove(unresolved.serviceName)
                            }
                        }

                        override fun onServiceResolved(resolved: NsdServiceInfo) {
                            synchronized(resolving) {
                                resolving.remove(resolved.serviceName)
                            }
                            if (!active.get() || resolved.serviceName == registeredServiceName) return
                            val endpoint = resolved.toEndpoint() ?: return
                            synchronized(peers) {
                                peers[resolved.serviceName] = endpoint
                            }
                            emitPeers()
                        }
                    },
                )
            } catch (_: SecurityException) {
                synchronized(resolving) { resolving.remove(serviceInfo.serviceName) }
                emitStatus(LocalWifiNodeState.ERROR, "NEARBY_WIFI_PERMISSION_REQUIRED")
            } catch (_: Exception) {
                synchronized(resolving) { resolving.remove(serviceInfo.serviceName) }
            }
        }

        override fun onServiceLost(serviceInfo: NsdServiceInfo) {
            synchronized(peers) { peers.remove(serviceInfo.serviceName) }
            synchronized(resolving) { resolving.remove(serviceInfo.serviceName) }
            emitPeers()
        }
    }

    fun start() {
        if (!active.compareAndSet(false, true)) return
        emitStatus(LocalWifiNodeState.STARTING)
        try {
            listeningPort = socketServer.start()
            acquireMulticastLock()
            sendExecutor = ThreadPoolExecutor(
                2,
                2,
                0,
                TimeUnit.MILLISECONDS,
                ArrayBlockingQueue(SEND_QUEUE_CAPACITY),
                { runnable ->
                    Thread(runnable, "shongket-wifi-send").apply { isDaemon = true }
                },
                ThreadPoolExecutor.AbortPolicy(),
            )
            val serviceInfo = NsdServiceInfo().apply {
                serviceName = localLabel
                serviceType = SERVICE_TYPE
                port = checkNotNull(listeningPort)
                setAttribute("v", LOCAL_WIFI_PROTOCOL_VERSION.toString())
                setAttribute("max", MAX_LOCAL_WIFI_FRAME_BYTES.toString())
            }
            nsdManager.registerService(
                serviceInfo,
                NsdManager.PROTOCOL_DNS_SD,
                registrationListener,
            )
        } catch (_: SecurityException) {
            emitStatus(LocalWifiNodeState.ERROR, "NEARBY_WIFI_PERMISSION_REQUIRED")
            stopInternal(emitStopped = false)
        } catch (_: Exception) {
            emitStatus(LocalWifiNodeState.ERROR, "LOCAL_WIFI_START_FAILED")
            stopInternal(emitStopped = false)
        }
    }

    fun send(peer: LocalWifiPeerEndpoint, frame: ByteArray) {
        if (!active.get()) {
            emitSend(peer, LocalWifiSendResult.Refused("LOCAL_WIFI_NOT_RUNNING"))
            return
        }
        try {
            sendExecutor?.execute {
                emitSend(peer, LocalWifiSocketClient.send(peer, frame.copyOf()))
            } ?: emitSend(peer, LocalWifiSendResult.Refused("LOCAL_WIFI_NOT_RUNNING"))
        } catch (_: RejectedExecutionException) {
            emitSend(peer, LocalWifiSendResult.Refused("SEND_QUEUE_FULL"))
        }
    }

    fun stop() {
        stopInternal(emitStopped = true)
    }

    override fun close() = stop()

    private fun startDiscovery() {
        if (!active.get() || discoveryStarted) return
        emitStatus(LocalWifiNodeState.DISCOVERING)
        try {
            nsdManager.discoverServices(
                SERVICE_TYPE,
                NsdManager.PROTOCOL_DNS_SD,
                discoveryListener,
            )
        } catch (_: SecurityException) {
            emitStatus(LocalWifiNodeState.ERROR, "NEARBY_WIFI_PERMISSION_REQUIRED")
            stopInternal(emitStopped = false)
        } catch (_: Exception) {
            emitStatus(LocalWifiNodeState.DEGRADED, "NSD_DISCOVERY_FAILED")
        }
    }

    @Synchronized
    private fun stopInternal(emitStopped: Boolean) {
        val wasActive = active.getAndSet(false)
        if (!wasActive && !emitStopped) return
        if (discoveryStarted) {
            runCatching { nsdManager.stopServiceDiscovery(discoveryListener) }
        }
        if (serviceRegistered) {
            runCatching { nsdManager.unregisterService(registrationListener) }
        }
        discoveryStarted = false
        serviceRegistered = false
        registeredServiceName = null
        synchronized(peers) { peers.clear() }
        synchronized(resolving) { resolving.clear() }
        sendExecutor?.shutdownNow()
        sendExecutor = null
        socketServer.close()
        releaseMulticastLock()
        listeningPort = null
        emitPeers()
        if (emitStopped) emitStatus(LocalWifiNodeState.STOPPED)
    }

    private fun acquireMulticastLock() {
        multicastLock = wifiManager.createMulticastLock("shongket-local-wifi").apply {
            setReferenceCounted(false)
            acquire()
        }
    }

    private fun releaseMulticastLock() {
        multicastLock?.let { lock ->
            if (lock.isHeld) runCatching { lock.release() }
        }
        multicastLock = null
    }

    private fun NsdServiceInfo.toEndpoint(): LocalWifiPeerEndpoint? {
        val resolvedHost = host ?: return null
        if (!LocalNetworkAddress.isAllowed(resolvedHost)) return null
        val version = attributes["v"]
            ?.toString(StandardCharsets.UTF_8)
            ?.toIntOrNull()
            ?: return null
        val maximum = attributes["max"]
            ?.toString(StandardCharsets.UTF_8)
            ?.toIntOrNull()
            ?: return null
        if (version != LOCAL_WIFI_PROTOCOL_VERSION) return null
        return runCatching {
            LocalWifiPeerEndpoint(
                serviceName = serviceName,
                address = resolvedHost,
                port = port,
                protocolVersion = version,
                maxPayloadBytes = maximum,
            )
        }.getOrNull()
    }

    private fun emitStatus(state: LocalWifiNodeState, reasonCode: String? = null) {
        val status = LocalWifiNodeStatus(
            state = state,
            reasonCode = reasonCode,
            localLabel = registeredServiceName ?: localLabel,
            listeningPort = listeningPort,
            localAddresses = localAddresses(),
        )
        mainHandler.post { listener.onStatusChanged(status) }
    }

    private fun emitPeers() {
        val snapshot = synchronized(peers) {
            peers.values.sortedBy { it.serviceName }.toList()
        }
        mainHandler.post { listener.onPeersChanged(snapshot) }
    }

    private fun emitSend(peer: LocalWifiPeerEndpoint, result: LocalWifiSendResult) {
        mainHandler.post { listener.onSendCompleted(peer, result) }
    }

    private fun localAddresses(): List<String> =
        runCatching {
            Collections.list(NetworkInterface.getNetworkInterfaces())
                .filter { network -> network.isUp && !network.isLoopback }
                .flatMap { network -> Collections.list(network.inetAddresses) }
                .filter(LocalNetworkAddress::isAllowed)
                .filterNot { address -> address.isLoopbackAddress }
                .mapNotNull { address -> address.hostAddress }
                .distinct()
                .sorted()
        }.getOrDefault(emptyList())

    private companion object {
        const val SERVICE_TYPE = "_shongket._tcp."
        const val SEND_QUEUE_CAPACITY = 16
    }
}
