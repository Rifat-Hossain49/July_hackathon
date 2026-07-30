import Foundation
import Network

struct NearbyPeer: Identifiable, Equatable {
    let id: String
    let name: String
}

enum LocalWifiNodeState: Equatable {
    case stopped
    case starting
    case ready
    case failed(String)
}

enum LocalWifiSendOutcome: Equatable {
    case accepted(duplicate: Bool)
    case refused(String)
}

final class LocalWifiNode {
    static let serviceType = "_shongket._tcp"

    var onStateChanged: ((LocalWifiNodeState) -> Void)?
    var onPeersChanged: (([NearbyPeer]) -> Void)?
    var receiveFrame: ((Data) -> Bool)?

    private let queue = DispatchQueue(label: "org.shongket.ios.local-wifi")
    private let localServiceName = "Shongket-iOS-\(UUID().uuidString.prefix(6))"
    private var listener: NWListener?
    private var browser: NWBrowser?
    private var peerEndpoints: [String: NWEndpoint] = [:]
    private var connections: [UUID: NWConnection] = [:]
    private var recentFrameIds = Set<String>()
    private var recentFrameOrder: [String] = []
    private var running = false

    func start() {
        queue.async { [weak self] in
            self?.startOnQueue()
        }
    }

    func stop() {
        queue.async { [weak self] in
            self?.stopOnQueue(notify: true)
        }
    }

    func send(
        frame: Data,
        to peerId: String,
        completion: @escaping (LocalWifiSendOutcome) -> Void
    ) {
        queue.async { [weak self] in
            guard let self else { return }
            guard self.running else {
                self.completeOnMain(completion, with: .refused("NEARBY_MODE_STOPPED"))
                return
            }
            guard !frame.isEmpty, frame.count <= maxLocalWifiFrameBytes else {
                self.completeOnMain(completion, with: .refused("FRAME_SIZE_INVALID"))
                return
            }
            guard let endpoint = self.peerEndpoints[peerId] else {
                self.completeOnMain(completion, with: .refused("PEER_UNAVAILABLE"))
                return
            }
            guard self.connections.count < Self.maximumActiveConnections else {
                self.completeOnMain(completion, with: .refused("PEER_BUSY"))
                return
            }

            self.startOutboundConnection(
                endpoint: endpoint,
                frame: frame,
                completion: completion
            )
        }
    }

    private func startOnQueue() {
        guard !running else { return }
        emitState(.starting)

        do {
            let listener = try NWListener(using: makeParameters())
            let txtRecord = NetService.data(fromTXTRecord: [
                "v": Data(String(localWifiProtocolVersion).utf8),
                "max": Data(String(maxLocalWifiFrameBytes).utf8),
            ])
            listener.service = NWListener.Service(
                name: localServiceName,
                type: Self.serviceType,
                domain: nil,
                txtRecord: txtRecord
            )
            listener.newConnectionHandler = { [weak self] connection in
                self?.accept(connection)
            }
            listener.stateUpdateHandler = { [weak self] state in
                self?.handleListenerState(state)
            }

            let browser = NWBrowser(
                for: .bonjour(type: Self.serviceType, domain: nil),
                using: makeParameters()
            )
            browser.browseResultsChangedHandler = { [weak self] results, _ in
                self?.updatePeers(results)
            }
            browser.stateUpdateHandler = { [weak self] state in
                self?.handleBrowserState(state)
            }

            self.listener = listener
            self.browser = browser
            running = true
            listener.start(queue: queue)
            browser.start(queue: queue)
        } catch {
            stopOnQueue(notify: false)
            emitState(.failed("LOCAL_NETWORK_UNAVAILABLE"))
        }
    }

    private func stopOnQueue(notify: Bool) {
        running = false
        listener?.stateUpdateHandler = nil
        listener?.newConnectionHandler = nil
        listener?.cancel()
        browser?.stateUpdateHandler = nil
        browser?.browseResultsChangedHandler = nil
        browser?.cancel()
        listener = nil
        browser = nil

        let activeConnections = Array(connections.values)
        connections.removeAll()
        activeConnections.forEach { connection in
            connection.stateUpdateHandler = nil
            connection.cancel()
        }
        peerEndpoints.removeAll()
        recentFrameIds.removeAll()
        recentFrameOrder.removeAll()
        emitPeers([])
        if notify {
            emitState(.stopped)
        }
    }

    private func makeParameters() -> NWParameters {
        let tcp = NWProtocolTCP.Options()
        tcp.connectionTimeout = Self.connectTimeoutSeconds
        let parameters = NWParameters(tls: nil, tcp: tcp)
        parameters.acceptLocalOnly = true
        return parameters
    }

    private func handleListenerState(_ state: NWListener.State) {
        guard running else { return }
        switch state {
        case .ready:
            emitState(.ready)
        case .failed:
            stopOnQueue(notify: false)
            emitState(.failed("LOCAL_NETWORK_UNAVAILABLE"))
        case .cancelled:
            if running {
                stopOnQueue(notify: false)
                emitState(.failed("LOCAL_NETWORK_INTERRUPTED"))
            }
        default:
            break
        }
    }

    private func handleBrowserState(_ state: NWBrowser.State) {
        guard running else { return }
        switch state {
        case .failed:
            emitState(.failed("DISCOVERY_UNAVAILABLE"))
        case .cancelled:
            if running {
                emitState(.failed("DISCOVERY_INTERRUPTED"))
            }
        default:
            break
        }
    }

    private func updatePeers(_ results: Set<NWBrowser.Result>) {
        guard running else { return }
        var updated: [String: NWEndpoint] = [:]
        var views: [NearbyPeer] = []

        for result in results {
            guard case let .service(name, type, domain, interface) = result.endpoint,
                  name != localServiceName else {
                continue
            }
            let interfaceName = interface?.name ?? ""
            let id = "\(name)|\(type)|\(domain)|\(interfaceName)"
            updated[id] = result.endpoint
            views.append(NearbyPeer(id: id, name: name))
        }

        peerEndpoints = updated
        emitPeers(views.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending })
    }

    private func accept(_ connection: NWConnection) {
        guard running, connections.count < Self.maximumActiveConnections else {
            connection.cancel()
            return
        }
        let id = UUID()
        connections[id] = connection
        connection.stateUpdateHandler = { [weak self] state in
            guard let self else { return }
            switch state {
            case .ready:
                self.receiveIncomingRequest(connection, id: id)
            case .failed, .cancelled:
                self.finishConnection(id)
            default:
                break
            }
        }
        connection.start(queue: queue)
        scheduleTimeout(for: id)
    }

    private func receiveIncomingRequest(_ connection: NWConnection, id: UUID) {
        receiveExactly(4, from: connection) { [weak self] result in
            guard let self, self.connections[id] != nil else { return }
            switch result {
            case let .success(prefix):
                do {
                    let size = try LocalWifiWire.decodeLengthPrefix(prefix)
                    guard (1...maxLocalWifiFrameBytes).contains(size) else {
                        self.finishConnection(id)
                        return
                    }
                    self.receiveIncomingFrame(size, from: connection, id: id)
                } catch {
                    self.finishConnection(id)
                }
            case .failure:
                self.finishConnection(id)
            }
        }
    }

    private func receiveIncomingFrame(
        _ size: Int,
        from connection: NWConnection,
        id: UUID
    ) {
        receiveExactly(size, from: connection) { [weak self] result in
            guard let self, self.connections[id] != nil else { return }
            guard case let .success(frame) = result else {
                self.finishConnection(id)
                return
            }

            let frameIdentifier = LocalWifiWire.frameIdentifier(frame)
            let frameId = frameIdentifier.hexString
            let status: LocalWifiAcknowledgementStatus
            if self.recentFrameIds.contains(frameId) {
                status = .duplicate
            } else if self.receiveFrame?(frame) == true {
                self.remember(frameId)
                status = .accepted
            } else {
                status = .refused
            }

            do {
                let acknowledgement = try LocalWifiWire.acknowledgement(
                    frameIdentifier: frameIdentifier,
                    status: status
                )
                connection.send(content: acknowledgement, completion: .contentProcessed { _ in
                    self.finishConnection(id)
                })
            } catch {
                self.finishConnection(id)
            }
        }
    }

    private func startOutboundConnection(
        endpoint: NWEndpoint,
        frame: Data,
        completion: @escaping (LocalWifiSendOutcome) -> Void
    ) {
        let id = UUID()
        let connection = NWConnection(to: endpoint, using: makeParameters())
        let frameIdentifier = LocalWifiWire.frameIdentifier(frame)
        var requestStarted = false
        connections[id] = connection

        connection.stateUpdateHandler = { [weak self] state in
            guard let self, self.connections[id] != nil else { return }
            switch state {
            case .ready where !requestStarted:
                requestStarted = true
                do {
                    let request = try LocalWifiWire.request(for: frame)
                    connection.send(content: request, completion: .contentProcessed { error in
                        if error != nil {
                            self.finishOutbound(
                                id,
                                outcome: .refused("SOCKET_IO_ERROR"),
                                completion: completion
                            )
                            return
                        }
                        self.receiveAcknowledgement(
                            connection,
                            id: id,
                            expectedFrameIdentifier: frameIdentifier,
                            completion: completion
                        )
                    })
                } catch {
                    self.finishOutbound(
                        id,
                        outcome: .refused(self.protocolCode(error)),
                        completion: completion
                    )
                }
            case .failed:
                self.finishOutbound(
                    id,
                    outcome: .refused("SOCKET_IO_ERROR"),
                    completion: completion
                )
            case .cancelled:
                self.finishOutbound(
                    id,
                    outcome: .refused("SOCKET_INTERRUPTED"),
                    completion: completion
                )
            default:
                break
            }
        }
        connection.start(queue: queue)
        queue.asyncAfter(deadline: .now() + Self.operationTimeoutSeconds) { [weak self] in
            guard let self, self.connections[id] != nil else { return }
            self.finishOutbound(
                id,
                outcome: .refused("SOCKET_TIMEOUT"),
                completion: completion
            )
        }
    }

    private func receiveAcknowledgement(
        _ connection: NWConnection,
        id: UUID,
        expectedFrameIdentifier: Data,
        completion: @escaping (LocalWifiSendOutcome) -> Void
    ) {
        receiveExactly(
            LocalWifiWire.acknowledgementFrameBytes,
            from: connection
        ) { [weak self] result in
            guard let self, self.connections[id] != nil else { return }
            switch result {
            case let .success(data):
                do {
                    let status = try LocalWifiWire.decodeAcknowledgement(
                        data,
                        expectedFrameIdentifier: expectedFrameIdentifier
                    )
                    let outcome: LocalWifiSendOutcome
                    switch status {
                    case .accepted:
                        outcome = .accepted(duplicate: false)
                    case .duplicate:
                        outcome = .accepted(duplicate: true)
                    case .refused:
                        outcome = .refused("PEER_REFUSED")
                    }
                    self.finishOutbound(id, outcome: outcome, completion: completion)
                } catch {
                    self.finishOutbound(
                        id,
                        outcome: .refused(self.protocolCode(error)),
                        completion: completion
                    )
                }
            case let .failure(error):
                self.finishOutbound(
                    id,
                    outcome: .refused(error.code),
                    completion: completion
                )
            }
        }
    }

    private func receiveExactly(
        _ count: Int,
        from connection: NWConnection,
        accumulated: Data = Data(),
        completion: @escaping (Result<Data, ShongketProtocolError>) -> Void
    ) {
        let remaining = count - accumulated.count
        guard remaining > 0 else {
            completion(.success(accumulated))
            return
        }
        connection.receive(
            minimumIncompleteLength: 1,
            maximumLength: remaining
        ) { [weak self] content, _, isComplete, error in
            guard let self else { return }
            if error != nil {
                completion(.failure(ShongketProtocolError("SOCKET_IO_ERROR")))
                return
            }
            var updated = accumulated
            if let content {
                updated.append(content)
            }
            if updated.count == count {
                completion(.success(updated))
            } else if isComplete || content?.isEmpty != false {
                completion(.failure(ShongketProtocolError("FRAME_TRUNCATED")))
            } else {
                self.receiveExactly(
                    count,
                    from: connection,
                    accumulated: updated,
                    completion: completion
                )
            }
        }
    }

    private func scheduleTimeout(for id: UUID) {
        queue.asyncAfter(deadline: .now() + Self.operationTimeoutSeconds) { [weak self] in
            guard let self, self.connections[id] != nil else { return }
            self.finishConnection(id)
        }
    }

    private func finishOutbound(
        _ id: UUID,
        outcome: LocalWifiSendOutcome,
        completion: @escaping (LocalWifiSendOutcome) -> Void
    ) {
        guard connections[id] != nil else { return }
        finishConnection(id)
        completeOnMain(completion, with: outcome)
    }

    private func finishConnection(_ id: UUID) {
        guard let connection = connections.removeValue(forKey: id) else { return }
        connection.stateUpdateHandler = nil
        connection.cancel()
    }

    private func remember(_ frameId: String) {
        recentFrameIds.insert(frameId)
        recentFrameOrder.append(frameId)
        while recentFrameOrder.count > Self.duplicateHistoryLimit {
            recentFrameIds.remove(recentFrameOrder.removeFirst())
        }
    }

    private func emitState(_ state: LocalWifiNodeState) {
        DispatchQueue.main.async { [weak self] in
            self?.onStateChanged?(state)
        }
    }

    private func emitPeers(_ peers: [NearbyPeer]) {
        DispatchQueue.main.async { [weak self] in
            self?.onPeersChanged?(peers)
        }
    }

    private func completeOnMain(
        _ completion: @escaping (LocalWifiSendOutcome) -> Void,
        with outcome: LocalWifiSendOutcome
    ) {
        DispatchQueue.main.async {
            completion(outcome)
        }
    }

    private func protocolCode(_ error: Error) -> String {
        (error as? ShongketProtocolError)?.code ?? "SOCKET_IO_ERROR"
    }

    private static let maximumActiveConnections = 8
    private static let duplicateHistoryLimit = 256
    private static let connectTimeoutSeconds = 4
    private static let operationTimeoutSeconds: TimeInterval = 5
}
