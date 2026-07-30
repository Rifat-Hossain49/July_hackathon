plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "org.shongket.data.persistence"
    compileSdk = 36

    defaultConfig {
        minSdk = 26
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation(project(":core-conformance"))
    testImplementation(libs.junit)
}
