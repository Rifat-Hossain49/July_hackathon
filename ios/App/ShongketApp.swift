import SwiftUI

@main
struct ShongketApp: App {
    @StateObject private var viewModel = NearbyWifiViewModel()

    var body: some Scene {
        WindowGroup {
            ContentView(viewModel: viewModel)
        }
    }
}
