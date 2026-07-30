package org.shongket.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import java.net.InetAddress
import org.shongket.data.transport.AndroidLocalWifiTransportAdapter
import org.shongket.data.transport.LocalWifiFrameReceiver
import org.shongket.data.transport.LocalWifiNodeListener
import org.shongket.data.transport.LocalWifiNodeState
import org.shongket.data.transport.LocalWifiNodeStatus
import org.shongket.data.transport.LocalWifiPeerEndpoint
import org.shongket.data.transport.LocalWifiReceiveDecision
import org.shongket.data.transport.LocalWifiSendResult

data class ReceivedCapsuleUi(
    val decoded: DecodedLocalWifiCapsule,
    val remoteAddress: String,
)

data class NearbyWifiUiState(
    val status: LocalWifiNodeStatus =
        LocalWifiNodeStatus(LocalWifiNodeState.STOPPED, localLabel = "Shongket"),
    val peers: List<LocalWifiPeerEndpoint> = emptyList(),
    val selectedPeerName: String? = null,
    val received: List<ReceivedCapsuleUi> = emptyList(),
    val resultCode: String? = null,
)

class MainActivity : ComponentActivity() {
    private var nearbyState by mutableStateOf(NearbyWifiUiState())
    private lateinit var localWifi: AndroidLocalWifiTransportAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        localWifi = AndroidLocalWifiTransportAdapter(
            context = this,
            receiver = LocalWifiFrameReceiver(::receiveFrame),
            listener = object : LocalWifiNodeListener {
                override fun onStatusChanged(status: LocalWifiNodeStatus) {
                    nearbyState = nearbyState.copy(
                        status = status,
                        resultCode = status.reasonCode ?: nearbyState.resultCode,
                    )
                }

                override fun onPeersChanged(peers: List<LocalWifiPeerEndpoint>) {
                    val retained = nearbyState.selectedPeerName
                        ?.takeIf { selected -> peers.any { it.serviceName == selected } }
                    nearbyState = nearbyState.copy(
                        peers = peers,
                        selectedPeerName = retained ?: peers.firstOrNull()?.serviceName,
                    )
                }

                override fun onSendCompleted(
                    peer: LocalWifiPeerEndpoint,
                    result: LocalWifiSendResult,
                ) {
                    nearbyState = nearbyState.copy(
                        resultCode = when (result) {
                            is LocalWifiSendResult.Accepted ->
                                if (result.duplicate) {
                                    "ALREADY_RECEIVED_BY_${peer.serviceName}"
                                } else {
                                    "DELIVERED_TO_${peer.serviceName}"
                                }
                            is LocalWifiSendResult.Refused -> result.code
                        },
                    )
                }
            },
        )
        setContent {
            MaterialTheme {
                ShongketNearbyScreen(this)
            }
        }
    }

    override fun onDestroy() {
        localWifi.close()
        super.onDestroy()
    }

    fun startNearbyWifi() {
        nearbyState = nearbyState.copy(resultCode = null)
        localWifi.start()
    }

    fun stopNearbyWifi() {
        localWifi.stop()
        nearbyState = nearbyState.copy(resultCode = "LOCAL_WIFI_STOPPED")
    }

    fun permissionDenied() {
        nearbyState = nearbyState.copy(resultCode = "NEARBY_WIFI_PERMISSION_DENIED")
    }

    fun selectPeer(serviceName: String) {
        if (nearbyState.peers.any { it.serviceName == serviceName }) {
            nearbyState = nearbyState.copy(selectedPeerName = serviceName, resultCode = null)
        }
    }

    fun sendCapsule(
        message: String,
        location: String,
        urgency: LocalWifiUrgency,
        visibility: LocalWifiVisibility,
        humanConfirmed: Boolean,
        forwardingConsent: Boolean,
    ) {
        val peer = nearbyState.peers.singleOrNull {
            it.serviceName == nearbyState.selectedPeerName
        } ?: return setResult("SELECT_LOCAL_WIFI_PEER")
        val now = System.currentTimeMillis() / 1_000
        val capsule = LocalWifiCapsule(
            senderLabel = nearbyState.status.localLabel,
            message = message.trim(),
            location = location.trim(),
            urgency = urgency,
            visibility = visibility,
            humanConfirmed = humanConfirmed,
            forwardingConsent = forwardingConsent,
            createdAtEpochSeconds = now,
            expiresAtEpochSeconds = now + CAPSULE_LIFETIME_SECONDS,
        )
        when (val admission = LocalWifiCapsuleAdmission.evaluate(capsule, now)) {
            LocalWifiAdmissionDecision.Allowed -> Unit
            is LocalWifiAdmissionDecision.Refused -> return setResult(admission.code)
        }
        val frame = try {
            LocalWifiCapsuleCodec.encode(capsule)
        } catch (error: LocalWifiProtocolException) {
            return setResult(error.code)
        }
        nearbyState = nearbyState.copy(resultCode = "SENDING_TO_${peer.serviceName}")
        localWifi.send(peer, frame)
    }

    private fun receiveFrame(
        frame: ByteArray,
        remoteAddress: InetAddress,
    ): LocalWifiReceiveDecision {
        val decoded = try {
            LocalWifiCapsuleCodec.decode(frame)
        } catch (error: LocalWifiProtocolException) {
            return LocalWifiReceiveDecision.Refused(error.code)
        }
        return when (
            val admission = LocalWifiCapsuleAdmission.evaluate(
                decoded.capsule,
                System.currentTimeMillis() / 1_000,
            )
        ) {
            LocalWifiAdmissionDecision.Allowed -> {
                runOnUiThread {
                    nearbyState = nearbyState.copy(
                        received = (
                            listOf(
                                ReceivedCapsuleUi(
                                    decoded,
                                    remoteAddress.hostAddress ?: "local-peer",
                                ),
                            ) + nearbyState.received
                            ).take(MAX_INBOX_ITEMS),
                        resultCode = "CAPSULE_RECEIVED_AND_VERIFIED",
                    )
                }
                LocalWifiReceiveDecision.Accepted
            }
            is LocalWifiAdmissionDecision.Refused ->
                LocalWifiReceiveDecision.Refused(admission.code)
        }
    }

    private fun setResult(code: String) {
        nearbyState = nearbyState.copy(resultCode = code)
    }

    @Composable
    private fun ShongketNearbyScreen(activity: MainActivity) {
        val state = nearbyState
        var message by rememberSaveable { mutableStateOf("") }
        var location by rememberSaveable { mutableStateOf("") }
        var urgency by rememberSaveable { mutableStateOf(LocalWifiUrgency.IMPORTANT) }
        var visibility by rememberSaveable { mutableStateOf(LocalWifiVisibility.PUBLIC) }
        var consent by rememberSaveable { mutableStateOf(false) }
        var confirmed by rememberSaveable { mutableStateOf(false) }

        val permissionLauncher = rememberLauncherForActivityResult(
            ActivityResultContracts.RequestPermission(),
        ) { granted ->
            if (granted) activity.startNearbyWifi() else activity.permissionDenied()
        }
        val startNearby = {
            if (
                Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.NEARBY_WIFI_DEVICES) !=
                PackageManager.PERMISSION_GRANTED
            ) {
                permissionLauncher.launch(Manifest.permission.NEARBY_WIFI_DEVICES)
            } else {
                activity.startNearbyWifi()
            }
        }

        Surface(modifier = Modifier.fillMaxSize()) {
            Column(
                modifier = Modifier
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 20.dp, vertical = 40.dp),
                horizontalAlignment = Alignment.Start,
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(
                    stringResource(R.string.home_title),
                    style = MaterialTheme.typography.headlineMedium,
                )
                Text(stringResource(R.string.local_wifi_real_notice))
                Text(stringResource(R.string.local_wifi_setup))
                LocalWifiStatus(state)

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = startNearby,
                        enabled = state.status.state == LocalWifiNodeState.STOPPED ||
                            state.status.state == LocalWifiNodeState.ERROR,
                    ) {
                        Text(stringResource(R.string.local_wifi_start))
                    }
                    Button(
                        onClick = activity::stopNearbyWifi,
                        enabled = state.status.state != LocalWifiNodeState.STOPPED,
                    ) {
                        Text(stringResource(R.string.local_wifi_stop))
                    }
                }

                HorizontalDivider()
                Text(
                    stringResource(R.string.local_wifi_compose_title),
                    style = MaterialTheme.typography.titleLarge,
                )
                OutlinedTextField(
                    value = message,
                    onValueChange = {
                        message = it.take(2_048)
                        confirmed = false
                    },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(stringResource(R.string.manual_summary_bn)) },
                )
                OutlinedTextField(
                    value = location,
                    onValueChange = {
                        location = it.take(512)
                        confirmed = false
                    },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(stringResource(R.string.manual_location)) },
                )
                Text(stringResource(R.string.local_wifi_urgency))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    LocalWifiUrgency.entries.forEach { option ->
                        Button(onClick = { urgency = option; confirmed = false }) {
                            Text(option.name)
                        }
                    }
                }
                Text(stringResource(R.string.demo_visibility))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = {
                            visibility = LocalWifiVisibility.PUBLIC
                            consent = false
                            confirmed = false
                        },
                    ) {
                        Text(stringResource(R.string.demo_public))
                    }
                    Button(
                        onClick = {
                            visibility = LocalWifiVisibility.PRIVATE
                            confirmed = false
                        },
                    ) {
                        Text(stringResource(R.string.demo_private))
                    }
                }
                Text(
                    stringResource(
                        R.string.local_wifi_selected_visibility,
                        visibility.name,
                    ),
                )
                if (visibility == LocalWifiVisibility.PRIVATE) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(
                            checked = consent,
                            onCheckedChange = {
                                consent = it
                                confirmed = false
                            },
                        )
                        Text(stringResource(R.string.private_forward_consent))
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = confirmed, onCheckedChange = { confirmed = it })
                    Text(stringResource(R.string.manual_human_confirmation))
                }

                Text(stringResource(R.string.local_wifi_peers))
                if (state.peers.isEmpty()) {
                    Text(stringResource(R.string.local_wifi_no_peers))
                } else {
                    state.peers.forEach { peer ->
                        Button(
                            onClick = { activity.selectPeer(peer.serviceName) },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            val selected = peer.serviceName == state.selectedPeerName
                            Text(
                                stringResource(
                                    if (selected) {
                                        R.string.local_wifi_peer_selected
                                    } else {
                                        R.string.local_wifi_peer_available
                                    },
                                    peer.serviceName,
                                ),
                            )
                        }
                    }
                }
                Button(
                    onClick = {
                        activity.sendCapsule(
                            message,
                            location,
                            urgency,
                            visibility,
                            confirmed,
                            consent,
                        )
                    },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = state.selectedPeerName != null &&
                        message.isNotBlank() &&
                        location.isNotBlank() &&
                        confirmed &&
                        (visibility == LocalWifiVisibility.PUBLIC || consent),
                ) {
                    Text(stringResource(R.string.local_wifi_send))
                }
                Text(stringResource(R.string.local_wifi_security_warning))
                state.resultCode?.let {
                    Text(stringResource(R.string.local_wifi_result, it))
                }

                HorizontalDivider()
                Text(
                    stringResource(R.string.local_wifi_inbox),
                    style = MaterialTheme.typography.titleLarge,
                )
                if (state.received.isEmpty()) {
                    Text(stringResource(R.string.local_wifi_inbox_empty))
                }
                state.received.forEach { item ->
                    val capsule = item.decoded.capsule
                    Text(
                        stringResource(
                            R.string.local_wifi_received_header,
                            capsule.senderLabel,
                            capsule.urgency.name,
                        ),
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(capsule.message)
                    Text(capsule.location)
                    Text(
                        stringResource(
                            R.string.local_wifi_verified_id,
                            item.decoded.capsuleId.take(16),
                        ),
                    )
                    Text(stringResource(R.string.local_wifi_unverified_identity))
                    HorizontalDivider()
                }
            }
        }
    }

    @Composable
    private fun LocalWifiStatus(state: NearbyWifiUiState) {
        Text(
            stringResource(
                R.string.local_wifi_status,
                state.status.state.name,
            ),
        )
        if (
            state.status.state == LocalWifiNodeState.STARTING ||
            state.status.state == LocalWifiNodeState.DISCOVERING
        ) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        }
        state.status.listeningPort?.let { port ->
            Text(
                stringResource(
                    R.string.local_wifi_listening,
                    state.status.localLabel,
                    port,
                ),
            )
        }
        if (state.status.localAddresses.isNotEmpty()) {
            Text(
                stringResource(
                    R.string.local_wifi_addresses,
                    state.status.localAddresses.joinToString(),
                ),
            )
        }
    }

    private companion object {
        const val CAPSULE_LIFETIME_SECONDS = 24 * 60 * 60L
        const val MAX_INBOX_ITEMS = 20
    }
}
