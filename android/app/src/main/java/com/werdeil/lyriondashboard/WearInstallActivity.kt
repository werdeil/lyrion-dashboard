package com.werdeil.lyriondashboard

import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.Toolbar
import androidx.preference.PreferenceManager
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/**
 * Installs the Wear OS companion APK on the watch, through the dashboard
 * server's adb (POST /wear/install.json).
 *
 * The install itself cannot run on the phone: modern watches only expose
 * "wireless debugging", whose pairing protocol is implemented by the real
 * adb binary but by no permissively-licensed Android library. So this
 * screen only collects what the watch displays (pair address + code,
 * connection address) and lets the server do the adb work.
 */
class WearInstallActivity : AppCompatActivity() {

    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var serverUrl: String

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val prefs = PreferenceManager.getDefaultSharedPreferences(this)
        val url = prefs.getString(MainActivity.PREF_SERVER_URL, null)?.trim()?.trimEnd('/')
        if (url.isNullOrEmpty()) {
            Toast.makeText(this, R.string.wear_no_server, Toast.LENGTH_LONG).show()
            finish()
            return
        }
        serverUrl = url

        setContentView(R.layout.activity_wear_install)
        applySystemBarInsets(findViewById(R.id.root))
        setSupportActionBar(findViewById<Toolbar>(R.id.toolbar))
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        findViewById<Button>(R.id.install_button).setOnClickListener { install() }
        checkServerStatus()
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    override fun onDestroy() {
        super.onDestroy()
        executor.shutdownNow()
    }

    /** Pre-flight: warn early when the server lacks adb or the APK. */
    private fun checkServerStatus() {
        executor.execute {
            val warning = try {
                val status = JSONObject(httpGet("$serverUrl/wear/status.json"))
                when {
                    !status.optBoolean("adb") -> getString(R.string.wear_status_no_adb)
                    !status.optBoolean("apk_present") -> getString(
                        R.string.wear_status_no_apk, status.optString("apk_path")
                    )
                    else -> null
                }
            } catch (e: Exception) {
                getString(R.string.error_cannot_connect)
            }
            runOnUiThread {
                if (isDestroyed) return@runOnUiThread
                findViewById<TextView>(R.id.server_status).apply {
                    visibility = if (warning != null) View.VISIBLE else View.GONE
                    text = warning ?: ""
                }
            }
        }
    }

    private fun install() {
        val pairAddress = text(R.id.pair_address)
        val pairCode = text(R.id.pair_code)
        val connectAddress = text(R.id.connect_address)

        val connect = parseHostPort(connectAddress)
        if (connect == null) {
            Toast.makeText(this, R.string.wear_bad_connect_address, Toast.LENGTH_LONG).show()
            return
        }
        // Pairing is optional (needed once per watch/server couple) but its
        // two fields come together.
        val pairPort = parseHostPort(pairAddress)?.second
        if ((pairAddress.isNotEmpty() || pairCode.isNotEmpty()) &&
            (pairPort == null || pairCode.length != 6)
        ) {
            Toast.makeText(this, R.string.wear_bad_pairing, Toast.LENGTH_LONG).show()
            return
        }

        val body = JSONObject().apply {
            put("host", connect.first)
            put("connect_port", connect.second)
            if (pairPort != null) {
                put("pair_port", pairPort)
                put("pair_code", pairCode)
            }
        }

        val progress = AlertDialog.Builder(this)
            .setMessage(R.string.wear_installing)
            .setCancelable(false)
            .show()

        executor.execute {
            val (message, detail) = try {
                val response = JSONObject(httpPost("$serverUrl/wear/install.json", body))
                if (response.optBoolean("ok")) {
                    getString(R.string.wear_install_success) to response.optString("detail")
                } else {
                    stepLabel(response.optString("step")) to response.optString("error")
                }
            } catch (e: Exception) {
                getString(R.string.error_cannot_connect) to (e.message ?: "")
            }
            runOnUiThread {
                if (isDestroyed) return@runOnUiThread
                progress.dismiss()
                Toast.makeText(this, message, Toast.LENGTH_LONG).show()
                findViewById<TextView>(R.id.result).apply {
                    visibility = View.VISIBLE
                    text = listOf(message, detail).filter { it.isNotEmpty() }
                        .joinToString("\n\n")
                }
            }
        }
    }

    private fun stepLabel(step: String): String = getString(
        when (step) {
            "adb" -> R.string.wear_status_no_adb
            "apk" -> R.string.wear_step_apk
            "pair" -> R.string.wear_step_pair
            "connect" -> R.string.wear_step_connect
            "install" -> R.string.wear_step_install
            else -> R.string.wear_step_input
        }
    )

    private fun text(id: Int): String =
        findViewById<TextView>(id).text?.toString()?.trim().orEmpty()

    /** "192.168.1.42:40001" -> host/port, or null when malformed. */
    private fun parseHostPort(value: String): Pair<String, Int>? {
        val host = value.substringBeforeLast(':', "")
        val port = value.substringAfterLast(':', "").toIntOrNull()
        if (host.isEmpty() || port == null || port !in 1..65535) return null
        return host to port
    }

    private fun httpGet(url: String): String {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 5_000
        conn.readTimeout = 15_000
        try {
            return conn.inputStream.bufferedReader().use(BufferedReader::readText)
        } finally {
            conn.disconnect()
        }
    }

    private fun httpPost(url: String, body: JSONObject): String {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.setRequestProperty("Content-Type", "application/json")
        conn.doOutput = true
        conn.connectTimeout = 5_000
        // The server's install step allows up to 5 minutes; outlast it.
        conn.readTimeout = 360_000
        try {
            conn.outputStream.use { it.write(body.toString().toByteArray()) }
            // Error statuses (400/502) still carry the JSON body we want.
            val stream = if (conn.responseCode >= 400) conn.errorStream else conn.inputStream
            return stream.bufferedReader().use(BufferedReader::readText)
        } finally {
            conn.disconnect()
        }
    }
}
