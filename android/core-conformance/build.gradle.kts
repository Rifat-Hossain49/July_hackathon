plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "org.shongket.core.conformance"
    compileSdk = 37

    defaultConfig {
        minSdk = 26
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    sourceSets {
        named("test") {
            resources.directories.add("../../shongket_core/testdata")
        }
    }

    testOptions {
        unitTests.all {
            it.systemProperty(
                "shongket.report.dir",
                layout.buildDirectory.dir("reports/conformance").get().asFile.absolutePath,
            )
        }
    }
}

dependencies {
    testImplementation(libs.junit)
}
