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
        versionCode = 1
        versionName = "0.1.0-demo.1"
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
}

dependencies {
    implementation(project(":data-persistence"))
    implementation(project(":data-transport"))
    implementation(project(":semantic"))
    implementation(project(":security"))
    implementation(project(":diagnostics"))
    implementation(project(":release-integration"))
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.material3)
}
