"""Coordinator-side client for a Shongket worker OS process."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from shongket_core import codec

from .endpoint import StreamFrameEndpoint
from .frame import FrameCodec


@dataclass(frozen=True)
class TranscriptRecord:
    seq: int
    peer_id: str
    direction: str
    body_bytes: int
    body_sha256: str
    frame_sha256: str

    def as_dict(self) -> dict:
        return {
            "seq": self.seq,
            "peer_id": self.peer_id,
            "direction": self.direction,
            "body_bytes": self.body_bytes,
            "body_sha256": self.body_sha256,
            "frame_sha256": self.frame_sha256,
        }


class ProcessTranscript:
    """Content-free, deterministic frame evidence."""

    def __init__(self) -> None:
        self._records: list[TranscriptRecord] = []

    def record(self, peer_id: str, direction: str, body: bytes) -> None:
        self._records.append(
            TranscriptRecord(
                seq=len(self._records),
                peer_id=peer_id,
                direction=direction,
                body_bytes=len(body),
                body_sha256=codec.sha256_hex(body),
                frame_sha256=codec.sha256_hex(FrameCodec.frame_body(body)),
            )
        )

    @property
    def records(self) -> tuple[TranscriptRecord, ...]:
        return tuple(self._records)

    def as_list(self) -> list[dict]:
        return [record.as_dict() for record in self._records]

    def digest(self) -> str:
        return codec.sha256_hex(codec.canonical_bytes(self.as_list()))


class ProcessClient:
    """One stdio-framed worker with an explicit durable store path."""

    def __init__(
        self,
        *,
        peer_id: str,
        store_path: Path | str,
        transcript: ProcessTranscript | None = None,
    ) -> None:
        self.peer_id = peer_id
        self.store_path = Path(store_path)
        self.transcript = transcript if transcript is not None else ProcessTranscript()
        self._request_id = 0
        root = Path(__file__).resolve().parents[2]
        creationflags = (
            subprocess.CREATE_NO_WINDOW
            if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0
        )
        self._process = subprocess.Popen(
            [
                sys.executable,
                "-X",
                "utf8",
                "-m",
                "adapters.process.worker",
                "--peer-id",
                peer_id,
                "--store",
                str(self.store_path),
            ],
            cwd=str(root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
        )
        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("worker process did not expose stdio pipes")
        self._endpoint = StreamFrameEndpoint(
            self._process.stdout,
            self._process.stdin,
        )

    @property
    def process_id(self) -> int:
        """Available to a test harness, deliberately absent from evidence."""
        return self._process.pid

    def request(self, operation: str, payload: dict | None = None) -> dict:
        if self._process.poll() is not None:
            raise RuntimeError(self._exit_detail())
        request = {
            "schema": "shongket.process.v1.0",
            "type": operation,
            "request_id": self._request_id,
            "payload": payload or {},
        }
        self._request_id += 1
        body = codec.canonical_bytes(request)
        self.transcript.record(self.peer_id, "sent", body)
        self._endpoint.send(body)
        try:
            response_body = self._endpoint.receive()
        except BaseException as exc:
            raise RuntimeError(self._exit_detail()) from exc
        self.transcript.record(self.peer_id, "received", response_body)
        response = codec.decode(response_body)
        if not isinstance(response, dict):
            raise RuntimeError("worker response was not an object")
        return response

    def kill(self) -> None:
        """Terminate without a protocol shutdown, for crash recovery tests."""
        if self._process.poll() is None:
            self._process.kill()
            self._process.wait(timeout=10)
        self._endpoint.close()

    def close(self) -> None:
        if self._process.poll() is None:
            try:
                self.request("shutdown")
            except RuntimeError:
                pass
        if self._process.poll() is None:
            self._process.wait(timeout=10)
        self._endpoint.close()

    def _exit_detail(self) -> str:
        code = self._process.poll()
        stderr = b""
        if code is not None and self._process.stderr is not None:
            stderr = self._process.stderr.read(2048)
        text = stderr.decode("utf-8", errors="replace").strip()
        return f"worker exited with code {code}: {text or 'no diagnostic'}"

    def __enter__(self) -> "ProcessClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
