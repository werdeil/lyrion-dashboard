plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// On a GitHub release, CI exports the tag (vX.Y.Z) as APP_VERSION_NAME and
// the version is derived from it — no manual bump needed. Local and everyday
// CI builds fall back to the dev default below.
val releaseVersion = System.getenv("APP_VERSION_NAME")?.removePrefix("v")

// Packs X.Y.Z into an integer that grows with every release (X*10000 +
// Y*100 + Z), so Android accepts each release as an update of the previous
// one. Assumes Y and Z stay below 100.
fun semverCode(version: String): Int? {
    val parts = version.split(".").map { it.takeWhile(Char::isDigit) }
    if (parts.size != 3 || parts.any { it.isEmpty() }) {
        return null
    }
    val (major, minor, patch) = parts.map { it.toInt() }
    return major * 10000 + minor * 100 + patch
}

android {
    namespace = "com.werdeil.lyrioncustomdata"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.werdeil.lyrioncustomdata"
        minSdk = 26
        targetSdk = 35
        versionCode = if (releaseVersion != null) {
            semverCode(releaseVersion)
                ?: error("Release tag must look like vX.Y.Z, got: $releaseVersion")
        } else {
            1
        }
        versionName = releaseVersion ?: "0.1.0-dev"
    }

    // A fixed debug keystore (standard debug credentials, committed on
    // purpose) so every CI build signs the debug APK with the same key —
    // otherwise each ephemeral runner generates its own and Android
    // refuses to update the app over a previous install.
    signingConfigs {
        getByName("debug") {
            storeFile = file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    // Release signing is driven by environment variables so CI can sign
    // without the release keystore ever being committed. Without them the
    // release build stays unsigned (app-release-unsigned.apk).
    val keystorePath = System.getenv("ANDROID_KEYSTORE_PATH")
    if (keystorePath != null) {
        signingConfigs {
            create("release") {
                storeFile = file(keystorePath)
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("ANDROID_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            if (keystorePath != null) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.preference:preference-ktx:1.2.1")
}
