import Combine
import Foundation

struct ReceivedCapsule: Identifiable {
    let id: String
    let sender: String
    let message: String
    let location: String
    let urgency: LocalWifiUrgency
    let visibility: LocalWifiVisibility
    let receivedAt: Date
}

@MainActor
final class NearbyWifiViewModel: ObservableObject {
    @Published private(set) var nearbyEnabled = false
    @Published private(set) var status = "Stopped"
    @Published private(set) var peers: [NearbyPeer] = []
    @Published var selectedPeerId: String?
    @Published var senderLabel = "Shongket-iOS-\(UUID().uuidString.prefix(4))"
    @Published var message = ""
    @Published var location = ""
    @Published var urgency: LocalWifiUrgency = .important
    @Published var visibility: LocalWifiVisibility = .public
    @Published var humanConfirmed = false
    @Published var forwardingConsent = false
    @Published private(set) var received: [ReceivedCapsule] = []
    @Published private(set) var sending = false
    @Published var notice: String?

    private let node = LocalWifiNode()

    init() {
        node.onStateChanged = { [weak self] state in
            guard let self else { return }
            switch state {
            case .stopped:
                self.nearbyEnabled = false
                self.status = "Stopped"
            case .starting:
                self.nearbyEnabled = true
                self.status = "Requesting local network…"
            case .ready:
                self.nearbyEnabled = true
                self.status = "Ready — no internet required"
            case let .failed(code):
                self.status = self.messageForCode(code)
                self.notice = self.messageForCode(code)
            }
        }
        node.onPeersChanged = { [weak self] peers in
            guard let self else { return }
            self.peers = peers
            if let selected = self.selectedPeerId,
               !peers.contains(where: { $0.id == selected }) {
                self.selectedPeerId = nil
            }
        }
        node.receiveFrame = { [weak self] frame in
            do {
                let decoded = try LocalWifiCapsuleCodec.decode(frame)
                guard LocalWifiCapsuleAdmission.evaluate(
                    decoded.capsule,
                    nowEpochSeconds: Int64(Date().timeIntervalSince1970)
                ) == .allowed else {
                    return false
                }
                Task { @MainActor [weak self] in
                    self?.store(decoded)
                }
                return true
            } catch {
                return false
            }
        }
    }

    var canSend: Bool {
        selectedPeerId != nil &&
            !message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
            !location.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
            humanConfirmed &&
            (visibility != .private || forwardingConsent) &&
            !sending
    }

    func toggleNearby() {
        notice = nil
        if nearbyEnabled {
            stop()
        } else {
            nearbyEnabled = true
            status = "Starting…"
            node.start()
        }
    }

    func stop() {
        node.stop()
        nearbyEnabled = false
        status = "Stopped"
        peers = []
        selectedPeerId = nil
        sending = false
    }

    func send() {
        notice = nil
        guard canSend, let selectedPeerId else {
            notice = "Choose a peer and complete the confirmation fields."
            return
        }

        let now = Int64(Date().timeIntervalSince1970)
        let capsule = LocalWifiCapsule(
            senderLabel: senderLabel,
            message: message,
            location: location,
            urgency: urgency,
            visibility: visibility,
            humanConfirmed: humanConfirmed,
            forwardingConsent: forwardingConsent,
            createdAtEpochSeconds: now,
            expiresAtEpochSeconds: now + 24 * 60 * 60
        )

        do {
            let frame = try LocalWifiCapsuleCodec.encode(capsule)
            sending = true
            node.send(frame: frame, to: selectedPeerId) { [weak self] outcome in
                guard let self else { return }
                self.sending = false
                switch outcome {
                case let .accepted(duplicate):
                    self.notice = duplicate
                        ? "Peer already had this capsule."
                        : "Capsule delivered and acknowledged."
                    if !duplicate {
                        self.message = ""
                        self.humanConfirmed = false
                        self.forwardingConsent = false
                    }
                case let .refused(code):
                    self.notice = self.messageForCode(code)
                }
            }
        } catch {
            notice = messageForCode((error as? ShongketProtocolError)?.code ?? "ENCODE_FAILED")
        }
    }

    func select(_ peer: NearbyPeer) {
        selectedPeerId = peer.id
    }

    func dismissNotice() {
        notice = nil
    }

    private func store(_ decoded: DecodedLocalWifiCapsule) {
        let capsule = decoded.capsule
        received.insert(
            ReceivedCapsule(
                id: decoded.capsuleId,
                sender: capsule.senderLabel,
                message: capsule.message,
                location: capsule.location,
                urgency: capsule.urgency,
                visibility: capsule.visibility,
                receivedAt: Date()
            ),
            at: 0
        )
        if received.count > 100 {
            received.removeLast(received.count - 100)
        }
        notice = "Verified capsule received from an unverified peer."
    }

    private func messageForCode(_ code: String) -> String {
        switch code {
        case "LOCAL_NETWORK_UNAVAILABLE", "DISCOVERY_UNAVAILABLE":
            return "Local network access is unavailable. Allow Shongket in Settings → Privacy & Security → Local Network, then try again."
        case "LOCAL_NETWORK_INTERRUPTED", "DISCOVERY_INTERRUPTED":
            return "Nearby discovery was interrupted. Keep both devices on the same Wi-Fi and restart nearby mode."
        case "PEER_UNAVAILABLE":
            return "That peer is no longer available."
        case "PEER_BUSY":
            return "Nearby mode is busy. Try again shortly."
        case "SOCKET_TIMEOUT":
            return "The peer did not respond before the local timeout."
        case "PEER_REFUSED":
            return "The peer refused this capsule."
        case "ACK_ID_MISMATCH":
            return "The peer acknowledgement did not match this capsule."
        case "MESSAGE_TOO_LARGE", "CAPSULE_TOO_LARGE":
            return "The capsule is too large for nearby transfer."
        case "CONSENT_REQUIRED":
            return "Private content requires explicit forwarding consent."
        case "NEARBY_MODE_STOPPED":
            return "Start nearby mode before sending."
        default:
            return "Nearby transfer failed (\(code))."
        }
    }
}
