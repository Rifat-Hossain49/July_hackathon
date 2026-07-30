import CryptoKit
import Foundation

public enum LocalWifiAcknowledgementStatus: UInt8, Equatable {
    case accepted = 1
    case duplicate = 2
    case refused = 3
}

public enum LocalWifiWire {
    public static let acknowledgementPayloadBytes = 38
    public static let acknowledgementFrameBytes = 42
    private static let acknowledgementMagic: UInt32 = 0x5348_4B41

    public static func frameIdentifier(_ frame: Data) -> Data {
        Data(SHA256.hash(data: frame))
    }

    public static func request(for frame: Data) throws -> Data {
        guard !frame.isEmpty, frame.count <= maxLocalWifiFrameBytes else {
            throw ShongketProtocolError("FRAME_SIZE_INVALID")
        }
        var output = Data()
        output.appendBigEndian(UInt32(frame.count))
        output.append(frame)
        return output
    }

    public static func decodeRequest(_ request: Data) throws -> Data {
        guard request.count >= 4 else {
            throw ShongketProtocolError("FRAME_TRUNCATED")
        }
        let size = Int(readUInt32(request.prefix(4)))
        guard (1...maxLocalWifiFrameBytes).contains(size) else {
            throw ShongketProtocolError("FRAME_SIZE_INVALID")
        }
        guard request.count == size + 4 else {
            throw ShongketProtocolError(
                request.count < size + 4 ? "FRAME_TRUNCATED" : "TRAILING_BYTES"
            )
        }
        return Data(request.dropFirst(4))
    }

    public static func acknowledgement(
        frameIdentifier: Data,
        status: LocalWifiAcknowledgementStatus
    ) throws -> Data {
        guard frameIdentifier.count == 32 else {
            throw ShongketProtocolError("IDENTIFIER_INVALID")
        }
        var output = Data()
        output.appendBigEndian(UInt32(acknowledgementPayloadBytes))
        output.appendBigEndian(acknowledgementMagic)
        output.append(localWifiProtocolVersion)
        output.append(status.rawValue)
        output.append(frameIdentifier)
        return output
    }

    public static func decodeAcknowledgement(
        _ acknowledgement: Data,
        expectedFrameIdentifier: Data
    ) throws -> LocalWifiAcknowledgementStatus {
        guard acknowledgement.count == acknowledgementFrameBytes else {
            throw ShongketProtocolError("ACK_SIZE_INVALID")
        }
        guard readUInt32(acknowledgement.prefix(4)) ==
            UInt32(acknowledgementPayloadBytes) else {
            throw ShongketProtocolError("ACK_SIZE_INVALID")
        }
        guard readUInt32(acknowledgement.dropFirst(4).prefix(4)) == acknowledgementMagic else {
            throw ShongketProtocolError("ACK_MAGIC_INVALID")
        }
        guard acknowledgement[8] == localWifiProtocolVersion else {
            throw ShongketProtocolError("ACK_VERSION_UNSUPPORTED")
        }
        guard let status = LocalWifiAcknowledgementStatus(rawValue: acknowledgement[9]) else {
            throw ShongketProtocolError("ACK_STATUS_INVALID")
        }
        let identifier = Data(acknowledgement.suffix(32))
        guard identifier == expectedFrameIdentifier else {
            throw ShongketProtocolError("ACK_ID_MISMATCH")
        }
        return status
    }

    public static func decodeLengthPrefix(_ prefix: Data) throws -> Int {
        guard prefix.count == 4 else {
            throw ShongketProtocolError("FRAME_TRUNCATED")
        }
        return Int(readUInt32(prefix))
    }

    private static func readUInt32<S: DataProtocol>(_ bytes: S) -> UInt32 {
        bytes.reduce(UInt32(0)) { ($0 << 8) | UInt32($1) }
    }
}
