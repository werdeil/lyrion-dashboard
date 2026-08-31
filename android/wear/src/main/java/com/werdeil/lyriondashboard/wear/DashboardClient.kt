package com.werdeil.lyriondashboard.wear

import android.os.SystemClock
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

data class NowPlaying(
    val playing: Boolean,
    val time: Double,
    val duration: Double,
    val trackId: String?,
    val title: String?,
    val artist: String?,
    val album: String?,
    val lyrics: String?,
    // SystemClock.elapsedRealtime() at which [time] was true on the server,
    // back-dated by half the request round trip like the dashboard page does,
    // so the position can be extrapolated locally between polls.
    val syncedAt: Long,
) {
    val hasTrack: Boolean get() = trackId != null
    // Same composite key as the dashboard page: streamed "flow" sources keep
    // one track_id for a whole session while the metadata changes underneath.
    val trackKey: String get() = listOf(trackId, title, artist, album).joinToString("|")

    fun positionAt(elapsedRealtime: Long): Double =
        if (playing) time + (elapsedRealtime - syncedAt) / 1000.0 else time
}

data class WebLyrics(val synced: String?, val plain: String?)

/**
 * Minimal client for the two Lyrion Dashboard endpoints the watch needs.
 * Plain HttpURLConnection: two small JSON GETs don't justify an HTTP
 * library on a watch. All calls are blocking — run them on Dispatchers.IO.
 */
object DashboardClient {

    fun fetchNowPlaying(baseUrl: String): NowPlaying {
        val sentAt = SystemClock.elapsedRealtime()
        val o = JSONObject(get("$baseUrl/now-playing.json"))
        val rtt = SystemClock.elapsedRealtime() - sentAt
        return NowPlaying(
            playing = o.optBoolean("playing"),
            time = o.optDouble("time", 0.0).takeIf { !it.isNaN() } ?: 0.0,
            duration = o.optDouble("duration", 0.0).takeIf { !it.isNaN() } ?: 0.0,
            trackId = optString(o, "track_id"),
            title = optString(o, "title"),
            artist = optString(o, "artist"),
            album = optString(o, "album"),
            lyrics = optString(o, "lyrics"),
            syncedAt = sentAt + rtt / 2,
        )
    }

    /** Web fallback (/lyrics.json), used when the library has no synced lyrics. */
    fun fetchWebLyrics(baseUrl: String, now: NowPlaying): WebLyrics {
        val params = buildString {
            append("track_id=").append(enc(now.trackId))
            append("&artist=").append(enc(now.artist))
            append("&title=").append(enc(now.title))
            append("&album=").append(enc(now.album))
            if (now.duration > 0) append("&duration=").append(now.duration)
        }
        val o = JSONObject(get("$baseUrl/lyrics.json?$params"))
        return WebLyrics(synced = optString(o, "synced"), plain = optString(o, "lyrics"))
    }

    private fun get(url: String): String {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 5000
        conn.readTimeout = 10000
        try {
            return conn.inputStream.bufferedReader().readText()
        } finally {
            conn.disconnect()
        }
    }

    // JSONObject.optString() returns "null" for JSON null; strip that and
    // empty strings in one place.
    private fun optString(o: JSONObject, key: String): String? =
        if (o.isNull(key)) null else o.opt(key)?.toString()?.takeIf { it.isNotEmpty() }

    private fun enc(s: String?): String = URLEncoder.encode(s ?: "", "UTF-8")
}
