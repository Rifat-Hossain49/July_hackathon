from __future__ import annotations

import base64
from dataclasses import dataclass

from adapters.process import ProcessClient
from shongket_core import codec


@dataclass(frozen=True)
class ProcessObject:
    source: bytes
    object_id: str
    capsule: dict
    manifest: dict
    descriptors: tuple[dict, ...]
    payloads: tuple[bytes, ...]


def build_process_object(chunk_size: int = 64) -> ProcessObject:
    source = (
        b"Shongket deterministic two-process source bytes. "
        b"Verified fragments survive interruption. "
    ) * 5
    object_id = codec.sha256_hex(source)
    payloads = tuple(
        source[index : index + chunk_size]
        for index in range(0, len(source), chunk_size)
    )
    descriptors = []
    cursor = 0
    for index, body in enumerate(payloads):
        descriptors.append(
            {
                "schema": "shongket.fragment.v1.0",
                "object_id": object_id,
                "representation_id": "original",
                "chunk_index": index,
                "chunk_size": chunk_size,
                "byte_range": [cursor, cursor + len(body) - 1],
                "hash": codec.sha256_hex(body),
            }
        )
        cursor += len(body)

    capsule = {
        "schema": "shongket.capsule.v1.0",
        "capsule_id": "c" * 64,
        "object_ref": object_id,
        "source_media_ref": object_id,
        "human_confirmed": True,
        "confirmation_method": "manual_form_only",
        "creator_pub_key_id": "development-test-key",
        "created_at_unix": 1_700_000_000,
        "extracted_fields": {"summary_bn": "জল বাড়ছে"},
        "signatures": [],
    }
    manifest = {
        "schema": "shongket.content.v1.0",
        "object_id": object_id,
        "capsule_ref": capsule["capsule_id"],
        "representations": [
            {
                "id": "original",
                "byte_len": len(source),
                "chunk_size": chunk_size,
                "hash": object_id,
                "hashes": [descriptor["hash"] for descriptor in descriptors],
            }
        ],
        "priority": "life_safety",
        "created_at_unix": 1_700_000_000,
        "expires_at_unix": None,
        "hop_limit": 6,
        "copy_budget": 8,
        "visibility": "public",
        "signatures": [],
    }
    return ProcessObject(
        source=source,
        object_id=object_id,
        capsule=capsule,
        manifest=manifest,
        descriptors=tuple(descriptors),
        payloads=payloads,
    )


def require_ok(response: dict) -> dict:
    assert response["ok"] is True, response
    return response["result"]


def seed_metadata(client: ProcessClient, value: ProcessObject) -> None:
    require_ok(client.request("put_capsule", {"capsule": value.capsule}))
    require_ok(client.request("put_manifest", {"manifest": value.manifest}))


def put_fragment(
    client: ProcessClient,
    value: ProcessObject,
    index: int,
) -> dict:
    return require_ok(
        client.request(
            "put_fragment",
            {
                "descriptor": value.descriptors[index],
                "payload_b64": base64.b64encode(value.payloads[index]).decode("ascii"),
            },
        )
    )

def seed_all(client: ProcessClient, value: ProcessObject) -> None:
    seed_metadata(client, value)
    for index in range(len(value.payloads)):
        put_fragment(client, value, index)


def transfer_fragment(
    sender: ProcessClient,
    receiver: ProcessClient,
    value: ProcessObject,
    index: int,
) -> dict:
    exported = require_ok(
        sender.request(
            "get_fragment",
            {
                "object_id": value.object_id,
                "representation_id": "original",
                "chunk_index": index,
            },
        )
    )
    return require_ok(receiver.request("put_fragment", exported))


def inventory(client: ProcessClient, value: ProcessObject) -> dict:
    return require_ok(
        client.request(
            "inventory",
            {
                "object_id": value.object_id,
                "representation_id": "original",
            },
        )
    )
