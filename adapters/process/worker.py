"""Deterministic stdio worker used by the two-process acceptance harness."""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

from shongket_core import canonical_registry, codec
from shongket_core.errors import ErrorCode, ProtocolError
from shongket_core.evidence import EvidenceLog
from shongket_core.persist import SnapshotStore, restore_into
from shongket_core.store import Fragment, FragmentStore, record_from_fragment

from .frame import EndOfStream, FrameCodec


PROCESS_SCHEMA = "shongket.process.v1.0"


class WorkerState:
    def __init__(self, peer_id: str, store_path: Path) -> None:
        self.peer_id = peer_id
        self.evidence = EvidenceLog()
        self.store = FragmentStore(evidence=self.evidence)
        self.snapshot = SnapshotStore(store_path, evidence=self.evidence)
        self.manifests: dict[str, dict] = {}
        self.capsules: dict[str, dict] = {}
        if self.snapshot.exists():
            loaded = self.snapshot.load()
            restore_into(self.store, loaded.fragments)

    def handle(self, request: dict) -> tuple[dict, bool]:
        request_id, operation, payload = _validate_request(request)
        if operation == "shutdown":
            return self._ok(request_id, {"closed": True}), True
        if operation == "hello":
            return self._ok(
                request_id,
                {
                    "peer_id": self.peer_id,
                    "transports": ["stdio", "loopback"],
                    "max_payload": FrameCodec.MAX_BODY_BYTES,
                    "public_only": False,
                },
            ), False
        if operation == "canonicalize":
            value = payload.get("value")
            if not isinstance(value, dict):
                raise ProtocolError(
                    ErrorCode.SCHEMA_INVALID,
                    "canonicalize value must be an object",
                )
            canonical = codec.canonical_bytes(value)
            return self._ok(
                request_id,
                {
                    "canonical_b64": base64.b64encode(canonical).decode("ascii"),
                    "byte_count": len(canonical),
                    "sha256": codec.sha256_hex(canonical),
                },
            ), False
        if operation == "put_capsule":
            capsule = _require_object(payload, "capsule")
            accepted = canonical_registry().accept(capsule)
            self.capsules[str(capsule["capsule_id"])] = dict(accepted.payload)
            return self._ok(
                request_id,
                {"capsule_id": capsule["capsule_id"]},
            ), False
        if operation == "put_manifest":
            manifest = _require_object(payload, "manifest")
            accepted = canonical_registry().accept(manifest)
            self.manifests[str(manifest["object_id"])] = dict(accepted.payload)
            return self._ok(
                request_id,
                {"object_id": manifest["object_id"]},
            ), False
        if operation == "put_fragment":
            descriptor = _require_object(payload, "descriptor")
            canonical_registry().accept(descriptor)
            fragment = _fragment_from_payload(descriptor, payload)
            stored = self.store.put(fragment)
            checksum = None
            if stored:
                checksum = self.snapshot.save(
                    self.store,
                    peer_id=self.peer_id,
                    created_at_unix=1_700_000_000,
                )
            return self._ok(
                request_id,
                {
                    "stored": stored,
                    "chunk_index": fragment.chunk_index,
                    "document_checksum": checksum,
                },
            ), False
        if operation == "inventory":
            object_id = _require_string(payload, "object_id")
            representation_id = _require_string(payload, "representation_id")
            return self._ok(
                request_id,
                {
                    "chunk_indexes": list(
                        self.store.chunk_indexes(object_id, representation_id)
                    ),
                    "used_bytes": self.store.used_bytes,
                    "fragment_count": len(self.store),
                    "evidence_digest": self.evidence.digest(),
                },
            ), False
        if operation == "get_fragment":
            object_id = _require_string(payload, "object_id")
            representation_id = _require_string(payload, "representation_id")
            chunk_index = _require_integer(payload, "chunk_index")
            fragment = self.store.get(object_id, representation_id, chunk_index)
            if fragment is None:
                raise ProtocolError(
                    ErrorCode.UNKNOWN_OBJECT,
                    f"fragment {chunk_index} is not held",
                    object_id=object_id,
                )
            record = record_from_fragment(fragment)
            descriptor = {
                "schema": "shongket.fragment.v1.0",
                "object_id": fragment.object_id,
                "representation_id": fragment.representation_id,
                "chunk_index": fragment.chunk_index,
                "chunk_size": len(fragment.payload),
                "byte_range": list(fragment.byte_range),
                "hash": fragment.sha256,
            }
            return self._ok(
                request_id,
                {
                    "descriptor": descriptor,
                    "payload_b64": record["payload_b64"],
                },
            ), False
        if operation == "complete":
            object_id = _require_string(payload, "object_id")
            representation_id = _require_string(payload, "representation_id")
            result = self._complete(object_id, representation_id)
            return self._ok(request_id, result), False
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"unknown process operation {operation!r}",
        )

    def _complete(self, object_id: str, representation_id: str) -> dict:
        manifest = self.manifests.get(object_id)
        if manifest is None:
            raise ProtocolError(
                ErrorCode.UNKNOWN_OBJECT,
                "manifest is not held",
                object_id=object_id,
            )
        representations = manifest.get("representations")
        if not isinstance(representations, list):
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                "manifest representations must be a list",
                object_id=object_id,
            )
        selected = next(
            (
                item
                for item in representations
                if isinstance(item, dict) and item.get("id") == representation_id
            ),
            None,
        )
        if selected is None:
            raise ProtocolError(
                ErrorCode.UNKNOWN_OBJECT,
                f"representation {representation_id!r} is not declared",
                object_id=object_id,
            )
        hashes = selected.get("hashes")
        expected_hash = selected.get("hash")
        if not isinstance(hashes, list) or not all(
            isinstance(item, str) for item in hashes
        ):
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                "representation hashes must be a string list",
                object_id=object_id,
            )
        if not isinstance(expected_hash, str):
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                "representation hash must be a string",
                object_id=object_id,
            )
        missing = self.store.missing_indexes(
            object_id,
            representation_id,
            range(len(hashes)),
        )
        if missing:
            raise ProtocolError(
                ErrorCode.UNKNOWN_OBJECT,
                f"representation is incomplete; missing indexes {list(missing)}",
                object_id=object_id,
            )
        assembled = bytearray()
        for index, expected_fragment_hash in enumerate(hashes):
            fragment = self.store.get(object_id, representation_id, index)
            if fragment is None or fragment.sha256 != expected_fragment_hash:
                raise ProtocolError(
                    ErrorCode.SCHEMA_INVALID,
                    f"fragment {index} does not match the manifest",
                    object_id=object_id,
                )
            assembled.extend(fragment.payload)
        actual_hash = codec.sha256_hex(bytes(assembled))
        if actual_hash != expected_hash:
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                "reconstructed representation hash does not match the manifest",
                object_id=object_id,
            )
        return {
            "object_id": object_id,
            "representation_id": representation_id,
            "sha256": actual_hash,
            "byte_count": len(assembled),
            "chunk_count": len(hashes),
        }

    def _ok(self, request_id: int, result: dict) -> dict:
        return {
            "schema": PROCESS_SCHEMA,
            "request_id": request_id,
            "ok": True,
            "result": result,
        }


def _validate_request(request: dict) -> tuple[int, str, dict]:
    if request.get("schema") != PROCESS_SCHEMA:
        raise ProtocolError(
            ErrorCode.VERSION_UNSUPPORTED,
            "process message schema is unsupported",
        )
    request_id = _require_integer(request, "request_id")
    operation = _require_string(request, "type")
    payload = request.get("payload")
    if not isinstance(payload, dict):
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            "process payload must be an object",
        )
    return request_id, operation, payload


def _require_object(payload: dict, key: str) -> dict:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"{key} must be an object",
        )
    return value


def _require_string(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"{key} must be a non-empty string",
        )
    return value


def _require_integer(payload: dict, key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"{key} must be a non-negative integer",
        )
    return value


def _fragment_from_payload(descriptor: dict, payload: dict) -> Fragment:
    encoded = payload.get("payload_b64")
    if not isinstance(encoded, str):
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            "payload_b64 must be a string",
        )
    try:
        body = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            "payload_b64 is not canonical base64",
        ) from exc
    byte_range = descriptor.get("byte_range")
    if (
        not isinstance(byte_range, list)
        or len(byte_range) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in byte_range)
    ):
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            "descriptor byte_range must contain two integers",
        )
    start, end = byte_range
    if start < 0 or end < start or end - start + 1 != len(body):
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            "descriptor byte_range does not match the payload",
        )
    return Fragment(
        object_id=_require_string(descriptor, "object_id"),
        representation_id=_require_string(descriptor, "representation_id"),
        chunk_index=_require_integer(descriptor, "chunk_index"),
        byte_range=(start, end),
        sha256=_require_string(descriptor, "hash"),
        payload=body,
    )


def _error_response(request: object, exc: ProtocolError) -> dict:
    request_id = (
        request.get("request_id")
        if isinstance(request, dict)
        and isinstance(request.get("request_id"), int)
        and not isinstance(request.get("request_id"), bool)
        else 0
    )
    return {
        "schema": PROCESS_SCHEMA,
        "request_id": request_id,
        "ok": False,
        "error": exc.to_dict(),
    }


def run(peer_id: str, store_path: Path) -> int:
    state = WorkerState(peer_id, store_path)
    while True:
        try:
            request = FrameCodec.read_value(sys.stdin.buffer)
        except EndOfStream:
            return 0
        except ProtocolError as exc:
            FrameCodec.write_value(sys.stdout.buffer, _error_response({}, exc))
            continue
        try:
            response, should_exit = state.handle(request)
        except ProtocolError as exc:
            response, should_exit = _error_response(request, exc), False
        except BaseException as exc:
            response, should_exit = _error_response(
                request,
                ProtocolError(
                    ErrorCode.INTERNAL,
                    f"worker defect: {type(exc).__name__}",
                ),
            ), False
        FrameCodec.write_value(sys.stdout.buffer, response)
        if should_exit:
            return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--peer-id", required=True)
    parser.add_argument("--store", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(args.peer_id, args.store)


if __name__ == "__main__":
    raise SystemExit(main())
