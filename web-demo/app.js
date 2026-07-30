(() => {
  "use strict";

  const STORAGE_KEY = "shongket-functional-demo-v2";
  const LEGACY_STORAGE_KEY = "shongket-functional-demo-v1";
  const MAX_MEDIA_BYTES = 512 * 1024;
  const CHUNK_BYTES = 16 * 1024;
  const AUTO_COMPLETE_DELAY_MS = 2400;

  const initialState = () => ({
    stage: "READY",
    message: "",
    location: "",
    urgency: "important",
    visibility: "public",
    consent: false,
    confirmed: false,
    capsuleHash: "",
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
  let transferGeneration = 0;
  let deferredInstallPrompt = null;

  const byId = (id) => document.getElementById(id);
  const nodes = {
    form: byId("capsule-form"),
    message: byId("message"),
    location: byId("location"),
    urgency: byId("urgency"),
    consentRow: byId("consent-row"),
    consent: byId("forward-consent"),
    humanConfirmed: byId("human-confirmed"),
    mediaInput: byId("media-input"),
    mediaSummary: byId("media-summary"),
    removeMedia: byId("remove-media"),
    formError: byId("form-error"),
    stage: byId("stage-label"),
    integrity: byId("integrity-label"),
    resume: byId("resume-label"),
    queueCount: byId("queue-count"),
    chunkCount: byId("chunk-count"),
    progressText: byId("progress-text"),
    progressBar: byId("progress-bar"),
    transferGuidance: byId("transfer-guidance"),
    transferError: byId("transfer-error"),
    eventLog: byId("event-log"),
    received: byId("received"),
    receivedGrid: byId("received-grid"),
    receivedPreviewFrame: byId("received-preview-frame"),
    receivedPreview: byId("received-preview"),
    receivedMessage: byId("received-message"),
    receivedLocation: byId("received-location"),
    receivedVisibility: byId("received-visibility"),
    receivedHash: byId("received-hash"),
    verifiedBadge: byId("verified-badge"),
    hashLabel: byId("hash-label"),
    duplicateCount: byId("duplicate-count"),
    offlineStatus: byId("offline-status"),
    installApp: byId("install-app"),
    installHelp: byId("install-help"),
  };

  function loadState() {
    try {
      // Version 1 could persist MEDIA_READY with a completed 2/3 queue.
      // Ignore that incompatible state so deployed users cannot remain trapped.
      localStorage.removeItem(LEGACY_STORAGE_KEY);
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (!stored || !stored.stage) return initialState();
      const restored = {
        ...initialState(),
        ...stored,
        queue: { ...initialState().queue, ...stored.queue },
      };
      if (restored.stage === "TRANSFERRING") {
        restored.stage = "INTERRUPTED";
        const tick = (restored.events?.[0]?.tick || 0) + 1;
        restored.events = [
          { tick, code: "RESTART_RECOVERY_READY", counter: 1 },
          ...(restored.events || []),
        ].slice(0, 64);
      }
      return restored;
    } catch (_) {
      return initialState();
    }
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function recordEvent(code, counter = 1) {
    const tick = (state.events[0]?.tick || 0) + 1;
    state.events.unshift({ tick, code, counter });
    state.events = state.events.slice(0, 64);
  }

  function fail(target, message, code) {
    target.textContent = message;
    recordEvent(code);
    saveState();
    render();
  }

  function resetTransfer({ clearPeer = true } = {}) {
    transferGeneration += 1;
    state.queue = { capsule: false, manifest: false, media: false };
    state.verifiedChunks = [];
    state.duplicateCount = 0;
    state.resumeRequested = [];
    state.integrity = "PENDING";
    if (clearPeer) state.peer = null;
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
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }

  async function digest(bytes) {
    const result = await crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(result)]
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("");
  }

  async function digestCapsule() {
    const canonicalCapsule = JSON.stringify({
      location: state.location,
      message: state.message,
      urgency: state.urgency,
      visibility: state.visibility,
    });
    return digest(new TextEncoder().encode(canonicalCapsule));
  }

  function safeFixture() {
    const padding = "source-preservation-fixture;".repeat(900);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="620" viewBox="0 0 960 620"><rect width="960" height="620" fill="#0b1d13"/><path d="M0 440C180 300 330 500 510 340s310-20 450-150v430H0z" fill="#173c26"/><circle cx="730" cy="140" r="62" fill="#72f59f"/><g fill="#eaf5ee" font-family="sans-serif"><text x="70" y="110" font-size="34" font-weight="700">SHONGKET DEMO FIXTURE</text><text x="70" y="157" font-size="22">Synthetic • license-clean • source preserved</text><text x="70" y="535" font-size="24">সংকেত — মানুষের যাচাই করা তথ্য</text></g><!--${padding}--></svg>`;
    return new TextEncoder().encode(svg);
  }

  async function setMedia(bytes, name, type) {
    if (bytes.byteLength > MAX_MEDIA_BYTES) {
      fail(nodes.formError, "Choose an image smaller than 512 KB.", "MEDIA_TOO_LARGE");
      return;
    }
    resetTransfer();
    state.media = {
      name,
      type,
      size: bytes.byteLength,
      bytes: bytesToBase64(bytes),
      hash: await digest(bytes),
      chunks: Math.ceil(bytes.byteLength / CHUNK_BYTES),
    };
    state.confirmed = false;
    state.capsuleHash = "";
    state.stage = "MEDIA_READY";
    recordEvent("OPTIONAL_SOURCE_ATTACHED", state.media.size);
    nodes.formError.textContent = "";
    nodes.transferError.textContent = "";
    saveState();
    render();
  }

  function removeMedia() {
    if (!state.media) return;
    resetTransfer();
    state.media = null;
    state.confirmed = false;
    state.capsuleHash = "";
    state.stage = "READY";
    nodes.mediaInput.value = "";
    recordEvent("OPTIONAL_SOURCE_REMOVED");
    saveState();
    render();
  }

  function chunkAt(index) {
    if (!state.media) throw new Error("MEDIA_NOT_ATTACHED");
    const source = base64ToBytes(state.media.bytes);
    return source.slice(
      index * CHUNK_BYTES,
      Math.min(source.length, (index + 1) * CHUNK_BYTES),
    );
  }

  async function acceptChunk(index) {
    if (state.verifiedChunks.includes(index)) {
      state.duplicateCount += 1;
      recordEvent("DUPLICATE_IGNORED", state.duplicateCount);
      return;
    }
    const chunk = chunkAt(index);
    if (!chunk.length) throw new Error("CHUNK_OUT_OF_RANGE");
    await digest(chunk);
    state.verifiedChunks.push(index);
    state.verifiedChunks.sort((left, right) => left - right);
    recordEvent("CHUNK_VERIFIED", index);
  }

  async function reconstruct() {
    if (!state.media) throw new Error("MEDIA_NOT_ATTACHED");
    const source = base64ToBytes(state.media.bytes);
    const rebuilt = new Uint8Array(source.length);
    state.verifiedChunks.forEach((index) => {
      rebuilt.set(chunkAt(index), index * CHUNK_BYTES);
    });
    const rebuiltHash = await digest(rebuilt);
    if (rebuiltHash !== state.media.hash) throw new Error("INTEGRITY_MISMATCH");
    state.integrity = "VERIFIED";
    state.queue.media = true;
    state.resumeRequested = [];
    state.stage = "RECEIVED";
    recordEvent("RECONSTRUCTION_VERIFIED", rebuilt.length);
  }

  async function completeMediaTransfer(generation, proveDuplicateSuppression = false) {
    if (generation !== transferGeneration || state.stage === "INTERRUPTED" || !state.media) return;
    const allChunks = Array.from({ length: state.media.chunks }, (_, index) => index);
    state.resumeRequested = allChunks.filter((index) => !state.verifiedChunks.includes(index));
    if (state.resumeRequested.length) {
      recordEvent("MISSING_ONLY_RESUME", state.resumeRequested.length);
    }
    for (const index of state.resumeRequested) {
      if (generation !== transferGeneration || state.stage === "INTERRUPTED") return;
      await acceptChunk(index);
    }
    if (proveDuplicateSuppression && state.verifiedChunks.length) {
      await acceptChunk(state.verifiedChunks[0]);
    }
    try {
      await reconstruct();
      nodes.transferError.textContent = "";
      saveState();
      render();
    } catch (error) {
      state.integrity = "REJECTED";
      fail(
        nodes.transferError,
        "Reconstruction integrity verification failed.",
        error.message,
      );
    }
  }

  function scheduleAutomaticCompletion() {
    const generation = transferGeneration;
    window.setTimeout(() => {
      if (generation === transferGeneration && state.stage === "TRANSFERRING") {
        completeMediaTransfer(generation);
      }
    }, AUTO_COMPLETE_DELAY_MS);
  }

  function currentProgress() {
    const signalComplete = Number(state.queue.capsule) + Number(state.queue.manifest);
    const attachmentProgress = state.media
      ? state.verifiedChunks.length / Math.max(1, state.media.chunks)
      : Number(state.queue.media);
    return Math.round(((signalComplete + attachmentProgress) / 3) * 100);
  }

  function guidanceForStage() {
    const messages = {
      READY: "Write and confirm a message. Adding an image is optional.",
      MEDIA_READY: "Optional image attached. Review and confirm the capsule.",
      CAPSULE_CONFIRMED: "Capsule confirmed. Select a simulated peer.",
      PEER_SELECTED: state.media
        ? "Ready. Start the simulated transfer; it can be interrupted and resumed."
        : "Ready. Start the text-only simulated transfer.",
      TRANSFERRING: "Transferring verified image chunks. Interrupt now to test resume, or wait for automatic completion.",
      INTERRUPTED: "Verified progress was kept. Resume requests only the missing chunks.",
      RECEIVED: state.media
        ? "Message and optional image were reconstructed and verified."
        : "Text-only capsule was received and hash-verified.",
    };
    return messages[state.stage] || "Confirm a capsule, then select a simulated peer.";
  }

  function renderEvents() {
    nodes.eventLog.replaceChildren();
    state.events.forEach((entry) => {
      const item = document.createElement("li");
      const time = document.createElement("time");
      const code = document.createElement("span");
      time.textContent = String(entry.tick).padStart(2, "0");
      code.textContent = entry.code;
      item.append(time, code);
      nodes.eventLog.append(item);
    });
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
      : "No image selected — text-only delivery is supported";
    nodes.removeMedia.classList.toggle("hidden", !state.media);
    nodes.stage.textContent = state.stage;
    nodes.integrity.textContent = state.integrity;
    nodes.resume.textContent = state.resumeRequested.length
      ? `[${state.resumeRequested.join(", ")}]`
      : "—";
    nodes.chunkCount.textContent = state.media
      ? `${state.media.chunks} chunk${state.media.chunks === 1 ? "" : "s"}`
      : "Text only";

    const completedQueue = Object.values(state.queue).filter(Boolean).length;
    nodes.queueCount.textContent = `${completedQueue} / 3`;
    Object.entries(state.queue).forEach(([key, complete]) => {
      document
        .querySelector(`[data-queue="${key}"]`)
        ?.classList.toggle("complete", complete);
    });

    const progress = currentProgress();
    nodes.progressText.textContent = `${progress}%`;
    nodes.progressBar.style.width = `${progress}%`;
    nodes.transferGuidance.textContent = guidanceForStage();
    nodes.transferGuidance.classList.toggle("attention", state.stage === "INTERRUPTED");

    document.querySelectorAll(".peer-card").forEach((peer) => {
      peer.classList.toggle("selected", peer.dataset.peer === state.peer);
    });
    byId("start-transfer").disabled = state.stage !== "PEER_SELECTED";
    byId("interrupt-transfer").disabled = state.stage !== "TRANSFERRING";
    byId("resume-transfer").disabled = state.stage !== "INTERRUPTED";
    renderEvents();

    if (state.stage === "RECEIVED") {
      const hasMedia = Boolean(state.media);
      nodes.received.hidden = false;
      nodes.receivedGrid.classList.toggle("text-only", !hasMedia);
      nodes.receivedPreviewFrame.hidden = !hasMedia;
      nodes.receivedMessage.textContent = state.message;
      nodes.receivedLocation.textContent = `${state.location} • ${state.urgency.toUpperCase()}`;
      nodes.receivedVisibility.textContent = state.visibility.toUpperCase();
      nodes.receivedHash.textContent = hasMedia ? state.media.hash : state.capsuleHash;
      nodes.hashLabel.textContent = hasMedia ? "Evidence hash" : "Capsule hash";
      nodes.verifiedBadge.textContent = hasMedia ? "✓ SHA-256 MATCH" : "✓ CAPSULE HASH VERIFIED";
      nodes.duplicateCount.textContent = String(state.duplicateCount);
      if (hasMedia) {
        nodes.receivedPreview.src = `data:${state.media.type};base64,${state.media.bytes}`;
      } else {
        nodes.receivedPreview.removeAttribute("src");
      }
    } else {
      nodes.received.hidden = true;
    }
  }

  function invalidateConfirmation(nextStage = "READY") {
    resetTransfer();
    state.confirmed = false;
    state.capsuleHash = "";
    state.stage = nextStage;
  }

  document.querySelectorAll('input[name="visibility"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      state.visibility = radio.value;
      if (radio.value === "public") state.consent = false;
      invalidateConfirmation(state.media ? "MEDIA_READY" : "READY");
      saveState();
      render();
    });
  });

  nodes.consent.addEventListener("change", () => {
    state.consent = nodes.consent.checked;
    saveState();
  });
  nodes.humanConfirmed.addEventListener("change", () => {
    state.confirmed = nodes.humanConfirmed.checked;
    saveState();
  });
  byId("choose-media").addEventListener("click", () => nodes.mediaInput.click());
  nodes.mediaInput.addEventListener("change", async () => {
    const file = nodes.mediaInput.files[0];
    if (file) {
      await setMedia(
        new Uint8Array(await file.arrayBuffer()),
        file.name,
        file.type || "application/octet-stream",
      );
    }
  });
  byId("use-fixture").addEventListener("click", async () => {
    await setMedia(safeFixture(), "shongket-safe-fixture.svg", "image/svg+xml");
  });
  nodes.removeMedia.addEventListener("click", removeMedia);

  byId("load-sample").addEventListener("click", () => {
    transferGeneration += 1;
    state = initialState();
    state.message = "নদীর পাশের গ্রামে বিশুদ্ধ পানি প্রয়োজন";
    state.location = "পুরনো সেতুর কাছে, নদীর পূর্ব পাড়";
    state.urgency = "critical";
    recordEvent("TEXT_ONLY_SAMPLE_LOADED");
    nodes.formError.textContent = "";
    nodes.transferError.textContent = "";
    saveState();
    render();
  });

  byId("reset-demo").addEventListener("click", () => {
    transferGeneration += 1;
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(LEGACY_STORAGE_KEY);
    state = initialState();
    nodes.formError.textContent = "";
    nodes.transferError.textContent = "";
    nodes.mediaInput.value = "";
    saveState();
    render();
  });

  nodes.form.addEventListener("submit", async (eventObject) => {
    eventObject.preventDefault();
    state.message = nodes.message.value.trim();
    state.location = nodes.location.value.trim();
    state.urgency = nodes.urgency.value;
    state.confirmed = nodes.humanConfirmed.checked;
    if (!state.message) {
      fail(nodes.formError, "Enter a Bengali or English crisis message.", "MESSAGE_REQUIRED");
      return;
    }
    if (!state.location) {
      fail(
        nodes.formError,
        "Enter an operator-supplied location description.",
        "LOCATION_REQUIRED",
      );
      return;
    }
    if (!state.confirmed) {
      fail(
        nodes.formError,
        "Human confirmation is required before scheduling.",
        "HUMAN_CONFIRMATION_REQUIRED",
      );
      return;
    }
    if (state.visibility === "private" && !state.consent) {
      fail(
        nodes.formError,
        "Explicit forwarding consent is required for private content.",
        "CONSENT_REQUIRED",
      );
      return;
    }

    resetTransfer();
    state.confirmed = true;
    state.capsuleHash = await digestCapsule();
    state.stage = "CAPSULE_CONFIRMED";
    recordEvent("CAPSULE_HUMAN_CONFIRMED");
    if (!state.media) recordEvent("TEXT_ONLY_CAPSULE_READY");
    nodes.formError.textContent = "";
    nodes.transferError.textContent = "";
    saveState();
    render();
  });

  document.querySelectorAll(".peer-card").forEach((peer) => {
    peer.addEventListener("click", () => {
      if (!state.confirmed || !state.message || !state.capsuleHash) {
        fail(
          nodes.transferError,
          "Confirm the capsule before selecting a peer.",
          "CAPSULE_NOT_CONFIRMED",
        );
        return;
      }
      state.peer = peer.dataset.peer;
      state.stage = "PEER_SELECTED";
      recordEvent("SIMULATED_PEER_SELECTED");
      nodes.transferError.textContent = "";
      saveState();
      render();
    });
  });

  byId("start-transfer").addEventListener("click", async () => {
    if (!state.peer) {
      fail(nodes.transferError, "Select a simulated peer first.", "PEER_REQUIRED");
      return;
    }
    if (state.stage !== "PEER_SELECTED") return;

    transferGeneration += 1;
    state.queue.capsule = true;
    recordEvent("CAPSULE_DELIVERED_FIRST");
    state.queue.manifest = true;
    recordEvent("MANIFEST_DELIVERED");
    nodes.transferError.textContent = "";

    if (!state.media) {
      state.queue.media = true;
      state.integrity = "VERIFIED";
      state.stage = "RECEIVED";
      recordEvent("OPTIONAL_ATTACHMENT_OMITTED");
      recordEvent("TEXT_ONLY_DELIVERED");
      recordEvent("CAPSULE_VERIFIED");
      saveState();
      render();
      return;
    }

    state.stage = "TRANSFERRING";
    if (state.media.chunks) await acceptChunk(0);
    saveState();
    render();
    if (state.verifiedChunks.length === state.media.chunks) {
      await completeMediaTransfer(transferGeneration);
    } else {
      scheduleAutomaticCompletion();
    }
  });

  byId("interrupt-transfer").addEventListener("click", () => {
    if (state.stage !== "TRANSFERRING") return;
    transferGeneration += 1;
    state.stage = "INTERRUPTED";
    state.resumeRequested = Array.from(
      { length: state.media?.chunks || 0 },
      (_, index) => index,
    ).filter((index) => !state.verifiedChunks.includes(index));
    recordEvent("TRANSFER_INTERRUPTED");
    saveState();
    render();
  });

  byId("resume-transfer").addEventListener("click", async () => {
    if (state.stage !== "INTERRUPTED" || !state.media) return;
    transferGeneration += 1;
    state.stage = "TRANSFERRING";
    const generation = transferGeneration;
    saveState();
    render();
    await completeMediaTransfer(generation, true);
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
        media_attached: Number(Boolean(state.media)),
      },
      codes: state.events.map((entry) => entry.code),
      ticks: state.events.map((entry) => entry.tick),
    };
    const blob = new Blob([JSON.stringify(exportDocument, null, 2)], {
      type: "application/json",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "shongket-redacted-diagnostics.json";
    link.click();
    URL.revokeObjectURL(link.href);
  });

  window.addEventListener("beforeinstallprompt", (eventObject) => {
    eventObject.preventDefault();
    deferredInstallPrompt = eventObject;
    nodes.installHelp.textContent = "Offline cache is ready. You can also install Shongket from this button.";
  });

  nodes.installApp.addEventListener("click", async () => {
    if (!deferredInstallPrompt) {
      nodes.installHelp.textContent =
        "Offline cache is ready. To install, use your browser menu and choose “Install app” or “Add to Home screen”.";
      return;
    }
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
  });

  async function registerOfflineShell() {
    if (!("serviceWorker" in navigator)) {
      nodes.offlineStatus.classList.add("offline-failed");
      nodes.offlineStatus.lastChild.textContent = " Offline unavailable";
      nodes.installHelp.textContent = "This browser does not support offline app caching.";
      return;
    }
    try {
      await navigator.serviceWorker.register("./service-worker.js");
      await navigator.serviceWorker.ready;
      nodes.offlineStatus.classList.add("offline-ready");
      nodes.offlineStatus.lastChild.textContent = navigator.onLine
        ? " Offline ready"
        : " Offline mode";
    } catch (_) {
      nodes.offlineStatus.classList.add("offline-failed");
      nodes.offlineStatus.lastChild.textContent = " Offline unavailable";
      nodes.installHelp.textContent = "Offline setup failed. Reload once while connected and try again.";
    }
  }

  window.addEventListener("online", () => {
    if (nodes.offlineStatus.classList.contains("offline-ready")) {
      nodes.offlineStatus.lastChild.textContent = " Offline ready";
    }
  });
  window.addEventListener("offline", () => {
    if (nodes.offlineStatus.classList.contains("offline-ready")) {
      nodes.offlineStatus.lastChild.textContent = " Offline mode";
    }
  });
  window.addEventListener("load", registerOfflineShell);

  saveState();
  render();
})();
