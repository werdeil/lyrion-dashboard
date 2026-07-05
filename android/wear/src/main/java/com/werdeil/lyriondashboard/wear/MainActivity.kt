package com.werdeil.lyriondashboard.wear

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.wear.compose.material.MaterialTheme
import androidx.wear.compose.navigation.SwipeDismissableNavHost
import androidx.wear.compose.navigation.composable
import androidx.wear.compose.navigation.rememberSwipeDismissableNavController

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { WearApp() }
    }
}

@Composable
fun WearApp() {
    val context = LocalContext.current
    // Settings are hoisted here so the lyrics screen reacts immediately when
    // they change, without re-reading SharedPreferences on navigation.
    var serverUrl by remember { mutableStateOf(Prefs.serverUrl(context)) }
    var keepScreenOn by remember { mutableStateOf(Prefs.keepScreenOn(context)) }

    val navController = rememberSwipeDismissableNavController()
    MaterialTheme {
        SwipeDismissableNavHost(navController = navController, startDestination = "lyrics") {
            composable("lyrics") {
                LyricsScreen(
                    serverUrl = serverUrl,
                    keepScreenOn = keepScreenOn,
                    onOpenSettings = { navController.navigate("settings") },
                )
            }
            composable("settings") {
                SettingsScreen(
                    serverUrl = serverUrl,
                    keepScreenOn = keepScreenOn,
                    onServerUrlChange = {
                        serverUrl = it
                        Prefs.setServerUrl(context, it)
                    },
                    onKeepScreenOnChange = {
                        keepScreenOn = it
                        Prefs.setKeepScreenOn(context, it)
                    },
                )
            }
        }
    }
}
