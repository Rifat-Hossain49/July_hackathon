from __future__ import annotations

import io
import json
import struct
import threading
from pathlib import Path

import pytest

from adapters.process import (
    FrameCodec,
    LoopbackListener,
    StreamFrameEndpoint,
    connect_loopback,
)
from shongket_core import codec
from shongket_core.errors import ErrorCode, ProtocolError


def _raw(body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + body


def test_round_trip_is_exact_and_canonical():
    value = {"schema": "shongket.capsule.v1.0", "value": "জল বাড়ছে"}
    frame = FrameCodec.frame_value(value)
    assert FrameCodec.value_from_frame(frame) == value
    assert FrameCodec.body_from_frame(frame) == codec.canonical_bytes(value)
    assert frame[:4] == len(frame[4:]).to_bytes(4, "big")


def test_committed_m2_frame_vector_matches_byte_for_byte():
    root = Path(__file__).resolve().parents[3]
    vectors = json.loads(
        (
            root
            / "shongket_core"
            / "testdata"
            / "m2_process_vectors.json"
        ).read_text(encoding="utf-8")
    )
    vector = vectors["frames"][0]
    body = codec.canonical_bytes(vector["value"])
    frame = FrameCodec.frame_value(vector["value"])
    assert body.decode("utf-8") == vector["canonical_text"]
    assert len(body) == vector["body_bytes"]
    assert frame[:4].hex() == vector["header_hex"]
    assert codec.sha256_hex(body) == vector["sha256"]


def test_exact_transport_limit_is_accepted():
    padding = "x" * (FrameCodec.MAX_BODY_BYTES - len(b'{"pad":""}'))
    body = codec.canonical_bytes({"pad": padding})
    assert len(body) == FrameCodec.MAX_BODY_BYTES
    assert FrameCodec.body_from_frame(FrameCodec.frame_body(body)) == body


def test_body_above_transport_limit_is_refused_before_framing():
    body = b"x" * (FrameCodec.MAX_BODY_BYTES + 1)
    with pytest.raises(ProtocolError) as caught:
        FrameCodec.frame_body(body)
    assert caught.value.code is ErrorCode.PAYLOAD_TOO_LARGE


@pytest.mark.parametrize(
    "frame,code",
    [
        (b"", ErrorCode.SCHEMA_INVALID),
        (b"\x00\x00\x00", ErrorCode.SCHEMA_INVALID),
        (b"\x00\x00\x00\x00", ErrorCode.SCHEMA_INVALID),
        (
            (FrameCodec.MAX_BODY_BYTES + 1).to_bytes(4, "big"),
            ErrorCode.PAYLOAD_TOO_LARGE,
        ),
        (_raw(b'{"a":1') , ErrorCode.SCHEMA_INVALID),
        (_raw(b"\xff"), ErrorCode.SCHEMA_INVALID),
        (_raw(b'{"a": 1}'), ErrorCode.SCHEMA_INVALID),
        (_raw(b'{"b":1,"a":2}'), ErrorCode.SCHEMA_INVALID),
        (_raw(b'{"a":1,"a":2}'), ErrorCode.SCHEMA_INVALID),
        (_raw(b"[]"), ErrorCode.SCHEMA_INVALID),
    ],
)
def test_invalid_frames_are_refused(frame: bytes, code: ErrorCode):
    with pytest.raises(ProtocolError) as caught:
        FrameCodec.value_from_frame(frame)
    assert caught.value.code is code


def test_trailing_bytes_are_refused():
    frame = FrameCodec.frame_value({"a": 1}) + b"x"
    with pytest.raises(ProtocolError) as caught:
        FrameCodec.value_from_frame(frame)
    assert caught.value.code is ErrorCode.SCHEMA_INVALID


def test_stream_eof_inside_header_and_body_is_refused():
    with pytest.raises(ProtocolError, match="header"):
        FrameCodec.read_body(io.BytesIO(b"\x00\x00"))
    with pytest.raises(ProtocolError, match="body"):
        FrameCodec.read_body(io.BytesIO(b"\x00\x00\x00\x05{}"))


def test_stdio_and_tcp_loopback_recover_identical_body_bytes():
    body = codec.canonical_bytes({"schema": "shongket.content.v1.0", "n": 7})
    writer = io.BytesIO()
    StreamFrameEndpoint(io.BytesIO(), writer).send(body)
    assert writer.getvalue() == FrameCodec.frame_body(body)

    received: list[bytes] = []
    with LoopbackListener() as listener:
        host, port = listener.address

        def serve() -> None:
            endpoint = listener.accept()
            incoming = endpoint.receive()
            received.append(incoming)
            endpoint.send(incoming)
            endpoint.close()

        thread = threading.Thread(target=serve)
        thread.start()
        client = connect_loopback(host, port)
        client.send(body)
        echoed = client.receive()
        client.close()
        thread.join(timeout=10)

    assert not thread.is_alive()
    assert received == [body]
    assert echoed == body
    assert codec.sha256_hex(FrameCodec.frame_body(echoed)) == codec.sha256_hex(
        writer.getvalue()
    )


def test_non_loopback_addresses_are_refused():
    with pytest.raises(ValueError, match="loopback"):
        LoopbackListener("0.0.0.0")
    with pytest.raises(ValueError, match="loopback"):
        connect_loopback("192.0.2.10", 1)
