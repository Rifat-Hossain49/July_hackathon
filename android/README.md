# Shongket Android foundation

This tree is the approved Kotlin/Android software boundary. The canonical
Python implementation in `../shongket_core/` remains normative.

## Modules

- `core-conformance`: Kotlin canonical JSON codec and JVM tests against
  every committed language-neutral vector document.
- `app`: minimal single-activity Compose shell. It intentionally declares
  no internet, Bluetooth, Wi-Fi, location, camera or microphone permission.

## Build

The pinned build requires JDK 17+, Android SDK platform 36 and Build Tools
36.0.0:

```text
./gradlew :core-conformance:testDebugUnitTest :app:assembleDebug
```

The checked-in wrapper verifies the Gradle distribution checksum. GitHub
CI also installs and launches the debug APK on an API 35 software emulator.
That job is emulator evidence only, never physical-device or real-radio
evidence.

This workstation did not have an Android SDK or emulator when the
foundation was created. Local Android results must therefore be recorded
as `NOT RUN` until the required SDK is installed; the GitHub job is the
independent build boundary.
