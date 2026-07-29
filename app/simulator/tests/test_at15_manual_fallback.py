"""AT-15 -- AI fallback to the structured manual form.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-15, M0, S1):

    with the model disabled or low-confidence, requesting confirmation
    on a capsule draft presents a structured manual form.

Evidence required: fallback log.
Automation: "M0 unit (model disabled path)".

Canonical basis: D-011 ("if the local model is unavailable or too slow,
the user must be able to create the semantic capsule through a compact
structured form") and SYSTEM_ARCHITECTURE.md's failure-mode row "Model
failure | automatic fallback to manual form (D-011)".

M0 runs no model. Nothing here loads, downloads or calls one, and no
external API is contacted; ``model_state`` only *declares* the canonical
condition. The fallback never fabricates a summary: ``ai_output`` is
always ``None``, so no generated text can be mistaken for model output
or overwrite what a human typed.
"""

from __future__ import annotations

import io

import pytest

from app.simulator import capsule, events, gate, hashutil, scenario, validation


def _logger():
    return events.EventLogger(sink=io.StringIO())


def _manual_capsule(object_id: str, form_values: dict) -> dict:
    """Build a capsule from manual-form values, as the UI layer would."""
    return capsule.build_capsule(
        object_id=object_id,
        summary_bn=form_values["summary_bn"],
        event_type=form_values["event_type"],
        urgency=form_values["urgency"],
        location_text=form_values["location_text"],
        required_action=form_values["required_action"],
        required_resource=form_values["required_resource"],
        human_confirmed=True,
        confirmation_method="manual_form_only",
        created_at_unix=1_700_000_000,
    )


_GOOD_FORM = {
    "event_type": "flood",
    "location_text": "Biporjo, Khulna",
    "urgency": "life_safety",
    "affected_people": "unknown",
    "required_action": "Uttar dike othobi uncha sthan e jaao",
    "required_resource": "Dry shelter, drinking water",
    "summary_bn": "Jol bere jacche, druto uncha jaygay jaan.",
}


# --- every canonical model condition falls back ------------------------------


@pytest.mark.parametrize(
    "model_state",
    [
        gate.MODEL_DISABLED,
        gate.MODEL_UNAVAILABLE,
        gate.MODEL_FAILED,
        gate.MODEL_LOW_CONFIDENCE,
    ],
)
def test_model_condition_falls_back_to_manual_form(model_state):
    scen = scenario.build_two_peer_scenario()
    logger = _logger()

    form = gate.manual_form_fallback(
        model_state=model_state,
        logger=logger,
        sender_id=scen.sender.peer_id,
        receiver_id=scen.receiver.peer_id,
        object_id=scen.object_id,
    )

    # A structured form is presented, with the canonical capsule fields.
    assert form["schema"] == "shongket.manualform.v1"
    assert tuple(form["fields"]) == gate.MANUAL_FORM_FIELDS
    assert set(gate.MANUAL_FORM_FIELDS) <= {
        "event_type",
        "location_text",
        "urgency",
        "affected_people",
        "required_action",
        "required_resource",
        "summary_bn",
    }

    # No fabricated model output, and the form starts empty.
    assert form["ai_output"] is None
    assert form["content_source"] == gate.SOURCE_MANUAL_FORM
    assert all(value == "" for value in form["fields"].values())

    # Deterministic fallback evidence.
    fallbacks = logger.of_type(events.EventType.MODEL_FALLBACK)
    assert len(fallbacks) == 1
    detail = fallbacks[0].detail
    assert detail["model_state"] == model_state
    assert detail["reason"] == "model_unavailable"
    assert detail["content_source"] == gate.SOURCE_MANUAL_FORM
    assert detail["ai_output_present"] is False
    assert detail["confirmation_method"] == "manual_form_only"
    assert fallbacks[0].object_id == scen.object_id


def test_model_condition_does_not_crash_or_block_manual_entry():
    """A failed model must not raise, and must not stop the manual path."""
    scen = scenario.build_two_peer_scenario()
    logger = _logger()

    # Returns normally: no exception escapes for any canonical state.
    gate.manual_form_fallback(
        model_state=gate.MODEL_FAILED,
        logger=logger,
        sender_id="peer-A",
        receiver_id="peer-B",
        object_id=scen.object_id,
    )

    # The manual capsule still builds, validates and passes the human gate.
    manual = _manual_capsule(scen.object_id, _GOOD_FORM)
    validation.validate_payload("shongket.capsule.v1", manual)
    gate.capsule_human_confirmation(
        manual, logger=logger, sender_id="peer-A", receiver_id="peer-B"
    )
    assert manual["human_confirmed"] is True
    assert manual["confirmation_method"] == "manual_form_only"


def test_unknown_model_state_is_rejected_not_silently_accepted():
    logger = _logger()
    with pytest.raises(validation.ProtocolError) as excinfo:
        gate.manual_form_fallback(
            model_state="totally_fine_actually",
            logger=logger,
            sender_id="peer-A",
            receiver_id="peer-B",
        )
    assert excinfo.value.code == "SCHEMA_INVALID"
    assert logger.of_type(events.EventType.MODEL_FALLBACK) == []


# --- the manual capsule still passes every existing gate ---------------------


def test_manual_capsule_passes_schema_human_confirmation_and_scheduling():
    scen = scenario.build_two_peer_scenario()
    logger = _logger()
    from app.simulator import ingress, priority

    gate.manual_form_fallback(
        model_state=gate.MODEL_DISABLED,
        logger=logger,
        sender_id=scen.sender.peer_id,
        receiver_id=scen.receiver.peer_id,
        object_id=scen.object_id,
    )
    manual = _manual_capsule(scen.object_id, _GOOD_FORM)

    # 1. schema validation
    validation.validate_payload("shongket.capsule.v1", manual)
    # 2. human confirmation gate
    gate.capsule_human_confirmation(
        manual,
        logger=logger,
        sender_id=scen.sender.peer_id,
        receiver_id=scen.receiver.peer_id,
    )
    # 3. consent gate -- a public object passes through untouched
    gate.private_content_consent(
        scen.manifest,
        logger=logger,
        sender_id=scen.sender.peer_id,
        receiver_id=scen.receiver.peer_id,
    )
    # 4. normal scheduling via the validated ingress boundary
    queue = ingress.SchedulerIngress()
    item = priority.SchedulerItem.capsule(
        object_id=scen.object_id,
        capsule_id=manual["capsule_id"],
        urgency="life_safety",
    )
    queue.admit(item, payload=manual)
    assert queue.queue_length() == 1
    assert queue.snapshot()[0].tier == priority.TIER_CRITICAL_CAPSULE


def test_manual_input_missing_required_field_is_rejected():
    """An incomplete manual form fails canonical schema validation."""
    scen = scenario.build_two_peer_scenario()
    manual = _manual_capsule(scen.object_id, _GOOD_FORM)
    del manual["object_ref"]

    with pytest.raises(validation.ProtocolError) as excinfo:
        validation.validate_payload("shongket.capsule.v1", manual)
    assert excinfo.value.code == "SCHEMA_INVALID"


def test_manual_input_with_invalid_confirmation_method_is_rejected():
    scen = scenario.build_two_peer_scenario()
    manual = _manual_capsule(scen.object_id, _GOOD_FORM)
    manual["confirmation_method"] = "vibes"

    with pytest.raises(validation.ProtocolError) as excinfo:
        validation.validate_payload("shongket.capsule.v1", manual)
    assert excinfo.value.code == "SCHEMA_INVALID"


def test_unconfirmed_manual_capsule_is_still_blocked():
    """Manual entry does not bypass the AT-02 human-confirmation gate."""
    scen = scenario.build_two_peer_scenario()
    logger = _logger()
    manual = capsule.build_capsule(
        object_id=scen.object_id,
        summary_bn=_GOOD_FORM["summary_bn"],
        human_confirmed=False,
        confirmation_method="manual_form_only",
        created_at_unix=1_700_000_000,
    )
    validation.validate_payload("shongket.capsule.v1", manual)

    with pytest.raises(validation.ProtocolError) as excinfo:
        gate.capsule_human_confirmation(
            manual, logger=logger, sender_id="peer-A", receiver_id="peer-B"
        )
    assert excinfo.value.code == "HUMAN_CONFIRMATION_MISSING"


# --- source media is untouched ----------------------------------------------


def test_fallback_does_not_modify_original_source_media():
    scen = scenario.build_two_peer_scenario()
    source_before = bytes(scen.source_bytes)
    hash_before = hashutil.sha256_hex(source_before)
    logger = _logger()

    gate.manual_form_fallback(
        model_state=gate.MODEL_DISABLED,
        logger=logger,
        sender_id="peer-A",
        receiver_id="peer-B",
        object_id=scen.object_id,
    )
    manual = _manual_capsule(scen.object_id, _GOOD_FORM)

    assert scen.source_bytes == source_before
    assert hashutil.sha256_hex(scen.source_bytes) == hash_before
    assert hash_before == scen.object_id
    # The capsule references the source; it does not replace it.
    assert manual["object_ref"] == scen.object_id
    assert manual["source_media_ref"] == scen.object_id


def test_fallback_is_deterministic():
    logs = []
    forms = []
    for _ in range(2):
        scen = scenario.build_two_peer_scenario()
        sink = io.StringIO()
        logger = events.EventLogger(sink=sink)
        form = gate.manual_form_fallback(
            model_state=gate.MODEL_DISABLED,
            logger=logger,
            sender_id="peer-A",
            receiver_id="peer-B",
            object_id=scen.object_id,
        )
        logs.append(sink.getvalue())
        forms.append(form)
    assert logs[0] == logs[1]
    assert forms[0] == forms[1]
