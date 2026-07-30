from __future__ import annotations

import base64
import json
from pathlib import Path

from adapters.process import FrameCodec, ProcessClient, ProcessTranscript
from shongket_core import codec

from .helpers import (
    build_process_object,
    inventory,
    put_fragment,
    require_ok,
    seed_all,
    seed_metadata,
    transfer_fragment,
)


def test_at38_two_fresh_processes_transfer_and_reconstruct(tmp_path: Path):
    value = build_process_object()
    transcript = ProcessTranscript()
    sender = ProcessClient(
        peer_id="peer-sender",
        store_path=tmp_path / "sender.json",
        transcript=transcript,
    )
    receiver = ProcessClient(
        peer_id="peer-receiver",
        store_path=tmp_path / "receiver.json",
        transcript=transcript,
    )
    try:
        assert sender.process_id != receiver.process_id
        seed_all(sender, value)
        seed_metadata(receiver, value)
        for index in range(len(value.payloads)):
            result = transfer_fragment(sender, receiver, value, index)
            assert result["stored"] is True

        completed = require_ok(
            receiver.request(
                "complete",
                {
                    "object_id": value.object_id,
                    "representation_id": "original",
                },
            )
        )
        assert completed["sha256"] == value.object_id
        assert completed["byte_count"] == len(value.source)
        assert completed["chunk_count"] == len(value.payloads)
        assert all(
            record.body_bytes <= FrameCodec.MAX_BODY_BYTES
            for record in transcript.records
        )
        assert transcript.digest() == transcript.digest()
    finally:
        sender.close()
        receiver.close()


def test_at39_both_processes_match_every_committed_serialization_vector(
    tmp_path: Path,
):
    root = Path(__file__).resolve().parents[3]
    vectors = json.loads(
        (root / "shongket_core" / "testdata" / "golden_vectors.json").read_text(
            encoding="utf-8"
        )
    )
    clients = [
        ProcessClient(peer_id="peer-A", store_path=tmp_path / "a.json"),
        ProcessClient(peer_id="peer-B", store_path=tmp_path / "b.json"),
    ]
    try:
        for vector in vectors["serialization"]:
            expected = vector["canonical_text"].encode("utf-8")
            expected_b64 = base64.b64encode(expected).decode("ascii")
            for client in clients:
                result = require_ok(
                    client.request("canonicalize", {"value": vector["value"]})
                )
                assert result["canonical_b64"] == expected_b64, vector["name"]
                assert result["byte_count"] == vector["byte_length"], vector["name"]
                assert result["sha256"] == vector["sha256"], vector["name"]
                assert result["sha256"] == codec.sha256_hex(
                    codec.canonical_bytes(vector["value"])
                )
    finally:
        for client in clients:
            client.close()


def test_at40_interruption_resumes_with_only_missing_indexes(tmp_path: Path):
    value = build_process_object()
    sender = ProcessClient(
        peer_id="peer-sender",
        store_path=tmp_path / "sender.json",
    )
    receiver_path = tmp_path / "receiver.json"
    receiver = ProcessClient(peer_id="peer-receiver", store_path=receiver_path)
    try:
        seed_all(sender, value)
        seed_metadata(receiver, value)
        transferred = (0, 1)
        for index in transferred:
            transfer_fragment(sender, receiver, value, index)
        receiver.close()

        receiver = ProcessClient(
            peer_id="peer-receiver",
            store_path=receiver_path,
        )
        require_ok(receiver.request("put_manifest", {"manifest": value.manifest}))
        before = inventory(receiver, value)
        assert before["chunk_indexes"] == list(transferred)
        missing = sorted(set(range(len(value.payloads))) - set(transferred))
        assert missing == list(range(2, len(value.payloads)))

        for index in missing:
            transfer_fragment(sender, receiver, value, index)
        after = inventory(receiver, value)
        assert after["chunk_indexes"] == list(range(len(value.payloads)))
        assert after["fragment_count"] == len(value.payloads)
        assert after["used_bytes"] == len(value.source)
        completed = require_ok(
            receiver.request(
                "complete",
                {
                    "object_id": value.object_id,
                    "representation_id": "original",
                },
            )
        )
        assert completed["sha256"] == value.object_id
    finally:
        sender.close()
        receiver.close()


def _crash_restart_run(run_dir: Path) -> tuple[str, dict, str]:
    value = build_process_object()
    transcript = ProcessTranscript()
    sender = ProcessClient(
        peer_id="peer-sender",
        store_path=run_dir / "sender.json",
    )
    receiver_path = run_dir / "receiver.json"
    receiver = ProcessClient(
        peer_id="peer-receiver",
        store_path=receiver_path,
        transcript=transcript,
    )
    try:
        seed_all(sender, value)
        seed_metadata(receiver, value)
        for index in (0, 1, 2):
            transfer_fragment(sender, receiver, value, index)
        receiver.kill()

        receiver = ProcessClient(
            peer_id="peer-receiver",
            store_path=receiver_path,
            transcript=transcript,
        )
        require_ok(receiver.request("put_manifest", {"manifest": value.manifest}))
        recovered = inventory(receiver, value)
        assert recovered["chunk_indexes"] == [0, 1, 2]
        missing = sorted(
            set(range(len(value.payloads))) - set(recovered["chunk_indexes"])
        )
        for index in missing:
            transfer_fragment(sender, receiver, value, index)
        completed = require_ok(
            receiver.request(
                "complete",
                {
                    "object_id": value.object_id,
                    "representation_id": "original",
                },
            )
        )
        final_inventory = inventory(receiver, value)
        return transcript.digest(), final_inventory, completed["sha256"]
    finally:
        sender.close()
        receiver.close()


def test_at41_killed_receiver_recovers_deterministically(tmp_path: Path):
    first = _crash_restart_run(tmp_path / "run-a")
    second = _crash_restart_run(tmp_path / "run-b")
    assert first[0] == second[0]
    assert first[1] == second[1]
    assert first[2] == second[2]
    assert first[1]["chunk_indexes"] == list(
        range(len(build_process_object().payloads))
    )
    assert first[1]["used_bytes"] == len(build_process_object().source)


def test_corrupted_fragment_is_refused_without_mutation(tmp_path: Path):
    value = build_process_object()
    client = ProcessClient(peer_id="peer-receiver", store_path=tmp_path / "state.json")
    try:
        seed_metadata(client, value)
        payload = bytearray(value.payloads[0])
        payload[0] ^= 0x01
        response = client.request(
            "put_fragment",
            {
                "descriptor": value.descriptors[0],
                "payload_b64": base64.b64encode(payload).decode("ascii"),
            },
        )
        assert response["ok"] is False
        assert response["error"]["code"] == "SCHEMA_INVALID"
        assert inventory(client, value)["chunk_indexes"] == []
        assert put_fragment(client, value, 0)["stored"] is True
    finally:
        client.close()
