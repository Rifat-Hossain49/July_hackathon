"""Single-call scenario builder for the M0 vertical slice.

Produces the deterministic inputs to every test:

* a synthetic source payload (deterministic via ``random.Random(seed)``);
* the canonical ``object_id`` (SHA-256 of the source bytes);
* a manually supplied semantic capsule;
* a content manifest with multiple progressive representations
  (``thumb``, ``preview``, ``standard``, ``original``);
* a fixed-size chunk plan per representation;
* two simulated peers (sender holds everything; receiver holds nothing).

The builder is the single source of truth for fixture shape; tests do
not duplicate it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import capsule, chunks, hashutil, media, manifest
from .peer import SimulatedPeer


# Representation sizes for the M0 slice. Each representation is a
# deterministic truncation of the synthetic source bytes so the
# ``object_id`` invariant for AT-21 (``original`` hash equals SHA-256 of
# the original source bytes) is preserved. AT-04 verifies that all four
# representations coexist with no fragment-key collision; AT-21 verifies
# the source bytes and their hash remain unchanged after the encounter.
_REPRESENTATION_SIZES: dict[str, int] = {
    "thumb": 8 * 1024,
    "preview": 32 * 1024,
    "standard": 80 * 1024,
    "original": 200 * 1024,
}


@dataclass(frozen=True)
class TwoPeerScenario:
    seed: int
    chunk_size: int
    source_bytes: bytes
    object_id: str
    capsule: dict
    manifest: dict
    chunk_plan: chunks.ChunkPlan
    plans: dict[str, chunks.ChunkPlan] = field(default_factory=dict)
    sender: SimulatedPeer = field(default_factory=lambda: SimulatedPeer(peer_id="peer-A"))
    receiver: SimulatedPeer = field(default_factory=lambda: SimulatedPeer(peer_id="peer-B"))


def build_two_peer_scenario(
    *,
    seed: int = 42,
    chunk_size: int = 65536,
    source_size_bytes: int = 200_000,
    priority: str = "life_safety",
) -> TwoPeerScenario:
    """Build a deterministic two-peer scenario for the M0 slice.

    Parameters
    ----------
    seed:
        Seed for the synthetic source media generator.
    chunk_size:
        Fixed chunk size in bytes. The original representation uses
        the full ``source_size_bytes``; smaller representations use a
        deterministic truncation of the same source bytes so the
        ``original`` representation hash is preserved for AT-21.
    source_size_bytes:
        Synthetic source payload size for ``"original"``. Defaults to
        200 KB so several chunks are produced.
    priority:
        Manifest priority tag.
    """
    # Use the requested size for "original"; smaller representations are
    # deterministic truncations so the source-hash invariant holds.
    source_bytes = media.synthetic_source_bytes(seed, source_size_bytes)
    object_id = media.object_id_from_source(source_bytes)

    cap = capsule.build_capsule(
        object_id=object_id,
        summary_bn="Biporjo area te jolobhironto somoy ki korle bachar upay hote pare.",
        event_type="flood",
        urgency="life_safety",
        location_text="Biporjo, Khulna",
        required_action="Uttar dike othobi uncha sthan e jaao",
        required_resource="Dry shelter, drinking water",
        human_confirmed=True,
        confirmation_method="manual_form_only",
        created_at_unix=1_700_000_000,
    )

    fragmenter = chunks.FixedSizeFragmenter(chunk_size)
    plans: dict[str, chunks.ChunkPlan] = {}
    representations: list[dict] = []
    for rep_id, rep_size in _REPRESENTATION_SIZES.items():
        # Deterministic truncation for non-original representations:
        # smaller views of the same source bytes, so the original hash
        # is unaffected and AT-21 invariants hold.
        rep_payload = source_bytes[:rep_size] if rep_id != "original" else source_bytes
        plan = fragmenter.fragment(
            object_id=object_id,
            representation_id=rep_id,
            payload=rep_payload,
        )
        plans[rep_id] = plan
        representations.append(
            {
                "id": rep_id,
                "kind": _MIME_FOR_REP[rep_id],
                "byte_len": len(rep_payload),
                "chunk_size": chunk_size,
                "hashes": [c.sha256 for c in plan.chunks],
                "rep_sha256": plan.representation_hash,
            }
        )

    mfst = manifest.build_manifest(
        object_id=object_id,
        capsule_id=cap["capsule_id"],
        representations=representations,
        priority=priority,
        created_at_unix=1_700_000_000,
    )

    sender = SimulatedPeer(peer_id="peer-A")
    receiver = SimulatedPeer(peer_id="peer-B")

    return TwoPeerScenario(
        seed=seed,
        chunk_size=chunk_size,
        source_bytes=source_bytes,
        object_id=object_id,
        capsule=cap,
        manifest=mfst,
        chunk_plan=plans["original"],
        plans=plans,
        sender=sender,
        receiver=receiver,
    )


_MIME_FOR_REP: dict[str, str] = {
    "thumb": "image/jpeg",
    "preview": "video/mp4",
    "standard": "application/octet-stream",
    "original": "application/octet-stream",
}


def schedule_full_transfer(scenario: TwoPeerScenario) -> list:
    """Build the scheduler item list for a full transfer of one object.

    Includes the manifest, the semantic capsule and every chunk of every
    representation. The deterministic priority order then ensures
    capsule-before-media for AT-01.
    """
    from . import priority as pri

    items: list[pri.SchedulerItem] = []
    items.append(pri.SchedulerItem.manifest(object_id=scenario.object_id, manifest_id=scenario.manifest["manifest_id"]))
    items.append(pri.SchedulerItem.capsule(object_id=scenario.object_id, capsule_id=scenario.capsule["capsule_id"], urgency="life_safety"))
    for plan in scenario.plans.values():
        for c in plan.chunks:
            items.append(
                pri.SchedulerItem.chunk(
                    object_id=scenario.object_id,
                    representation_id=c.representation_id,
                    chunk_index=c.chunk_index,
                )
            )
    return pri.order(items)


def all_chunks(scenario: TwoPeerScenario) -> list[chunks.Chunk]:
    """Return every media fragment across every representation, in tier order."""
    from . import priority as pri

    items = schedule_full_transfer(scenario)
    plan_by_key = {
        (scenario.object_id, rep, idx): c
        for rep, plan in scenario.plans.items()
        for idx, c in enumerate(plan.chunks)
    }
    out: list[chunks.Chunk] = []
    for it in items:
        if it.chunk_index is None or it.representation_id is None:
            continue
        chunk = plan_by_key.get((it.object_id, it.representation_id, it.chunk_index))
        if chunk is not None:
            out.append(chunk)
    return out
