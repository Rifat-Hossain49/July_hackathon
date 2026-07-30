package org.shongket.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import java.io.File
import org.shongket.data.persistence.AppPrivateStateStore
import org.shongket.data.persistence.BackgroundTransferPort
import org.shongket.data.persistence.DurableTransferRepository
import org.shongket.data.persistence.LifecycleRecovery
import org.shongket.data.persistence.SavedUiIdentifiers
import org.shongket.data.persistence.TransferLifecycleCoordinator

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val repository = DurableTransferRepository(
            AppPrivateStateStore(File(filesDir, "shongket-state").toPath()),
        )
        val recovery = TransferLifecycleCoordinator(repository).recover(
            savedUi = SavedUiIdentifiers(activeTransferId = null),
            backgroundTransfer = BackgroundTransferPort {
                // Slice 4 binds this port to the selected transport adapter.
            },
        )
        setContent {
            val savedTransferId by rememberSaveable {
                mutableStateOf(recovery.activeTransferId)
            }
            MaterialTheme {
                ShongketHome(
                    recovery.copy(activeTransferId = savedTransferId),
                )
            }
        }
    }
}

@Composable
private fun ShongketHome(recovery: LifecycleRecovery) {
    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 24.dp, vertical = 48.dp),
            horizontalAlignment = Alignment.Start,
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                text = stringResource(R.string.home_title),
                style = MaterialTheme.typography.headlineMedium,
            )
            Text(
                text = stringResource(R.string.software_preview_notice),
                style = MaterialTheme.typography.bodyLarge,
            )
            Text(
                text = if (recovery.activeTransferId == null) {
                    stringResource(R.string.no_active_transfer)
                } else {
                    stringResource(
                        R.string.transfer_recovery_status,
                        recovery.verifiedFragments,
                        recovery.expectedFragments,
                    )
                },
                style = MaterialTheme.typography.bodyMedium,
            )
            Button(
                onClick = {},
                enabled = false,
            ) {
                Text(text = stringResource(R.string.transport_unavailable_action))
            }
        }
    }
}
