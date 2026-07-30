"""Stdio/stream and TCP-loopback carriers for identical frame bytes."""

from __future__ import annotations

import ipaddress
import socket
from typing import BinaryIO

from .frame import FrameCodec


class StreamFrameEndpoint:
    def __init__(self, reader: BinaryIO, writer: BinaryIO) -> None:
        self._reader = reader
        self._writer = writer
        self._closed = False

    def send(self, body: bytes) -> None:
        if self._closed:
            raise OSError("endpoint is closed")
        FrameCodec.write_body(self._writer, body)

    def receive(self) -> bytes:
        if self._closed:
            raise OSError("endpoint is closed")
        return FrameCodec.read_body(self._reader)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for stream in (self._writer, self._reader):
            try:
                stream.close()
            except OSError:
                pass


class SocketFrameEndpoint(StreamFrameEndpoint):
    def __init__(self, connection: socket.socket) -> None:
        self._socket = connection
        super().__init__(
            connection.makefile("rb", buffering=0),
            connection.makefile("wb", buffering=0),
        )

    def close(self) -> None:
        super().close()
        try:
            self._socket.close()
        except OSError:
            pass


class LoopbackListener:
    """One-host TCP listener that refuses non-loopback bind addresses."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError("host must be a loopback address")
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((host, port))
        self._socket.listen(1)

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._socket.getsockname()
        return str(host), int(port)

    def accept(self, timeout: float = 5.0) -> SocketFrameEndpoint:
        self._socket.settimeout(timeout)
        connection, _address = self._socket.accept()
        return SocketFrameEndpoint(connection)

    def close(self) -> None:
        self._socket.close()

    def __enter__(self) -> "LoopbackListener":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def connect_loopback(
    host: str,
    port: int,
    *,
    timeout: float = 5.0,
) -> SocketFrameEndpoint:
    if not ipaddress.ip_address(host).is_loopback:
        raise ValueError("host must be a loopback address")
    connection = socket.create_connection((host, port), timeout=timeout)
    return SocketFrameEndpoint(connection)
