"""Four-byte big-endian framing for canonical JSON protocol objects."""

from __future__ import annotations

import struct
from collections.abc import Mapping
from typing import BinaryIO

from shongket_core import codec
from shongket_core.capabilities import MAX_TRANSPORT_PAYLOAD
from shongket_core.errors import ErrorCode, ProtocolError


class EndOfStream(EOFError):
    """Clean EOF between frames, used only to finish an endpoint loop."""


class FrameCodec:
    """Encode and decode exactly one bounded canonical object per frame."""

    HEADER_BYTES = 4
    MAX_BODY_BYTES = MAX_TRANSPORT_PAYLOAD

    @classmethod
    def frame_value(cls, value: Mapping[str, object]) -> bytes:
        return cls.frame_body(codec.canonical_bytes(dict(value)))

    @classmethod
    def frame_body(cls, body: bytes) -> bytes:
        cls.validate_body(body)
        return struct.pack(">I", len(body)) + body

    @classmethod
    def validate_body(cls, body: bytes) -> dict:
        if not isinstance(body, bytes):
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"frame body must be bytes, got {type(body).__name__}",
            )
        size = len(body)
        if size == 0:
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, "frame body is empty")
        if size > cls.MAX_BODY_BYTES:
            raise ProtocolError(
                ErrorCode.PAYLOAD_TOO_LARGE,
                f"frame body of {size} bytes exceeds {cls.MAX_BODY_BYTES}",
            )
        value = codec.decode(body)
        if not isinstance(value, dict):
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                "frame body must be a JSON object",
            )
        if codec.canonical_bytes(value) != body:
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                "frame body is not canonical JSON",
            )
        return value

    @classmethod
    def body_from_frame(cls, frame: bytes) -> bytes:
        if not isinstance(frame, bytes):
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"frame must be bytes, got {type(frame).__name__}",
            )
        if len(frame) < cls.HEADER_BYTES:
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                "frame header is truncated",
            )
        declared = struct.unpack(">I", frame[: cls.HEADER_BYTES])[0]
        if declared == 0:
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, "declared body length is zero")
        if declared > cls.MAX_BODY_BYTES:
            raise ProtocolError(
                ErrorCode.PAYLOAD_TOO_LARGE,
                f"declared body length {declared} exceeds {cls.MAX_BODY_BYTES}",
            )
        actual = len(frame) - cls.HEADER_BYTES
        if actual < declared:
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"frame body is truncated: declared {declared}, received {actual}",
            )
        if actual > declared:
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"frame contains {actual - declared} trailing byte(s)",
            )
        body = frame[cls.HEADER_BYTES :]
        cls.validate_body(body)
        return body

    @classmethod
    def value_from_frame(cls, frame: bytes) -> dict:
        return cls.validate_body(cls.body_from_frame(frame))

    @classmethod
    def read_body(cls, reader: BinaryIO) -> bytes:
        first = reader.read(1)
        if first == b"":
            raise EndOfStream()
        header_tail = cls._read_exact(reader, cls.HEADER_BYTES - 1)
        if len(header_tail) != cls.HEADER_BYTES - 1:
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                "EOF inside frame header",
            )
        declared = struct.unpack(">I", first + header_tail)[0]
        if declared == 0:
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, "declared body length is zero")
        if declared > cls.MAX_BODY_BYTES:
            raise ProtocolError(
                ErrorCode.PAYLOAD_TOO_LARGE,
                f"declared body length {declared} exceeds {cls.MAX_BODY_BYTES}",
            )
        body = cls._read_exact(reader, declared)
        if len(body) != declared:
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"EOF inside frame body: declared {declared}, received {len(body)}",
            )
        cls.validate_body(body)
        return body

    @classmethod
    def read_value(cls, reader: BinaryIO) -> dict:
        return cls.validate_body(cls.read_body(reader))

    @classmethod
    def write_body(cls, writer: BinaryIO, body: bytes) -> None:
        writer.write(cls.frame_body(body))
        writer.flush()

    @classmethod
    def write_value(cls, writer: BinaryIO, value: Mapping[str, object]) -> None:
        writer.write(cls.frame_value(value))
        writer.flush()

    @staticmethod
    def _read_exact(reader: BinaryIO, size: int) -> bytes:
        result = bytearray()
        while len(result) < size:
            chunk = reader.read(size - len(result))
            if not chunk:
                break
            result.extend(chunk)
        return bytes(result)
