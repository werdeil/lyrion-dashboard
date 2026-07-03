package com.werdeil.lyriondashboard

import android.os.Bundle
import android.text.InputType
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.Toolbar
import androidx.preference.EditTextPreference
import androidx.preference.Preference
import androidx.preference.PreferenceFragmentCompat
import java.util.concurrent.Executors

class SettingsActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)
        applySystemBarInsets(findViewById(R.id.root))

        setSupportActionBar(findViewById<Toolbar>(R.id.toolbar))
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        if (savedInstanceState == null) {
            supportFragmentManager
                .beginTransaction()
                .replace(R.id.settings_container, SettingsFragment())
                .commit()
        }
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    class SettingsFragment : PreferenceFragmentCompat() {

        private val executor = Executors.newSingleThreadExecutor()

        override fun onCreatePreferences(savedInstanceState: Bundle?, rootKey: String?) {
            setPreferencesFromResource(R.xml.preferences, rootKey)

            findPreference<EditTextPreference>(MainActivity.PREF_SERVER_URL)?.apply {
                setOnBindEditTextListener { editText ->
                    editText.inputType = InputType.TYPE_TEXT_VARIATION_URI
                    editText.hint = getString(R.string.pref_server_url_hint)
                }
            }

            findPreference<Preference>(PREF_DISCOVER)?.setOnPreferenceClickListener {
                discoverServers()
                true
            }
        }

        override fun onDestroy() {
            super.onDestroy()
            executor.shutdownNow()
        }

        private fun discoverServers() {
            val progress = AlertDialog.Builder(requireContext())
                .setMessage(R.string.discover_in_progress)
                .setCancelable(false)
                .show()

            executor.execute {
                val servers = try {
                    ServerDiscovery.discover()
                } catch (e: Exception) {
                    emptyList()
                }
                activity?.runOnUiThread {
                    if (!isAdded) {
                        return@runOnUiThread
                    }
                    progress.dismiss()
                    if (servers.isEmpty()) {
                        Toast.makeText(
                            requireContext(),
                            R.string.discover_no_server,
                            Toast.LENGTH_LONG
                        ).show()
                    } else {
                        showServerChoice(servers)
                    }
                }
            }
        }

        private fun showServerChoice(servers: List<ServerDiscovery.Server>) {
            val labels = servers
                .map { "${it.name} (${it.host})" }
                .toTypedArray()
            AlertDialog.Builder(requireContext())
                .setTitle(R.string.discover_choose_server)
                .setItems(labels) { _, which ->
                    val url = "http://${servers[which].host}:$DEFAULT_APP_PORT"
                    findPreference<EditTextPreference>(MainActivity.PREF_SERVER_URL)?.text = url
                    Toast.makeText(
                        requireContext(),
                        getString(R.string.discover_url_set, url),
                        Toast.LENGTH_LONG
                    ).show()
                }
                .setNegativeButton(android.R.string.cancel, null)
                .show()
        }

        companion object {
            private const val PREF_DISCOVER = "discover"

            /** Default port of the Lyrion Dashboard Flask app (see config.py). */
            private const val DEFAULT_APP_PORT = 1111
        }
    }
}
