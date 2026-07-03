package com.werdeil.lyriondashboard

import android.app.Activity
import android.view.View
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat

/**
 * Draws edge-to-edge on every Android version (15+ enforces it anyway) and
 * pads [root] by the top/side system bar and display cutout insets so the
 * page is not covered by the status bar. No bottom padding: the page keeps
 * extending behind the (transparent) gesture bar.
 */
fun Activity.applySystemBarInsets(root: View) {
    WindowCompat.setDecorFitsSystemWindows(window, false)
    ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
        val bars = insets.getInsets(
            WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout()
        )
        view.setPadding(bars.left, bars.top, bars.right, 0)
        WindowInsetsCompat.CONSUMED
    }
}
