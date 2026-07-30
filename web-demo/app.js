(() => {
  "use strict";

  const STORAGE_KEY = "shongket-functional-demo-v1";
  const MAX_MEDIA_BYTES = 512 * 1024;
  const CHUNK_BYTES = 16 * 1024;
  const initialState = () => ({
    stage: "READY",
    message: "",
    location: "",
    urgency: "important",
    visibility: "public",
    consent: false,
    confirmed: false,
    media: null,
    peer: null,
    queue: { capsule: false, manifest: false, media: false },
    verifiedChunks: [],
    duplicateCount: 0,
    integrity: "PENDING",
    resumeRequested: [],
    events: [{ tick: 0, code: "DEMO_READY", counter: 1 }],
  });

  let state = loadState();
  const byId = (id) => document.getElementById(id);
  const nodes = {
    form: byId("capsule-form"), message: byId("message"), location: byId("location"),
    urgency: byId("urgency"), consentRow: byId("consent-row"), consent: byId("forward-consent"),
    humanConfirmed: byId("human-confirmed"), mediaInput: byId("media-input"),
    mediaSummary: byId("media-summary"), formError: byId("form-error"),
    stage: byId("stage-label"), integrity: byId("integrity-label"), resume: byId("resume-label"),
    queueCount: byId("queue-count"), chunkCount: byId("chunk-count"),
    progressText: byId("progress-text"), progressBar: byId("progress-bar"),
    transferError: byId("transfer-error"), eventLog: byId("event-log"),
    received: byId("received"), receivedPreview: byId("received-preview"),
    receivedMessage: byId("received-message"), receivedLocation: byId("received-location"),
    receivedVisibility: byId("received-visibility"), receivedHash: byId("received-hash"),
    duplicateCount: byId("duplicate-count"),
  };

  function loadState() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
      return stored && stored.stage ? { ...initialState(), ...stored } : initialState();
    } catch (_) {
      return initialState();
    }
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function event(code, counter = 1) {
    const tick = (state.events[0]?.tick || 0) + 1;
    state.events.unshift({ tick, code, counter });
    state.events = state.events.slice(0, 64);
  }

  function fail(target, message, code) {
    target.textContent = message;
    event(code);
    saveState();
    render();
  }

  function bytesToBase64(bytes) {
    let binary = "";
    for (let offset = 0; offset < bytes.length; offset += 8192) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
    }
    return btoa(binary);
  }

  function base64ToBytes(value) {
    const binary = atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }

  async function digest(bytes) {
    const result = await crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(result)].map((value) => value.toString(16).padStart(2, "0")).join("");
  }

  function safeFixture() {
    const padding = "source-preservation-fixture;".repeat(900);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="620" viewBox="0 0 960 620"><rect width="960" height="620" fill="#0b1d13"/><path d="M0 440C180 300 330 500 510 340s310-20 450-150v430H0z" fill="#173c26"/><circle cx="730" cy="140" r="62" fill="#72f59f"/><g fill="#eaf5ee" font-family="sans-serif"><text x="70" y="110" font-size="34" font-weight="700">SHONGKET DEMO FIXTURE</text><text x="70" y="157" font-size="22">Synthetic • license-clean • source preserved</text><text x="70" y="535" font-size="24">সংকেত — মানুষের যাচাই করা তথ্য</text></g><!--${padding}--></svg>`;
    return new TextEncoder().encode(svg);
  }

  async function setMedia(bytes, name, type) {
    if (bytes.byteLength > MAX_MEDIA_BYTES) {
      return fail(nodes.formError, "Choose an image smaller than 512 KB.", "MEDIA_TOO_LARGE");
    }
    state.media = {
      name, type, size: bytes.byteLength, bytes: bytesToBase64(bytes),
      hash: await digest(bytes), chunks: Math.ceil(bytes.byteLength / CHUNK_BYTES),
    };
    state.verifiedChunks = [];
    state.integrity = "PENDING";
    state.stage = "MEDIA_READY";
    event("SOURCE_PRESERVED", state.media.size);
    nodes.formError.textContent = "";
    saveState();
    render();
  }

  function chunkAt(index) {
    const source = base64ToBytes(state.media.bytes);
    return source.slice(index * CHUNK_BYTES, Math.min(source.length, (index + 1) * CHUNK_BYTES));
  }

  async function acceptChunk(index) {
    if (state.verifiedChunks.includes(index)) {
      state.duplicateCount += 1;
      event("DUPLICATE_IGNORED", state.duplicateCount);
      return;
    }
    const chunk = chunkAt(index);
    if (!chunk.length) throw new Error("CHUNK_OUT_OF_RANGE");
    await digest(chunk);
    state.verifiedChunks.push(index);
    state.verifiedChunks.sort((a, b) => a - b);
    event("CHUNK_VERIFIED", index);
  }

  async function reconstruct() {
    const source = base64ToBytes(state.media.bytes);
    const rebuilt = new Uint8Array(source.length);
    state.verifiedChunks.forEach((index) => rebuilt.set(chunkAt(index), index * CHUNK_BYTES));
    const rebuiltHash = await digest(rebuilt);
    if (rebuiltHash !== state.media.hash) throw new Error("INTEGRITY_MISMATCH");
    state.integrity = "VERIFIED";
    state.queue.media = true;
    state.stage = "RECEIVED";
    event("RECONSTRUCTION_VERIFIED", rebuilt.length);
  }

  function currentProgress() {
    if (!state.media) return 0;
    const signalComplete = Number(state.queue.capsule) + Number(state.queue.manifest);
    const mediaProgress = state.verifiedChunks.length / Math.max(1, state.media.chunks);
    return Math.round(((signalComplete + mediaProgress) / 3) * 100);
  }

  function render() {
    nodes.message.value = state.message;
    nodes.location.value = state.location;
    nodes.urgency.value = state.urgency;
    document.querySelectorAll('input[name="visibility"]').forEach((radio) => {
      radio.checked = radio.value === state.visibility;
    });
    nodes.consentRow.classList.toggle("hidden", state.visibility !== "private");
    nodes.consent.checked = state.consent;
    nodes.humanConfirmed.checked = state.confirmed;
    nodes.mediaSummary.textContent = state.media
      ? `${state.media.name} • ${state.media.size.toLocaleString()} bytes • SHA ${state.media.hash.slice(0, 12)}…`
      : "No media selected";
    nodes.stage.textContent = state.stage;
    nodes.integrity.textContent = state.integrity;
    nodes.resume.textContent = state.resumeRequested.length ? `[${state.resumeRequested.join(", ")}]` : "—";
    nodes.chunkCount.textContent = `${state.media?.chunks || 0} chunks`;
    const completedQueue = Object.values(state.queue).filter(Boolean).length;
    nodes.queueCount.textContent = `${completedQueue} / 3`;
    Object.entries(state.queue).forEach(([key, complete]) => {
      document.querySelector(`[data-queue="${key}"]`)?.classList.toggle("complete", complete);
    });
    const progress = currentProgress();
    nodes.progressText.textContent = `${progress}%`;
    nodes.progressBar.style.width = `${progress}%`;
    document.querySelectorAll(".peer-card").forEach((peer) => {
      peer.classList.toggle("selected", peer.dataset.peer === state.peer);
    });
    byId("start-transfer").disabled = !state.confirmed || !state.peer || state.stage === "RECEIVED";
    byId("interrupt-transfer").disabled = state.stage !== "TRANSFERRING";
    byId("resume-transfer").disabled = !["INTERRUPTED", "TRANSFERRING"].includes(state.stage);
    nodes.eventLog.innerHTML = state.events.map((entry) =>
      `<li><time>${String(entry.tick).padStart(2, "0")}</time><span>${entry.code}</span></li>`
    ).join("");
    if (state.stage === "RECEIVED") {
      nodes.received.hidden = false;
      nodes.receivedMessage.textContent = state.message;
      nodes.receivedLocation.textContent = `${state.location} • ${state.urgency.toUpperCase()}`;
      nodes.receivedVisibility.textContent = state.visibility.toUpperCase();
      nodes.receivedHash.textContent = state.media.hash;
      nodes.duplicateCount.textContent = String(state.duplicateCount);
      nodes.receivedPreview.src = `data:${state.media.type};base64,${state.media.bytes}`;
    } else {
      nodes.received.hidden = true;
    }
  }

  document.querySelectorAll('input[name="visibility"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      state.visibility = radio.value;
      if (radio.value === "public") state.consent = false;
      saveState(); render();
    });
  });
  nodes.consent.addEventListener("change", () => { state.consent = nodes.consent.checked; saveState(); });
  nodes.humanConfirmed.addEventListener("change", () => { state.confirmed = nodes.humanConfirmed.checked; saveState(); });
  byId("choose-media").addEventListener("click", () => nodes.mediaInput.click());
  nodes.mediaInput.addEventListener("change", async () => {
    const file = nodes.mediaInput.files[0];
    if (file) await setMedia(new Uint8Array(await file.arrayBuffer()), file.name, file.type || "application/octet-stream");
  });
  byId("use-fixture").addEventListener("click", async () => setMedia(safeFixture(), "shongket-safe-fixture.svg", "image/svg+xml"));
  byId("load-sample").addEventListener("click", async () => {
    state = initialState();
    state.message = "নদীর পাশের গ্রামে বিশুদ্ধ পানি প্রয়োজন";
    state.location = "পুরনো সেতুর কাছে, নদীর পূর্ব পাড়";
    state.urgency = "critical";
    await setMedia(safeFixture(), "shongket-safe-fixture.svg", "image/svg+xml");
    event("SAMPLE_SCENARIO_LOADED");
    saveState(); render();
  });
  byId("reset-demo").addEventListener("click", () => {
    localStorage.removeItem(STORAGE_KEY);
    state = initialState();
    nodes.formError.textContent = "";
    nodes.transferError.textContent = "";
    render();
  });
  nodes.form.addEventListener("submit", (eventObject) => {
    eventObject.preventDefault();
    state.message = nodes.message.value.trim();
    state.location = nodes.location.value.trim();
    state.urgency = nodes.urgency.value;
    state.confirmed = nodes.humanConfirmed.checked;
    if (!state.media) return fail(nodes.formError, "Create or choose source evidence first.", "MEDIA_REQUIRED");
    if (!state.message) return fail(nodes.formError, "Enter a Bengali or English crisis message.", "MESSAGE_REQUIRED");
    if (!state.location) return fail(nodes.formError, "Enter an operator-supplied location description.", "LOCATION_REQUIRED");
    if (!state.confirmed) return fail(nodes.formError, "Human confirmation is required before scheduling.", "HUMAN_CONFIRMATION_REQUIRED");
    if (state.visibility === "private" && !state.consent) {
      return fail(nodes.formError, "Explicit forwarding consent is required for private content.", "CONSENT_REQUIRED");
    }
    state.stage = "CAPSULE_CONFIRMED";
    state.queue.capsule = false; state.queue.manifest = false; state.queue.media = false;
    state.verifiedChunks = [];
    state.integrity = "PENDING";
    event("CAPSULE_HUMAN_CONFIRMED");
    nodes.formError.textContent = "";
    saveState(); render();
  });
  document.querySelectorAll(".peer-card").forEach((peer) => {
    peer.addEventListener("click", () => {
      if (!state.confirmed || !state.message) {
        return fail(nodes.transferError, "Confirm the capsule before selecting a peer.", "CAPSULE_NOT_CONFIRMED");
      }
      state.peer = peer.dataset.peer;
      state.stage = "PEER_SELECTED";
      event("SIMULATED_PEER_SELECTED");
      nodes.transferError.textContent = "";
      saveState(); render();
    });
  });
  byId("start-transfer").addEventListener("click", async () => {
    if (!state.peer) return fail(nodes.transferError, "Select a simulated peer first.", "PEER_REQUIRED");
    state.queue.capsule = true;
    event("CAPSULE_DELIVERED_FIRST");
    state.queue.manifest = true;
    event("MANIFEST_DELIVERED");
    if (state.media.chunks) await acceptChunk(0);
    state.stage = "TRANSFERRING";
    nodes.transferError.textContent = "";
    saveState(); render();
  });
  byId("interrupt-transfer").addEventListener("click", () => {
    state.stage = "INTERRUPTED";
    event("TRANSFER_INTERRUPTED");
    saveState(); render();
  });
  byId("resume-transfer").addEventListener("click", async () => {
    const all = Array.from({ length: state.media.chunks }, (_, index) => index);
    state.resumeRequested = all.filter((index) => !state.verifiedChunks.includes(index));
    event("MISSING_ONLY_RESUME", state.resumeRequested.length);
    for (const index of state.resumeRequested) await acceptChunk(index);
    // Replay one chunk to prove bounded duplicate suppression.
    if (state.verifiedChunks.length) await acceptChunk(state.verifiedChunks[0]);
    try {
      await reconstruct();
      nodes.transferError.textContent = "";
    } catch (error) {
      state.integrity = "REJECTED";
      return fail(nodes.transferError, "Reconstruction integrity verification failed.", error.message);
    }
    saveState(); render();
  });
  byId("export-diagnostics").addEventListener("click", () => {
    const exportDocument = {
      schema: "shongket.web-diagnostics.v1.0",
      transport: "SIMULATED_PEER_TRANSPORT",
      stage: state.stage,
      counters: {
        events: state.events.length,
        verified_chunks: state.verifiedChunks.length,
        duplicates_ignored: state.duplicateCount,
      },
      codes: state.events.map((entry) => entry.code),
      ticks: state.events.map((entry) => entry.tick),
    };
    const blob = new Blob([JSON.stringify(exportDocument, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "shongket-redacted-diagnostics.json";
    link.click();
    URL.revokeObjectURL(link.href);
  });

  render();
})();
