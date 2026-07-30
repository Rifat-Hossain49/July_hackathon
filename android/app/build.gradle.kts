plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.compose.compiler)
}

android {
    namespace = "org.shongket.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "org.shongket.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 2
        versionName = "0.2.0-local-wifi.1"
    }

    buildFeatures {
        compose = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
        create("releaseCandidate") {
            initWith(getByName("release"))
            applicationIdSuffix = ".rc"
            versionNameSuffix = "-rc"
            matchingFallbacks += listOf("release")
            // Deliberately unsigned. Production signing remains a manual gate.
            signingConfig = null
        }
    }

    sourceSets {
        named("test") {
            resources.directories.add("../../protocol-testdata")
        }
    }
}

dependencies {
    implementation(project(":data-persistence"))
    implementation(project(":data-transport"))
    implementation(project(":semantic"))
    implementation(project(":security"))
    implementation(project(":diagnostics"))
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.material3)
    testImplementation(libs.junit)
}
