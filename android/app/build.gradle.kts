import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
}

android {
    namespace = "com.werdeil.lyriondashboard"
    compileSdk = 35

    // AGP 9 disables resValues by default; the debug build type sets a
    // custom app_name via resValue, so the feature must be enabled.
    buildFeatures {
        resValues = true
    }

    defaultConfig {
        applicationId = "com.werdeil.lyriondashboard"
        minSdk = 26
        targetSdk = 35
        // Static literals on purpose: F-Droid builds from the source at the
        // release tag and parses these values from this file, so they must
        // be committed. Bump both for every release (versionCode packs the
        // semver as X*10000 + Y*100 + Z); CI fails the release if the tag
        // doesn't match versionName.
        versionCode = 100
        versionName = "0.1.0"
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
        debug {
            // Distinct application ID (and label) so a debug build installs
            // side by side with a signed release build instead of refusing
            // to install over it (same ID, different signing key).
            applicationIdSuffix = ".debug"
            resValue("string", "app_name", "Lyrion Dashboard (debug)")
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
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.1")
    implementation("com.google.android.material:material:1.14.0")
    implementation("androidx.preference:preference-ktx:1.2.1")
}
