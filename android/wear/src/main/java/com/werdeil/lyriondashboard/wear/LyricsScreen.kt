package com.werdeil.lyriondashboard.wear

import android.os.SystemClock
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import androidx.wear.compose.foundation.lazy.AutoCenteringParams
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.foundation.lazy.itemsIndexed
import androidx.wear.compose.foundation.lazy.rememberScalingLazyListState
import androidx.wear.compose.material.Chip
import androidx.wear.compose.material.ChipDefaults
import androidx.wear.compose.material.CircularProgressIndicator
import androidx.wear.compose.material.MaterialTheme
import androidx.wear.compose.material.Scaffold
import androidx.wear.compose.material.Text
import androidx.wear.compose.material.TimeText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

private const val POLL_MS = 5_000L
private const val TICK_MS = 250L

/**
 * The main (and usually only) screen: whatever the dashboard reports as
 * playing, with its lyrics — line-by-line karaoke style when they carry LRC
 * timestamps, scrollable plain text otherwise. Long-press opens settings.
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun LyricsScreen(
    serverUrl: String?,
    keepScreenOn: Boolean,
    onOpenSettings: () -> Unit,
) {
    if (serverUrl == null) {
        MessageScreen(stringResource(R.string.no_server), onOpenSettings)
        return
    }

    var now by remember { mutableStateOf<NowPlaying?>(null) }
    var unreachable by remember { mutableStateOf(false) }
    var lrcLines by remember { mutableStateOf<List<LrcLine>?>(null) }
    var plainLyrics by remember { mutableStateOf<String?>(null) }
    var searchingWeb by remember { mutableStateOf(false) }

    val lifecycleOwner = LocalLifecycleOwner.current
    LaunchedEffect(serverUrl) {
        // Both survive STARTED/STOPPED cycles so wrist-down doesn't retrigger
        // the web lookup for the same track.
        var trackKey: String? = null
        var webTried = false
        lifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (true) {
                val np = try {
                    withContext(Dispatchers.IO) { DashboardClient.fetchNowPlaying(serverUrl) }
                } catch (_: Exception) {
                    null
                }
                unreachable = np == null
                if (np != null) {
                    now = np
                    if (!np.hasTrack) {
                        trackKey = null
                        lrcLines = null
                        plainLyrics = null
                    } else if (np.trackKey != trackKey) {
                        trackKey = np.trackKey
                        webTried = false
                        val library = np.lyrics?.let { Lrc.parse(it) }
                        lrcLines = library
                        plainLyrics = if (library == null) np.lyrics else null
                    }
                    // The library gave nothing synced: ask the dashboard's web
                    // fallback once per track. Plain library lyrics are still
                    // upgraded to a synced version when one is found, like the
                    // dashboard page does in auto mode.
                    if (np.hasTrack && lrcLines == null && !webTried &&
                        np.title != null && np.artist != null
                    ) {
                        webTried = true
                        searchingWeb = true
                        val web = try {
                            withContext(Dispatchers.IO) {
                                DashboardClient.fetchWebLyrics(serverUrl, np)
                            }
                        } catch (_: Exception) {
                            null
                        }
                        searchingWeb = false
                        val synced = web?.synced?.let { Lrc.parse(it) }
                        if (synced != null) {
                            lrcLines = synced
                            plainLyrics = null
                        } else if (plainLyrics == null) {
                            plainLyrics = web?.plain
                        }
                    }
                }
                delay(POLL_MS)
            }
        }
    }

    // Local playback clock: extrapolate the position between polls, like the
    // dashboard page's paintProgress() ticker.
    var position by remember { mutableDoubleStateOf(0.0) }
    LaunchedEffect(now) {
        val np = now ?: return@LaunchedEffect
        while (true) {
            position = np.positionAt(SystemClock.elapsedRealtime())
            if (!np.playing) break
            delay(TICK_MS)
        }
    }

    // Karaoke needs the screen awake; only force it while actually playing.
    val view = LocalView.current
    val screenOn = keepScreenOn && now?.playing == true
    DisposableEffect(screenOn) {
        view.keepScreenOn = screenOn
        onDispose { view.keepScreenOn = false }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .combinedClickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = null,
                onClick = {},
                onLongClick = onOpenSettings,
            ),
    ) {
        val np = now
        when {
            np == null && unreachable ->
                MessageScreen(stringResource(R.string.error_cannot_connect), onOpenSettings)

            np == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }

            !np.hasTrack ->
                MessageScreen(stringResource(R.string.not_playing), onOpenSettings)

            else -> LyricsContent(
                now = np,
                lrcLines = lrcLines,
                plainLyrics = plainLyrics,
                searchingWeb = searchingWeb,
                position = position,
            )
        }
    }
}

@Composable
private fun LyricsContent(
    now: NowPlaying,
    lrcLines: List<LrcLine>?,
    plainLyrics: String?,
    searchingWeb: Boolean,
    position: Double,
) {
    val listState = rememberScalingLazyListState()
    val activeIdx = lrcLines?.let { Lrc.activeIndex(it, position) } ?: -1

    // Keep the active line centred; +1 skips the track header item.
    LaunchedEffect(activeIdx, lrcLines) {
        if (activeIdx >= 0) listState.animateScrollToItem(activeIdx + 1, 0)
    }

    Scaffold(timeText = { TimeText() }) {
        ScalingLazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize(),
            autoCentering = AutoCenteringParams(itemIndex = 0),
        ) {
            item { TrackHeader(now) }

            if (lrcLines != null) {
                itemsIndexed(lrcLines) { i, line ->
                    val active = i == activeIdx
                    Text(
                        text = line.text.ifEmpty { " " },
                        textAlign = TextAlign.Center,
                        color = if (active) MaterialTheme.colors.primary
                        else MaterialTheme.colors.onBackground.copy(alpha = 0.55f),
                        style = if (active) MaterialTheme.typography.title3
                        else MaterialTheme.typography.body2,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 10.dp, vertical = 3.dp),
                    )
                }
            } else if (plainLyrics != null) {
                itemsIndexed(plainLyrics.lines()) { _, line ->
                    Text(
                        text = line.ifEmpty { " " },
                        textAlign = TextAlign.Center,
                        style = MaterialTheme.typography.body2,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 10.dp, vertical = 3.dp),
                    )
                }
            } else {
                item {
                    Text(
                        text = stringResource(
                            if (searchingWeb) R.string.searching_web else R.string.no_lyrics
                        ),
                        textAlign = TextAlign.Center,
                        color = MaterialTheme.colors.onBackground.copy(alpha = 0.55f),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(10.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun TrackHeader(now: NowPlaying) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Text(
            text = now.title ?: "",
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.title3,
        )
        Text(
            text = now.artist ?: "",
            textAlign = TextAlign.Center,
            color = MaterialTheme.colors.onBackground.copy(alpha = 0.7f),
            style = MaterialTheme.typography.caption2,
        )
    }
}

/** Empty state (no URL, unreachable, nothing playing) with a settings shortcut. */
@Composable
private fun MessageScreen(message: String, onOpenSettings: () -> Unit) {
    Scaffold(timeText = { TimeText() }) {
        ScalingLazyColumn(
            modifier = Modifier.fillMaxSize(),
            autoCentering = AutoCenteringParams(itemIndex = 0),
        ) {
            item {
                Text(
                    text = message,
                    textAlign = TextAlign.Center,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(10.dp),
                )
            }
            item {
                Chip(
                    label = { Text(stringResource(R.string.settings_title)) },
                    onClick = onOpenSettings,
                    colors = ChipDefaults.secondaryChipColors(),
                )
            }
        }
    }
}
