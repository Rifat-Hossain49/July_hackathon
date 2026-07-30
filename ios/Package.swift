// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "ShongketIOS",
    platforms: [
        .iOS(.v16),
        .macOS(.v13),
    ],
    products: [
        .library(name: "ShongketProtocol", targets: ["ShongketProtocol"]),
    ],
    targets: [
        .target(name: "ShongketProtocol"),
        .testTarget(
            name: "ShongketProtocolTests",
            dependencies: ["ShongketProtocol"]
        ),
    ],
    swiftLanguageVersions: [.v5]
)
