# Shongket Android foundation

This tree is the approved Kotlin/Android software boundary. The canonical
Python implementation in `../shongket_core/` remains normative.

## Modules

- `core-conformance`: Kotlin canonical JSON codec and JVM tests against
  every committed language-neutral vector document.
- `data-transport`: bounded transport contracts plus an experimental
  Android local-Wi-Fi implementation. It advertises `_shongket._tcp`
  through NSD/mDNS and exchanges integrity-verified frames over TCP between
  phones on the same Wi-Fi network or a user-enabled hotspot.
- `app`: single-activity Compose shell with a human-confirmed text-capsule
  send/receive flow. It requests nearby-Wi-Fi access at point of use on
  Android 13+ and degrades to the manual form when denied.

## Real local-Wi-Fi use

1. Install the same APK on two Android phones.
2. Join both phones to the same Wi-Fi network. Internet service is not
   required. Alternatively, enable a hotspot in one phone's system settings
   and join the second phone to it.
3. Open Shongket on both phones and tap **Start nearby Wi-Fi**.
4. Allow the Nearby devices permission when Android asks.
5. Wait for the other Shongket session to appear, select it, review the
   capsule and tap **Send verified capsule over local Wi-Fi**.

Both apps must remain open in this first experimental slice. The peer label is
not an authenticated identity, and the transport is not end-to-end encrypted.
Physical AT-47 through AT-50 evidence is still required before claiming device
or OEM compatibility.

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
