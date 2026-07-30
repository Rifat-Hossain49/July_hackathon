# Shongket for iOS

This directory contains the experimental native iOS 16+ client for direct,
text-only Shongket transfer over a local Wi-Fi network.

## What works in the software build

- manual, human-confirmed text capsules with no image requirement;
- Bonjour discovery using `_shongket._tcp`;
- direct bounded TCP exchange using the same version-1 wire bytes as Android;
- SHA-256 corruption detection and matched acknowledgements;
- private-content forwarding consent;
- foreground-only discovery and transfer; and
- no required account, cloud endpoint or internet service.

Peer identity and message facts are not authenticated. Content is not
encrypted. Use a trusted local network.

## Build without Apple credentials

On macOS with Xcode installed:

```sh
swift test --package-path ios
xcodebuild \
  -project ios/Shongket.xcodeproj \
  -scheme Shongket \
  -destination "generic/platform=iOS Simulator" \
  -derivedDataPath build/ios \
  CODE_SIGNING_ALLOWED=NO \
  build
```

GitHub Actions runs both commands and uploads the unsigned Simulator `.app`
as software evidence. A Simulator app cannot be installed on a physical
iPhone.

## Install on an iPhone

1. Clone the repository onto a Mac and open
   `ios/Shongket.xcodeproj` in Xcode.
2. Select the `Shongket` target, open **Signing & Capabilities**, choose your
   Apple developer team and change the bundle identifier if Xcode reports a
   conflict.
3. Connect the iPhone, choose it as the run destination and press **Run**.
4. When Shongket first starts nearby mode, allow **Local Network** access.

Do not send an Apple ID password, signing certificate or private key through
chat or commit it to Git. TestFlight or App Store distribution requires a
separately approved signing and distribution workflow.

## Android-to-iPhone use

1. Install the current Android APK and a developer-signed iOS build.
2. Connect both phones to the same Wi-Fi network, or connect one phone to a
   personal hotspot enabled by the other. The network does not need internet.
3. Keep both apps open and start nearby mode on both.
4. Allow Android nearby-Wi-Fi and iOS local-network permissions.
5. Select the other phone, enter text and a location, confirm the capsule and
   send.

Some access points isolate clients or block multicast discovery. If no peer
appears, disable guest/client isolation or try a personal hotspot. Physical
Android-to-iPhone interoperability remains unclaimed until the checklist in
`IOS_LOCAL_WIFI_SCOPE.md` is captured on named devices.
