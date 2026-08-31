package com.werdeil.lyriondashboard.wear

import android.app.RemoteInput
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.wear.compose.foundation.lazy.AutoCenteringParams
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.material.Chip
import androidx.wear.compose.material.ChipDefaults
import androidx.wear.compose.material.ListHeader
import androidx.wear.compose.material.Scaffold
import androidx.wear.compose.material.Switch
import androidx.wear.compose.material.Text
import androidx.wear.compose.material.TimeText
import androidx.wear.compose.material.ToggleChip
import androidx.wear.input.RemoteInputIntentHelper

private const val KEY_SERVER_URL = "server_url"

@Composable
fun SettingsScreen(
    serverUrl: String?,
    keepScreenOn: Boolean,
    onServerUrlChange: (String) -> Unit,
    onKeepScreenOnChange: (Boolean) -> Unit,
) {
    // Wear Compose has no on-screen text field: the URL is typed (or
    // dictated) through the system remote-input activity.
    val urlInputLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val entered = result.data
            ?.let { RemoteInput.getResultsFromIntent(it) }
            ?.getCharSequence(KEY_SERVER_URL)
            ?.toString()
        Prefs.normalizeUrl(entered)?.let(onServerUrlChange)
    }

    val urlLabel = stringResource(R.string.pref_server_url)
    Scaffold(timeText = { TimeText() }) {
        ScalingLazyColumn(
            modifier = Modifier.fillMaxSize(),
            autoCentering = AutoCenteringParams(itemIndex = 0),
        ) {
            item {
                ListHeader { Text(stringResource(R.string.settings_title)) }
            }
            item {
                Chip(
                    label = { Text(urlLabel) },
                    secondaryLabel = {
                        Text(
                            text = serverUrl ?: stringResource(R.string.pref_server_url_hint),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    },
                    onClick = {
                        val intent = RemoteInputIntentHelper.createActionRemoteInputIntent()
                        val input = RemoteInput.Builder(KEY_SERVER_URL)
                            .setLabel(urlLabel)
                            .build()
                        RemoteInputIntentHelper.putRemoteInputsExtra(intent, listOf(input))
                        urlInputLauncher.launch(intent)
                    },
                    colors = ChipDefaults.secondaryChipColors(),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            item {
                ToggleChip(
                    checked = keepScreenOn,
                    onCheckedChange = onKeepScreenOnChange,
                    label = { Text(stringResource(R.string.pref_keep_screen_on)) },
                    toggleControl = { Switch(checked = keepScreenOn) },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}
