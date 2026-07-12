import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    // Kotlin itself is AGP 9's built-in (no kotlin.android plugin, same as the
    // phone app module). Only the Compose compiler plugin must be applied, and
    // its version must match AGP 9.2's bundled Kotlin (KGP 2.2.10) so the
    // Compose compiler matches the compiler doing the build.
    id("org.jetbrains.kotlin.plugin.compose") version "2.2.10"
}

android {
    namespace = "com.werdeil.lyriondashboard.wear"
    compileSdk = 37

    // AGP 9 disables resValues by default; the debug build type sets a
    // custom app_name via resValue, so the feature must be enabled.
    buildFeatures {
        compose = true
        resValues = true
    }

    defaultConfig {
        // Same application ID as the phone app: Google Play requires the
        // Wear form factor of a listing to share the phone app's package
        // name. The watch APK never installs on a phone (uses-feature
        // android.hardware.type.watch), so the two don't collide.
        applicationId = "com.werdeil.lyriondashboard"
        minSdk = 26
        targetSdk = 35
        // Same static-literal rule as app/: F-Droid parses these from the
        // committed file. If this ever ships to Play alongside the phone
        // APK, offset the versionCode (e.g. +1_000_000) — multi-APK
        // uploads of the same package must have distinct versionCodes.
        versionCode = 100
        versionName = "0.1.0"
    }

    // Same fixed debug keystore as app/ so CI debug builds are updatable
    // over previous installs (see app/build.gradle.kts for the rationale).
    signingConfigs {
        getByName("debug") {
            storeFile = file("../app/debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

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
        debug {
            applicationIdSuffix = ".debug"
            resValue("string", "app_name", "Lyrion Lyrics (debug)")
        }
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
}

kotlin {
    compilerOptions {
        jvmTarget = JvmTarget.JVM_17
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.19.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.wear.compose:compose-material:1.4.1")
    implementation("androidx.wear.compose:compose-foundation:1.4.1")
    implementation("androidx.wear.compose:compose-navigation:1.4.1")
    // System remote-input activity (keyboard/voice) for entering the server
    // URL — Wear Compose has no on-screen text field.
    implementation("androidx.wear:wear-input:1.1.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
}
