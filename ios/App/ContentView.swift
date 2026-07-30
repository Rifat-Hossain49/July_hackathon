import SwiftUI
import UIKit

struct ContentView: View {
    @ObservedObject var viewModel: NearbyWifiViewModel
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        NavigationStack {
            Form {
                nearbySection
                peerSection
                capsuleSection
                receivedSection
                safetySection
            }
            .navigationTitle("Shongket")
            .alert(
                "Nearby mode",
                isPresented: Binding(
                    get: { viewModel.notice != nil },
                    set: { if !$0 { viewModel.dismissNotice() } }
                )
            ) {
                Button("OK", role: .cancel) {
                    viewModel.dismissNotice()
                }
                if viewModel.notice?.contains("Settings") == true {
                    Button("Open Settings") {
                        if let url = URL(string: UIApplication.openSettingsURLString) {
                            UIApplication.shared.open(url)
                        }
                    }
                }
            } message: {
                Text(viewModel.notice ?? "")
            }
            .onChange(of: scenePhase) { phase in
                if phase != .active, viewModel.nearbyEnabled {
                    viewModel.stop()
                }
            }
        }
    }

    private var nearbySection: some View {
        Section("Nearby Wi-Fi — foreground only") {
            HStack {
                Circle()
                    .fill(viewModel.nearbyEnabled ? Color.green : Color.secondary)
                    .frame(width: 10, height: 10)
                Text(viewModel.status)
                    .font(.subheadline)
            }
            Button(viewModel.nearbyEnabled ? "Stop nearby mode" : "Start nearby mode") {
                viewModel.toggleNearby()
            }
            .buttonStyle(.borderedProminent)
            Text("Connect both phones to the same Wi-Fi or personal hotspot. Internet service is not required.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private var peerSection: some View {
        Section("Discovered peers") {
            if !viewModel.nearbyEnabled {
                Text("Start nearby mode to ask for local-network access.")
                    .foregroundStyle(.secondary)
            } else if viewModel.peers.isEmpty {
                Text("No peer found yet. Open Shongket nearby mode on the other phone.")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(viewModel.peers) { peer in
                    Button {
                        viewModel.select(peer)
                    } label: {
                        HStack {
                            VStack(alignment: .leading) {
                                Text(peer.name)
                                    .foregroundStyle(.primary)
                                Text("Unverified nearby peer")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            if viewModel.selectedPeerId == peer.id {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundStyle(.green)
                            }
                        }
                    }
                }
            }
        }
    }

    private var capsuleSection: some View {
        Section("Create text capsule") {
            TextField("Sender label", text: $viewModel.senderLabel)
                .textInputAutocapitalization(.never)
            TextField("Location description", text: $viewModel.location)
            TextEditor(text: $viewModel.message)
                .frame(minHeight: 100)
                .overlay(alignment: .topLeading) {
                    if viewModel.message.isEmpty {
                        Text("Crisis message")
                            .foregroundStyle(.tertiary)
                            .padding(.top, 8)
                            .padding(.leading, 5)
                            .allowsHitTesting(false)
                    }
                }
            Picker("Urgency", selection: $viewModel.urgency) {
                ForEach(LocalWifiUrgency.allCases) { urgency in
                    Text(urgency.displayName).tag(urgency)
                }
            }
            Picker("Visibility", selection: $viewModel.visibility) {
                ForEach(LocalWifiVisibility.allCases) { visibility in
                    Text(visibility.displayName).tag(visibility)
                }
            }
            Toggle(
                "I reviewed this capsule against the source.",
                isOn: $viewModel.humanConfirmed
            )
            if viewModel.visibility == .private {
                Toggle(
                    "I explicitly consent to forwarding this private content.",
                    isOn: $viewModel.forwardingConsent
                )
            }
            Button(viewModel.sending ? "Sending…" : "Send to selected peer") {
                viewModel.send()
            }
            .disabled(!viewModel.canSend)
            .buttonStyle(.borderedProminent)
        }
    }

    private var receivedSection: some View {
        Section("Received capsules") {
            if viewModel.received.isEmpty {
                Text("No verified capsule received in this session.")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(viewModel.received) { item in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(item.urgency.displayName.uppercased())
                                .font(.caption.bold())
                            Spacer()
                            Text(item.visibility.displayName)
                                .font(.caption)
                        }
                        Text(item.message)
                        Text("\(item.location) · \(item.sender)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("Integrity verified; sender and facts unverified.")
                            .font(.caption2)
                            .foregroundStyle(.orange)
                    }
                    .padding(.vertical, 4)
                }
            }
        }
    }

    private var safetySection: some View {
        Section("Security boundary") {
            Text("Use a trusted local network. This experimental version verifies corruption but does not encrypt messages or authenticate peer identity.")
                .font(.caption)
            Text("No photo, account, cloud service, location permission or internet connection is required.")
                .font(.caption)
        }
    }
}
