from __future__ import annotations

import ast
import json
import socket
from pathlib import Path

import pytest

from adapters.process import ProcessSession, SocketFrameEndpoint
from adapters.transport_sim import (
    InMemoryNetwork,
    PeerRef,
    SimulatedTransportAdapter,
    TransportEventKind,
    TransportFailure,
)
from shongket_core import codec
from shongket_core.capabilities import (
    NegotiatedCapabilities,
    PeerCapabilities,
    ensure_payload_fits,
    negotiate_capabilities,
)
from shongket_core.errors import ErrorCode, ProtocolError


def _caps(peer_id: str, *transports: str, limit: int = 1024, public=False):
    return PeerCapabilities(
        peer_id=peer_id,
        transports=tuple(transports),
        max_payload=limit,
        public_only=public,
    )


def test_at42_simulated_adapter_discovery_capabilities_and_events():
    network = InMemoryNetwork()
    first = SimulatedTransportAdapter(network, _caps("peer-A", "simulated"))
    second = SimulatedTransportAdapter(network, _caps("peer-B", "simulated"))
    assert first.discover() == (PeerRef("peer-B"),)
    assert first.capabilities(PeerRef("peer-B")) == second.capability_report()

    sender = first.connect(PeerRef("peer-B"))
    receiver = second.connect(PeerRef("peer-A"))
    body = codec.canonical_bytes({"schema": "shongket.capsule.v1.0"})
    assert sender.send(body).accepted
    assert receiver.receive() == body
    sender.interrupt()
    sender.close()
    assert [event.kind for event in sender.events()] == [
        TransportEventKind.CONNECTED,
        TransportEventKind.PROGRESS,
        TransportEventKind.INTERRUPTED,
        TransportEventKind.CLOSED,
    ]


def test_at42_process_and_simulated_sessions_have_event_parity():
    body = codec.canonical_bytes({"schema": "shongket.capsule.v1.0"})
    network = InMemoryNetwork()
    first = SimulatedTransportAdapter(network, _caps("a", "simulated"))
    second = SimulatedTransportAdapter(network, _caps("b", "simulated"))
    simulated_sender = first.connect(PeerRef("b"))
    simulated_receiver = second.connect(PeerRef("a"))
    simulated_sender.send(body)
    assert simulated_receiver.receive() == body
    simulated_sender.interrupt()
    simulated_sender.close()

    left, right = socket.socketpair()
    negotiated = NegotiatedCapabilities("stdio", 1024, False)
    process_sender = ProcessSession(SocketFrameEndpoint(left), negotiated)
    process_receiver = ProcessSession(SocketFrameEndpoint(right), negotiated)
    process_sender.send(body)
    assert process_receiver.receive() == body
    process_sender.interrupt()
    process_sender.close()
    process_receiver.close()

    assert [event.as_dict() for event in process_sender.events()] == [
        event.as_dict() for event in simulated_sender.events()
    ]


def test_at43_negotiation_uses_intersection_lower_limit_and_receiver_flag():
    sender = _caps("a", "loopback", "stdio", limit=900)
    receiver = _caps("b", "stdio", "loopback", limit=400, public=True)
    result = negotiate_capabilities(
        sender,
        receiver,
        enabled_transports=("stdio", "loopback"),
    )
    assert result.accepted
    assert result.negotiated == NegotiatedCapabilities(
        transport="loopback",
        max_payload=400,
        receiver_public_only=True,
    )


def test_at43_committed_capability_vectors_match_core_results():
    root = Path(__file__).resolve().parents[3]
    vectors = json.loads(
        (
            root
            / "shongket_core"
            / "testdata"
            / "m2_process_vectors.json"
        ).read_text(encoding="utf-8")
    )
    for vector in vectors["capability_negotiation"]:
        sender = PeerCapabilities(
            **{
                **vector["sender"],
                "transports": tuple(vector["sender"]["transports"]),
            }
        )
        receiver = PeerCapabilities(
            **{
                **vector["receiver"],
                "transports": tuple(vector["receiver"]["transports"]),
            }
        )
        result = negotiate_capabilities(
            sender,
            receiver,
            enabled_transports=vector["enabled_transports"],
        )
        expected = vector["expected"]
        assert result.accepted is expected["accepted"], vector["name"]
        if result.accepted:
            assert result.negotiated is not None
            assert result.negotiated.as_dict() == {
                key: expected[key]
                for key in (
                    "transport",
                    "max_payload",
                    "receiver_public_only",
                )
            }
        else:
            assert result.reason == expected["reason"]


@pytest.mark.parametrize(
    "sender,receiver,enabled,reason",
    [
        (
            _caps("a", "stdio"),
            _caps("b", "loopback"),
            ("stdio", "loopback"),
            "no_usable_transport",
        ),
        (
            _caps("a", "stdio", limit=0),
            _caps("b", "stdio"),
            ("stdio",),
            "non_positive_payload_limit",
        ),
        (
            _caps("a", "stdio"),
            _caps("b", "stdio"),
            (),
            "no_usable_transport",
        ),
    ],
)
def test_at43_incompatible_pairs_decline_cleanly(
    sender,
    receiver,
    enabled,
    reason,
):
    result = negotiate_capabilities(
        sender,
        receiver,
        enabled_transports=enabled,
    )
    assert not result.accepted
    assert result.negotiated is None
    assert result.reason == reason


def test_at43_over_limit_refusal_is_a_canonical_core_error():
    with pytest.raises(ProtocolError) as caught:
        ensure_payload_fits(33, 32)
    assert caught.value.code is ErrorCode.PAYLOAD_TOO_LARGE
    assert caught.value.__class__.__module__ == "shongket_core.errors"


def test_at43_empty_payload_is_refused_before_transmission():
    with pytest.raises(ProtocolError) as caught:
        ensure_payload_fits(0, 32)
    assert caught.value.code is ErrorCode.SCHEMA_INVALID


class _NoWriteEndpoint:
    def __init__(self) -> None:
        self.send_count = 0

    def send(self, body: bytes) -> None:
        self.send_count += 1

    def receive(self) -> bytes:
        raise AssertionError("receive was not expected")

    def close(self) -> None:
        pass


def test_at44_process_binding_cannot_turn_core_size_refusal_into_a_send():
    endpoint = _NoWriteEndpoint()
    session = ProcessSession(
        endpoint,  # type: ignore[arg-type]
        NegotiatedCapabilities("stdio", 16, False),
    )
    body = codec.canonical_bytes({"payload": "too large"})
    with pytest.raises(ProtocolError) as caught:
        session.send(body)
    assert caught.value.code is ErrorCode.PAYLOAD_TOO_LARGE
    assert endpoint.send_count == 0


def test_at44_adapter_sources_do_not_reference_forwarding_fields():
    root = Path(__file__).resolve().parents[3]
    forbidden = {
        "expiry",
        "expires",
        "consent",
        "visibility",
        "hop_limit",
        "hop_count",
        "copy_budget",
        "remaining_copy",
        "admission",
    }
    findings = []
    for path in sorted((root / "adapters").rglob("*.py")):
        if "tests" in path.parts:
            continue
        lowered = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            if token in lowered:
                findings.append((path.relative_to(root).as_posix(), token))
    assert findings == []


def test_at44_core_imports_no_adapter():
    root = Path(__file__).resolve().parents[3]
    findings = []
    for path in sorted((root / "shongket_core").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".", 1)[0]]
            else:
                continue
            if "adapters" in names:
                findings.append(path.name)
    assert findings == []


def test_closed_and_interrupted_sessions_fail_without_hanging():
    network = InMemoryNetwork()
    first = SimulatedTransportAdapter(network, _caps("a", "simulated"))
    SimulatedTransportAdapter(network, _caps("b", "simulated"))
    session = first.connect(PeerRef("b"))
    session.interrupt()
    with pytest.raises(TransportFailure, match="session_interrupted"):
        session.send(b"{}")
    session.close()
    with pytest.raises(TransportFailure, match="session_closed"):
        session.receive()
