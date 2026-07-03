# Keep the WebView JavaScript bridge (window.LyrionApp) in release builds.
-keepclassmembers class com.werdeil.lyrioncustomdata.MainActivity$AppBridge {
    @android.webkit.JavascriptInterface <methods>;
}
