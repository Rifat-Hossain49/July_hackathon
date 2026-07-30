import CryptoKit
import Foundation

public let localWifiProtocolVersion: UInt8 = 1
public let maxLocalWifiFrameBytes = 8_192
public let maxCapsuleMessageBytes = 4_096
public let maxCapsuleLocationBytes = 1_024
public let maxCapsuleSenderLabelBytes = 64

public enum LocalWifiUrgency: UInt8, CaseIterable, Identifiable {
    case routine = 1
    case important = 2
    case critical = 3

    public var id: UInt8 { rawValue }

    public var displayName: String {
        switch self {
        case .routine: return "Routine"
        case .important: return "Important"
        case .critical: return "Critical"
        }
    }
}

public enum LocalWifiVisibility: UInt8, CaseIterable, Identifiable {
    case `public` = 1
    case `private` = 2

    public var id: UInt8 { rawValue }

    public var displayName: String {
        switch self {
        case .public: return "Public"
        case .private: return "Private"
        }
    }
}

public struct LocalWifiCapsule: Equatable {
    public let senderLabel: String
    public let message: String
    public let location: String
    public let urgency: LocalWifiUrgency
    public let visibility: LocalWifiVisibility
    public let humanConfirmed: Bool
    public let forwardingConsent: Bool
    public let createdAtEpochSeconds: Int64
    public let expiresAtEpochSeconds: Int64

    public init(
        senderLabel: String,
        message: String,
        location: String,
        urgency: LocalWifiUrgency,
        visibility: LocalWifiVisibility,
        humanConfirmed: Bool,
        forwardingConsent: Bool,
        createdAtEpochSeconds: Int64,
        expiresAtEpochSeconds: Int64
    ) {
        self.senderLabel = senderLabel
        self.message = message
        self.location = location
        self.urgency = urgency
        self.visibility = visibility
        self.humanConfirmed = humanConfirmed
        self.forwardingConsent = forwardingConsent
        self.createdAtEpochSeconds = createdAtEpochSeconds
        self.expiresAtEpochSeconds = expiresAtEpochSeconds
    }
}

public struct DecodedLocalWifiCapsule: Equatable {
    public let capsuleId: String
    public let capsule: LocalWifiCapsule
}

public struct ShongketProtocolError: Error, Equatable, LocalizedError {
    public let code: String

    public init(_ code: String) {
        self.code = code
    }

    public var errorDescription: String? { code }
}

public enum LocalWifiCapsuleCodec {
    private static let magic: UInt32 = 0x5348_4B54
    private static let capsuleType: UInt8 = 1
    private static let digestBytes = 32
    private static let minimumCapsuleBytes = 62
    private static let maximumLifetimeSeconds: Int64 = 7 * 24 * 60 * 60

    public static func encode(_ capsule: LocalWifiCapsule) throws -> Data {
        try requireTimestampRange(
            createdAt: capsule.createdAtEpochSeconds,
            expiresAt: capsule.expiresAtEpochSeconds
        )
        let sender = try encodeUtf8(
            capsule.senderLabel,
            maximum: maxCapsuleSenderLabelBytes,
            field: "SENDER_LABEL"
        )
        let message = try encodeUtf8(
            capsule.message,
            maximum: maxCapsuleMessageBytes,
            field: "MESSAGE"
        )
        let location = try encodeUtf8(
            capsule.location,
            maximum: maxCapsuleLocationBytes,
            field: "LOCATION"
        )

        var body = Data()
        body.appendBigEndian(magic)
        body.append(localWifiProtocolVersion)
        body.append(capsuleType)
        body.appendBigEndian(capsule.createdAtEpochSeconds)
        body.appendBigEndian(capsule.expiresAtEpochSeconds)
        body.append(capsule.urgency.rawValue)
        body.append(capsule.visibility.rawValue)
        body.append(capsule.humanConfirmed ? 1 : 0)
        body.append(capsule.forwardingConsent ? 1 : 0)
        appendSized(sender, to: &body)
        appendSized(message, to: &body)
        appendSized(location, to: &body)

        let digest = Data(SHA256.hash(data: body))
        let frame = body + digest
        guard frame.count <= maxLocalWifiFrameBytes else {
            throw ShongketProtocolError("CAPSULE_TOO_LARGE")
        }
        return frame
    }

    public static func decode(_ frame: Data) throws -> DecodedLocalWifiCapsule {
        guard frame.count >= minimumCapsuleBytes,
              frame.count <= maxLocalWifiFrameBytes else {
            throw ShongketProtocolError("FRAME_SIZE_INVALID")
        }

        let bodyEnd = frame.count - digestBytes
        let body = Data(frame.prefix(bodyEnd))
        let receivedDigest = Data(frame.suffix(digestBytes))
        let expectedDigest = Data(SHA256.hash(data: body))
        guard receivedDigest == expectedDigest else {
            throw ShongketProtocolError("INTEGRITY_MISMATCH")
        }

        var cursor = DataCursor(body)
        guard try cursor.readUInt32() == magic else {
            throw ShongketProtocolError("MAGIC_INVALID")
        }
        guard try cursor.readUInt8() == localWifiProtocolVersion else {
            throw ShongketProtocolError("VERSION_UNSUPPORTED")
        }
        guard try cursor.readUInt8() == capsuleType else {
            throw ShongketProtocolError("TYPE_UNSUPPORTED")
        }

        let createdAt = try cursor.readInt64()
        let expiresAt = try cursor.readInt64()
        try requireTimestampRange(createdAt: createdAt, expiresAt: expiresAt)

        guard let urgency = LocalWifiUrgency(rawValue: try cursor.readUInt8()) else {
            throw ShongketProtocolError("URGENCY_INVALID")
        }
        guard let visibility = LocalWifiVisibility(rawValue: try cursor.readUInt8()) else {
            throw ShongketProtocolError("VISIBILITY_INVALID")
        }
        let humanConfirmed = try cursor.readBoolean()
        let forwardingConsent = try cursor.readBoolean()
        let sender = try cursor.readSizedUtf8(
            maximum: maxCapsuleSenderLabelBytes,
            field: "SENDER_LABEL"
        )
        let message = try cursor.readSizedUtf8(
            maximum: maxCapsuleMessageBytes,
            field: "MESSAGE"
        )
        let location = try cursor.readSizedUtf8(
            maximum: maxCapsuleLocationBytes,
            field: "LOCATION"
        )
        guard cursor.isAtEnd else {
            throw ShongketProtocolError("TRAILING_BYTES")
        }

        return DecodedLocalWifiCapsule(
            capsuleId: expectedDigest.hexString,
            capsule: LocalWifiCapsule(
                senderLabel: sender,
                message: message,
                location: location,
                urgency: urgency,
                visibility: visibility,
                humanConfirmed: humanConfirmed,
                forwardingConsent: forwardingConsent,
                createdAtEpochSeconds: createdAt,
                expiresAtEpochSeconds: expiresAt
            )
        )
    }

    private static func appendSized(_ value: Data, to output: inout Data) {
        output.appendBigEndian(UInt16(value.count))
        output.append(value)
    }

    private static func encodeUtf8(
        _ value: String,
        maximum: Int,
        field: String
    ) throws -> Data {
        let bytes = Data(value.utf8)
        guard !bytes.isEmpty else {
            throw ShongketProtocolError("\(field)_REQUIRED")
        }
        guard bytes.count <= maximum else {
            throw ShongketProtocolError("\(field)_TOO_LARGE")
        }
        return bytes
    }

    private static func requireTimestampRange(
        createdAt: Int64,
        expiresAt: Int64
    ) throws {
        guard createdAt > 0 else {
            throw ShongketProtocolError("CREATED_AT_INVALID")
        }
        guard expiresAt > createdAt,
              expiresAt - createdAt <= maximumLifetimeSeconds else {
            throw ShongketProtocolError("EXPIRY_INVALID")
        }
    }
}

extension Data {
    mutating func appendBigEndian(_ value: UInt16) {
        var bigEndian = value.bigEndian
        Swift.withUnsafeBytes(of: &bigEndian) { bytes in
            append(contentsOf: bytes)
        }
    }

    mutating func appendBigEndian(_ value: UInt32) {
        var bigEndian = value.bigEndian
        Swift.withUnsafeBytes(of: &bigEndian) { bytes in
            append(contentsOf: bytes)
        }
    }

    mutating func appendBigEndian(_ value: Int64) {
        var bigEndian = value.bigEndian
        Swift.withUnsafeBytes(of: &bigEndian) { bytes in
            append(contentsOf: bytes)
        }
    }

    public var hexString: String {
        map { String(format: "%02x", $0) }.joined()
    }

    public init(hex: String) throws {
        guard hex.count.isMultiple(of: 2) else {
            throw ShongketProtocolError("HEX_INVALID")
        }
        var output = Data()
        output.reserveCapacity(hex.count / 2)
        var index = hex.startIndex
        while index < hex.endIndex {
            let next = hex.index(index, offsetBy: 2)
            guard let byte = UInt8(hex[index..<next], radix: 16) else {
                throw ShongketProtocolError("HEX_INVALID")
            }
            output.append(byte)
            index = next
        }
        self = output
    }
}

private struct DataCursor {
    private let data: Data
    private(set) var offset = 0

    init(_ data: Data) {
        self.data = data
    }

    var isAtEnd: Bool { offset == data.count }

    mutating func readUInt8() throws -> UInt8 {
        let bytes = try readData(count: 1)
        return bytes[bytes.startIndex]
    }

    mutating func readBoolean() throws -> Bool {
        switch try readUInt8() {
        case 0: return false
        case 1: return true
        default: throw ShongketProtocolError("BOOLEAN_INVALID")
        }
    }

    mutating func readUInt16() throws -> UInt16 {
        let bytes = try readData(count: 2)
        return bytes.reduce(UInt16(0)) { ($0 << 8) | UInt16($1) }
    }

    mutating func readUInt32() throws -> UInt32 {
        let bytes = try readData(count: 4)
        return bytes.reduce(UInt32(0)) { ($0 << 8) | UInt32($1) }
    }

    mutating func readInt64() throws -> Int64 {
        let bytes = try readData(count: 8)
        let unsigned = bytes.reduce(UInt64(0)) { ($0 << 8) | UInt64($1) }
        return Int64(bitPattern: unsigned)
    }

    mutating func readSizedUtf8(maximum: Int, field: String) throws -> String {
        let length = Int(try readUInt16())
        guard length > 0 else {
            throw ShongketProtocolError("\(field)_REQUIRED")
        }
        guard length <= maximum, length <= data.count - offset else {
            throw ShongketProtocolError("\(field)_SIZE_INVALID")
        }
        let bytes = try readData(count: length)
        guard let value = String(data: bytes, encoding: .utf8) else {
            throw ShongketProtocolError("\(field)_UTF8_INVALID")
        }
        return value
    }

    mutating func readData(count: Int) throws -> Data {
        guard count >= 0, count <= data.count - offset else {
            throw ShongketProtocolError("FRAME_MALFORMED")
        }
        let start = data.index(data.startIndex, offsetBy: offset)
        let end = data.index(start, offsetBy: count)
        offset += count
        return Data(data[start..<end])
    }
}
