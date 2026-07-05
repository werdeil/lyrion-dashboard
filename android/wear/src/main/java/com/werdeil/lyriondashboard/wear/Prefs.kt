package com.werdeil.lyriondashboard.wear

import android.content.Context

object Prefs {
    private const val NAME = "settings"
    private const val KEY_SERVER_URL = "server_url"
    private const val KEY_KEEP_SCREEN_ON = "keep_screen_on"

    private fun prefs(context: Context) =
        context.getSharedPreferences(NAME, Context.MODE_PRIVATE)

    fun serverUrl(context: Context): String? =
        prefs(context).getString(KEY_SERVER_URL, null)?.takeIf { it.isNotBlank() }

    fun setServerUrl(context: Context, url: String) {
        prefs(context).edit().putString(KEY_SERVER_URL, url).apply()
    }

    fun keepScreenOn(context: Context): Boolean =
        prefs(context).getBoolean(KEY_KEEP_SCREEN_ON, true)

    fun setKeepScreenOn(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_KEEP_SCREEN_ON, value).apply()
    }

    /**
     * Clean up a hand-typed server URL: assume http:// when no scheme is
     * given (the dashboard usually runs over plain HTTP on the LAN) and drop
     * any trailing slash so endpoint paths can be appended directly.
     */
    fun normalizeUrl(input: String?): String? {
        val trimmed = input?.trim()?.trimEnd('/') ?: return null
        if (trimmed.isEmpty()) return null
        return if ("://" in trimmed) trimmed else "http://$trimmed"
    }
}
