// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "GmindMenuBar",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "GmindMenuBarApp", targets: ["GmindMenuBarApp"])
    ],
    targets: [
        .executableTarget(
            name: "GmindMenuBarApp"
        )
    ]
)
