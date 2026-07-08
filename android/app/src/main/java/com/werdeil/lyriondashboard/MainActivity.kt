package com.werdeil.lyriondashboard

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.preference.PreferenceManager

/**
 * Full screen WebView wrapping the Lyrion Dashboard app, following
 * the same principle as lms-material-app: the whole UI lives in the web page,
 * the app only provides the shell (settings, reload, keep-screen-on).
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var errorView: View
    private var loadedUrl: String? = null
    private var mainFrameFailed = false

    // Only intercepts back while the WebView has history; otherwise the
    // system handles it (predictive back, app exit).
    private val backCallback = object : OnBackPressedCallback(false) {
        override fun handleOnBackPressed() {
            webView.goBack()
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        applySystemBarInsets(findViewById(R.id.root))

        webView = findViewById(R.id.webview)
        errorView = findViewById(R.id.error_view)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
        }
        // Lets the dashboard show its own menu button in the page header
        // (only the dashboard origin ever loads in this WebView).
        webView.addJavascriptInterface(AppBridge(), "LyrionApp")
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView?,
                request: WebResourceRequest?
            ): Boolean {
                val url = request?.url ?: return false
                // Only the dashboard itself stays in the WebView; anything
                // else (the Lyrion Material link, intent:// deep links to
                // lms-material-app, ...) is handed to the system.
                if ((url.scheme == "http" || url.scheme == "https") && isDashboardUrl(url)) {
                    return false
                }
                openExternal(url.toString())
                return true
            }

            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                mainFrameFailed = false
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                if (!mainFrameFailed) {
                    showWebView()
                }
            }

            override fun doUpdateVisitedHistory(view: WebView?, url: String?, isReload: Boolean) {
                backCallback.isEnabled = webView.canGoBack()
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                if (request?.isForMainFrame == true) {
                    mainFrameFailed = true
                    showError()
                }
            }
        }

        findViewById<View>(R.id.button_retry).setOnClickListener { reload() }
        findViewById<View>(R.id.button_settings).setOnClickListener { openSettings() }

        onBackPressedDispatcher.addCallback(this, backCallback)
    }

    override fun onResume() {
        super.onResume()
        applyKeepScreenOn()

        val url = serverUrl()
        if (url == null) {
            openSettings()
        } else if (url != loadedUrl || mainFrameFailed) {
            loadedUrl = url
            webView.loadUrl(url)
        }
    }

    private fun serverUrl(): String? {
        val prefs = PreferenceManager.getDefaultSharedPreferences(this)
        val raw = prefs.getString(PREF_SERVER_URL, null)?.trim().orEmpty()
        if (raw.isEmpty()) {
            return null
        }
        return if (raw.contains("://")) raw else "http://$raw"
    }

    private fun applyKeepScreenOn() {
        val prefs = PreferenceManager.getDefaultSharedPreferences(this)
        if (prefs.getBoolean(PREF_KEEP_SCREEN_ON, true)) {
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    private fun reload() {
        val url = serverUrl()
        if (url == null) {
            openSettings()
            return
        }
        loadedUrl = url
        webView.loadUrl(url)
    }

    private fun showWebView() {
        errorView.visibility = View.GONE
        webView.visibility = View.VISIBLE
    }

    private fun showError() {
        webView.visibility = View.GONE
        errorView.visibility = View.VISIBLE
    }

    private fun showMenuDialog() {
        AlertDialog.Builder(this)
            .setTitle(R.string.app_name)
            .setItems(
                arrayOf(
                    getString(R.string.menu_settings),
                    getString(R.string.menu_reload),
                    getString(R.string.menu_quit)
                )
            ) { _, which ->
                when (which) {
                    0 -> openSettings()
                    1 -> reload()
                    2 -> finish()
                }
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun openSettings() {
        startActivity(Intent(this, SettingsActivity::class.java))
    }

    private inner class AppBridge {
        @JavascriptInterface
        fun openMenu() {
            runOnUiThread { this@MainActivity.showMenuDialog() }
        }

        // Kept for dashboards older than the openMenu bridge.
        @JavascriptInterface
        fun openSettings() {
            runOnUiThread { this@MainActivity.openSettings() }
        }
    }

    private fun isDashboardUrl(url: Uri): Boolean {
        val dashboard = Uri.parse(serverUrl() ?: return false)
        return url.scheme == dashboard.scheme &&
            url.host == dashboard.host &&
            url.port == dashboard.port
    }

    /**
     * Opens a link outside the WebView. intent:// URLs (used by the page to
     * deep-link into lms-material-app) fall back to their embedded
     * browser_fallback_url when the target app is not installed.
     */
    private fun openExternal(url: String) {
        try {
            if (url.startsWith("intent:")) {
                val intent = Intent.parseUri(url, Intent.URI_INTENT_SCHEME)
                intent.addCategory(Intent.CATEGORY_BROWSABLE)
                try {
                    startActivity(intent)
                } catch (e: ActivityNotFoundException) {
                    val fallback = intent.getStringExtra("browser_fallback_url")
                    if (fallback != null) {
                        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(fallback)))
                    }
                }
            } else {
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
            }
        } catch (e: Exception) {
            // No app can handle the link; ignore rather than crash.
        }
    }

    companion object {
        const val PREF_SERVER_URL = "server_url"
        const val PREF_KEEP_SCREEN_ON = "keep_screen_on"
    }
}
