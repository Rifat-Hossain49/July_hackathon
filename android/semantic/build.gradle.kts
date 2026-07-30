plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "org.shongket.semantic"
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
    implementation(project(":media"))
    testImplementation(libs.junit)
}
