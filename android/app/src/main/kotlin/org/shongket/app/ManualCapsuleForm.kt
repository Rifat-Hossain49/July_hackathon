package org.shongket.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import org.shongket.semantic.CapsuleDraft
import org.shongket.semantic.ManualCapsuleWorkflow
import org.shongket.semantic.SemanticSource
import org.shongket.semantic.Urgency

@Composable
fun ManualCapsuleForm(
    source: SemanticSource,
    onConfirmed: (CapsuleDraft) -> Unit,
) {
    var eventType by rememberSaveable { mutableStateOf("") }
    var location by rememberSaveable { mutableStateOf("") }
    var action by rememberSaveable { mutableStateOf("") }
    var summaryBn by rememberSaveable { mutableStateOf("") }
    var confirmed by rememberSaveable { mutableStateOf(false) }
    val complete = eventType.isNotBlank() &&
        location.isNotBlank() &&
        summaryBn.isNotBlank()

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(stringResource(R.string.manual_form_title))
        OutlinedTextField(
            value = eventType,
            onValueChange = { eventType = it.take(64) },
            label = { Text(stringResource(R.string.manual_event_type)) },
        )
        OutlinedTextField(
            value = location,
            onValueChange = { location = it.take(256) },
            label = { Text(stringResource(R.string.manual_location)) },
        )
        OutlinedTextField(
            value = action,
            onValueChange = { action = it.take(512) },
            label = { Text(stringResource(R.string.manual_action)) },
        )
        OutlinedTextField(
            value = summaryBn,
            onValueChange = { summaryBn = it.take(1_024) },
            label = { Text(stringResource(R.string.manual_summary_bn)) },
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = confirmed, onCheckedChange = { confirmed = it })
            Text(stringResource(R.string.manual_human_confirmation))
        }
        Button(
            enabled = complete && confirmed,
            onClick = {
                val draft = ManualCapsuleWorkflow().manualDraft(
                    source = source,
                    eventType = eventType,
                    locationText = location,
                    urgency = Urgency.IMPORTANT,
                    requiredAction = action,
                    summaryBn = summaryBn,
                )
                onConfirmed(draft.confirmed())
            },
        ) {
            Text(stringResource(R.string.manual_schedule))
        }
    }
}
