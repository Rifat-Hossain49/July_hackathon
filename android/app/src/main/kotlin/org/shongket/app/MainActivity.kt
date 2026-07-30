package org.shongket.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import java.io.File
import org.shongket.release.DemoController
import org.shongket.release.DemoStage
import org.shongket.release.DemoState

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val controller = DemoController(File(filesDir, "demo-state").toPath())
        setContent {
            MaterialTheme {
                ShongketDemo(controller)
            }
        }
    }
}

@Composable
private fun ShongketDemo(controller: DemoController) {
    var state by remember { mutableStateOf(controller.state()) }
    var message by rememberSaveable { mutableStateOf("") }
    var location by rememberSaveable { mutableStateOf("") }
    var isPrivate by rememberSaveable { mutableStateOf(false) }
    var consent by rememberSaveable { mutableStateOf(false) }

    fun refresh(action: () -> Unit) {
        action()
        state = controller.state()
    }

    Surface(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp, vertical = 40.dp),
            horizontalAlignment = Alignment.Start,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(stringResource(R.string.home_title), style = MaterialTheme.typography.headlineMedium)
            Text(stringResource(R.string.demo_simulated_notice))
            DemoStatus(state)

            Button(onClick = { refresh(controller::createFixture) }) {
                Text(stringResource(R.string.demo_create_media))
            }
            if (state.objectId != null) {
                Text(
                    stringResource(
                        R.string.demo_media_metadata,
                        state.sourceBytes,
                        state.objectId.take(12),
                    ),
                )
            }

            OutlinedTextField(
                value = message,
                onValueChange = { message = it.take(1_024) },
                label = { Text(stringResource(R.string.manual_summary_bn)) },
            )
            OutlinedTextField(
                value = location,
                onValueChange = { location = it.take(256) },
                label = { Text(stringResource(R.string.manual_location)) },
            )
            Text(stringResource(R.string.demo_visibility))
            Button(onClick = { isPrivate = false; consent = false }) {
                Text(stringResource(R.string.demo_public))
            }
            Button(onClick = { isPrivate = true }) {
                Text(stringResource(R.string.demo_private))
            }
            if (isPrivate) {
                Text(stringResource(R.string.demo_private_selected))
                PrivateForwardConsent { consent = it }
            }
            Button(
                onClick = {
                    refresh {
                        controller.confirmCapsule(message, location, isPrivate, consent)
                    }
                },
            ) {
                Text(stringResource(R.string.manual_schedule))
            }
            Button(onClick = { refresh(controller::selectSimulatedPeer) }) {
                Text(stringResource(R.string.demo_select_peer))
            }
            Button(onClick = { refresh(controller::startTransfer) }) {
                Text(stringResource(R.string.demo_start_transfer))
            }
            Button(onClick = { refresh(controller::interruptTransfer) }) {
                Text(stringResource(R.string.demo_interrupt))
            }
            Button(onClick = { refresh(controller::resumeTransfer) }) {
                Text(stringResource(R.string.demo_resume))
            }
            Button(onClick = { refresh(controller::exportDiagnostics) }) {
                Text(stringResource(R.string.demo_export_diagnostics))
            }
            state.lastErrorCode?.let {
                Text(stringResource(R.string.demo_error, it), color = MaterialTheme.colorScheme.error)
            }
            state.diagnosticJson?.let {
                Text(stringResource(R.string.demo_diagnostics_ready, it.length))
            }
        }
    }
}

@Composable
private fun DemoStatus(state: DemoState) {
    Text(stringResource(R.string.demo_stage, state.stage.name))
    LinearProgressIndicator(
        progress = { state.progressPercent / 100f },
        modifier = Modifier.fillMaxWidth(),
    )
    Text(
        stringResource(
            R.string.demo_progress,
            state.progressPercent,
            state.verifiedFragments,
            state.expectedFragments,
        ),
    )
    state.simulatedPeer?.let { Text(stringResource(R.string.demo_peer, it)) }
    if (state.stage == DemoStage.RECEIVED && state.receivedVerified) {
        Text(stringResource(R.string.demo_received_verified))
    }
}
