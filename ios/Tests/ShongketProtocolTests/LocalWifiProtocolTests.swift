import CryptoKit
import Foundation
import XCTest
@testable import ShongketProtocol

final class LocalWifiProtocolTests: XCTestCase {
    func testSharedAndroidVectorIsByteExact() throws {
        let vector = try loadVector()
        let capsule = LocalWifiCapsule(
            senderLabel: vector.capsule.senderLabel,
            message: vector.capsule.message,
            location: vector.capsule.location,
            urgency: .critical,
            visibility: .public,
            humanConfirmed: vector.capsule.humanConfirmed,
            forwardingConsent: vector.capsule.forwardingConsent,
            createdAtEpochSeconds: vector.capsule.createdAtEpochSeconds,
            expiresAtEpochSeconds: vector.capsule.expiresAtEpochSeconds
        )

        let frame = try LocalWifiCapsuleCodec.encode(capsule)
        XCTAssertEqual(frame.hexString, vector.frameHex)
        XCTAssertEqual(try LocalWifiCapsuleCodec.decode(frame).capsule, capsule)
        XCTAssertEqual(
            try LocalWifiCapsuleCodec.decode(frame).capsuleId,
            vector.capsuleIdHex
        )
        XCTAssertEqual(
            LocalWifiWire.frameIdentifier(frame).hexString,
            vector.frameIdHex
        )
        XCTAssertEqual(
            try LocalWifiWire.request(for: frame).hexString,
            vector.requestHex
        )
    }

    func testAllAcknowledgementVectorsAreByteExactAndMatched() throws {
        let vector = try loadVector()
        let frameIdentifier = try Data(hex: vector.frameIdHex)
        let pairs: [(LocalWifiAcknowledgementStatus, String)] = [
            (.accepted, vector.acceptedAckHex),
            (.duplicate, vector.duplicateAckHex),
            (.refused, vector.refusedAckHex),
        ]

        for (status, expectedHex) in pairs {
            let acknowledgement = try LocalWifiWire.acknowledgement(
                frameIdentifier: frameIdentifier,
                status: status
            )
            XCTAssertEqual(acknowledgement.hexString, expectedHex)
            XCTAssertEqual(
                try LocalWifiWire.decodeAcknowledgement(
                    acknowledgement,
                    expectedFrameIdentifier: frameIdentifier
                ),
                status
            )
        }
    }

    func testCorruptionAndUnknownVersionAreRejected() throws {
        let frame = try fixtureFrame()
        var corrupted = frame
        corrupted[corrupted.index(before: corrupted.endIndex)] ^= 1
        assertProtocolError("INTEGRITY_MISMATCH") {
            _ = try LocalWifiCapsuleCodec.decode(corrupted)
        }

        var body = Data(frame.dropLast(32))
        body[4] = 99
        let unknownVersion = body + Data(SHA256.hash(data: body))
        assertProtocolError("VERSION_UNSUPPORTED") {
            _ = try LocalWifiCapsuleCodec.decode(unknownVersion)
        }
    }

    func testInvalidBooleanMalformedUtf8AndTrailingBytesAreRejected() throws {
        let frame = try fixtureFrame()

        var invalidBooleanBody = Data(frame.dropLast(32))
        invalidBooleanBody[24] = 2
        let invalidBoolean = invalidBooleanBody + Data(SHA256.hash(data: invalidBooleanBody))
        assertProtocolError("BOOLEAN_INVALID") {
            _ = try LocalWifiCapsuleCodec.decode(invalidBoolean)
        }

        var invalidUtf8Body = Data(frame.dropLast(32))
        invalidUtf8Body[28] = 0xC3
        invalidUtf8Body[29] = 0x28
        let invalidUtf8 = invalidUtf8Body + Data(SHA256.hash(data: invalidUtf8Body))
        assertProtocolError("SENDER_LABEL_UTF8_INVALID") {
            _ = try LocalWifiCapsuleCodec.decode(invalidUtf8)
        }

        let trailingBody = Data(frame.dropLast(32)) + Data([0])
        let trailing = trailingBody + Data(SHA256.hash(data: trailingBody))
        assertProtocolError("TRAILING_BYTES") {
            _ = try LocalWifiCapsuleCodec.decode(trailing)
        }
    }

    func testSizeTimestampAndAdmissionRulesFailClosed() throws {
        let vector = try loadVector()
        let oversized = LocalWifiCapsule(
            senderLabel: vector.capsule.senderLabel,
            message: String(repeating: "a", count: maxCapsuleMessageBytes + 1),
            location: vector.capsule.location,
            urgency: .critical,
            visibility: .public,
            humanConfirmed: true,
            forwardingConsent: false,
            createdAtEpochSeconds: 1_800_000_000,
            expiresAtEpochSeconds: 1_800_086_400
        )
        assertProtocolError("MESSAGE_TOO_LARGE") {
            _ = try LocalWifiCapsuleCodec.encode(oversized)
        }

        let privateWithoutConsent = try fixtureCapsule().copy(
            visibility: .private,
            forwardingConsent: false
        )
        XCTAssertEqual(
            LocalWifiCapsuleAdmission.evaluate(
                privateWithoutConsent,
                nowEpochSeconds: 1_800_000_001
            ),
            .refused("CONSENT_REQUIRED")
        )
        XCTAssertEqual(
            LocalWifiCapsuleAdmission.evaluate(
                try fixtureCapsule(),
                nowEpochSeconds: 1_800_000_001
            ),
            .allowed
        )
    }

    func testMalformedFramingAndMismatchedAcknowledgementAreRejected() throws {
        assertProtocolError("FRAME_SIZE_INVALID") {
            _ = try LocalWifiWire.decodeRequest(Data([0, 0, 0, 0]))
        }
        assertProtocolError("FRAME_TRUNCATED") {
            _ = try LocalWifiWire.decodeRequest(Data([0, 0, 0, 2, 1]))
        }

        let vector = try loadVector()
        let acknowledgement = try Data(hex: vector.acceptedAckHex)
        assertProtocolError("ACK_ID_MISMATCH") {
            _ = try LocalWifiWire.decodeAcknowledgement(
                acknowledgement,
                expectedFrameIdentifier: Data(repeating: 0, count: 32)
            )
        }
    }

    private func fixtureFrame() throws -> Data {
        try LocalWifiCapsuleCodec.encode(fixtureCapsule())
    }

    private func fixtureCapsule() throws -> LocalWifiCapsule {
        let vector = try loadVector()
        return LocalWifiCapsule(
            senderLabel: vector.capsule.senderLabel,
            message: vector.capsule.message,
            location: vector.capsule.location,
            urgency: .critical,
            visibility: .public,
            humanConfirmed: true,
            forwardingConsent: false,
            createdAtEpochSeconds: vector.capsule.createdAtEpochSeconds,
            expiresAtEpochSeconds: vector.capsule.expiresAtEpochSeconds
        )
    }

    private func loadVector() throws -> Vector {
        let testDirectory = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        let vectorURL = testDirectory
            .appendingPathComponent("../../../protocol-testdata/local_wifi_v1.json")
            .standardizedFileURL
        return try JSONDecoder().decode(Vector.self, from: Data(contentsOf: vectorURL))
    }

    private func assertProtocolError(
        _ code: String,
        file: StaticString = #filePath,
        line: UInt = #line,
        action: () throws -> Void
    ) {
        XCTAssertThrowsError(try action(), file: file, line: line) { error in
            XCTAssertEqual(
                (error as? ShongketProtocolError)?.code,
                code,
                file: file,
                line: line
            )
        }
    }
}

private struct Vector: Decodable {
    let capsule: Capsule
    let frameHex: String
    let capsuleIdHex: String
    let frameIdHex: String
    let requestHex: String
    let acceptedAckHex: String
    let duplicateAckHex: String
    let refusedAckHex: String

    struct Capsule: Decodable {
        let senderLabel: String
        let message: String
        let location: String
        let humanConfirmed: Bool
        let forwardingConsent: Bool
        let createdAtEpochSeconds: Int64
        let expiresAtEpochSeconds: Int64
    }
}

private extension LocalWifiCapsule {
    func copy(
        visibility: LocalWifiVisibility,
        forwardingConsent: Bool
    ) -> LocalWifiCapsule {
        LocalWifiCapsule(
            senderLabel: senderLabel,
            message: message,
            location: location,
            urgency: urgency,
            visibility: visibility,
            humanConfirmed: humanConfirmed,
            forwardingConsent: forwardingConsent,
            createdAtEpochSeconds: createdAtEpochSeconds,
            expiresAtEpochSeconds: expiresAtEpochSeconds
        )
    }
}
