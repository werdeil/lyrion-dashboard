package com.werdeil.lyriondashboard.wear

/**
 * LRC parsing, a port of parseLRC() in static/nowplaying.js — keep the two
 * in sync so the watch highlights the same line as the dashboard.
 */
data class LrcLine(
    val time: Double,
    val text: String,
    // Blank separator lines between verses: rendered as a gap, never
    // allowed to become the active line.
    val blank: Boolean = false,
)

object Lrc {
    private val LINE_RE = Regex("""^\[(\d+):(\d{2}(?:\.\d+)?)\](.*)$""")
    private val META_RE =
        Regex("""^\[(ar|ti|al|au|by|offset|length|re|ve):""", RegexOption.IGNORE_CASE)
    private val OFFSET_RE = Regex("""^\[offset:([+-]?\d+)\]""", RegexOption.IGNORE_CASE)

    /** Returns the timed lines sorted by time, or null when [text] is not LRC. */
    fun parse(text: String): List<LrcLine>? {
        val parsed = mutableListOf<LrcLine>()
        var offset = 0.0
        var lastTime = 0.0
        for (line in text.split("\r\n", "\n")) {
            val offsetMatch = OFFSET_RE.find(line)
            if (offsetMatch != null) {
                offset = offsetMatch.groupValues[1].toInt() / 1000.0
                continue
            }
            if (META_RE.containsMatchIn(line)) continue
            val m = LINE_RE.find(line)
            if (m == null) {
                // Untimed blank lines between verses: keep them as separators,
                // sorted right after the previous timed line.
                if (line.isBlank() && parsed.isNotEmpty()) {
                    parsed.add(LrcLine(lastTime, "", blank = true))
                }
                continue
            }
            val t = m.groupValues[1].toInt() * 60 + m.groupValues[2].toDouble() + offset
            lastTime = t
            // A timestamp with only whitespace is a blank separator too.
            val txt = m.groupValues[3].trim()
            parsed.add(LrcLine(t, txt, blank = txt.isEmpty()))
        }
        if (parsed.isEmpty()) return null
        return parsed.sortedBy { it.time }
    }

    /**
     * Index of the line to highlight at playback position [time], skipping
     * blank separators (they share the previous line's timestamp), or -1
     * before the first line.
     */
    fun activeIndex(lines: List<LrcLine>, time: Double): Int {
        var active = -1
        for ((i, line) in lines.withIndex()) {
            if (line.time > time) break
            if (!line.blank) active = i
        }
        return active
    }
}
