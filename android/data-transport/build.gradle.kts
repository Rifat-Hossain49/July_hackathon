plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "org.shongket.data.transport"
    compileSdk = 36

    defaultConfig {
        minSdk = 26
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    sourceSets {
        named("test") {
            resources.directories.add("../../protocol-testdata")
        }
    }
}

dependencies {
    implementation(project(":data-persistence"))
    testImplementation(libs.junit)
}
