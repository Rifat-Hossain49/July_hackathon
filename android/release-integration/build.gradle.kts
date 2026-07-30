plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "org.shongket.release"
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
    implementation(project(":data-persistence"))
    implementation(project(":data-transport"))
    implementation(project(":media"))
    implementation(project(":semantic"))
    implementation(project(":security"))
    implementation(project(":diagnostics"))
    testImplementation(libs.junit)
}
