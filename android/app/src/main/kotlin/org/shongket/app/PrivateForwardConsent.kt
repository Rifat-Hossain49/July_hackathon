package org.shongket.app

import androidx.compose.foundation.layout.Row
import androidx.compose.material3.Checkbox
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.res.stringResource

@Composable
fun PrivateForwardConsent(onChanged: (Boolean) -> Unit) {
    var confirmed by rememberSaveable { mutableStateOf(false) }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Checkbox(
            checked = confirmed,
            onCheckedChange = {
                confirmed = it
                onChanged(it)
            },
        )
        Text(stringResource(R.string.private_forward_consent))
    }
}
