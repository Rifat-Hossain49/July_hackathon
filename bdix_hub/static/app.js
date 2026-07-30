(() => {
  "use strict";

  const SCHEMA = "shongket.bdix.capsule.v1.0";
  const CHANNEL_KEY = "shongket-bdix-channel-v1";
  const OUTBOX_KEY = "shongket-bdix-public-outbox-v1";
  const MAX_OUTBOX = 20;
  const POLL_INTERVAL_MS = 5000;

  const byId = (id) => document.getElementById(id);
  const nodes = {
    networkState: byId("network-state"),
    networkLabel: byId("network-label"),
    heroEyebrow: byId("hero-eyebrow"),
    heroTitle: byId("hero-title"),
    heroSummary: byId("hero-summary"),
    routeCard: byId("route-card"),
    routePeerA: byId("route-peer-a"),
    routePeerB: byId("route-peer-b"),
    routeHubContext: byId("route-hub-context"),
    routeSummary: byId("route-summary"),
    truthText: byId("truth-text"),
    localEntry: byId("local-entry"),
    friendlyLink: byId("friendly-link"),
    friendlyLabel: byId("friendly-label"),
    fallbackLink: byId("fallback-link"),
    bulletinEyebrow: byId("bulletin-eyebrow"),
    fieldStatus: byId("field-status"),
    installApp: byId("install-app"),
    installHelp: byId("install-help"),
    channelForm: byId("channel-form"),
    channel: byId("channel"),
    channelError: byId("channel-error"),
    activeChannel: byId("active-channel"),
    feedSubtitle: byId("feed-subtitle"),
    capsuleForm: byId("capsule-form"),
    message: byId("message"),
    location: byId("location"),
    urgency: byId("urgency"),
    expiry: byId("expiry"),
    humanConfirmed: byId("human-confirmed"),
    publicConsent: byId("public-consent"),
    publishError: byId("publish-error"),
    publishSuccess: byId("publish-success"),
    outboxCount: byId("outbox-count"),
    refreshFeed: byId("refresh-feed"),
    feedNotice: byId("feed-notice"),
    feed: byId("capsule-feed"),
  };

  let activeChannel = "";
  let cursor = 0;
  let feedLoading = false;
  let outboxFlushing = false;
  let installPrompt = null;
  let deploymentMode = "domestic-hub";
  const seenCapsules = new Set();

  const isLocalMode = () => deploymentMode === "local-access-point";
  const reachableLabel = () =>
    isLocalMode() ? "Local laptop hub reachable" : "Domestic hub reachable";
  const unreachableLabel = () =>
    isLocalMode() ? "Local laptop hub unreachable" : "Domestic hub unreachable";
  const hubDescription = () =>
    isLocalMode() ? "local laptop hub" : "domestic hub";

  function normalizedChannel(value) {
    const channel = String(value || "").trim().toUpperCase();
    return /^[A-Z0-9](?:[A-Z0-9-]{1,30}[A-Z0-9])$/.test(channel)
      ? channel
      : "";
  }

  function readOutbox() {
    try {
      const value = JSON.parse(localStorage.getItem(OUTBOX_KEY) || "[]");
      return Array.isArray(value) ? value.slice(0, MAX_OUTBOX) : [];
    } catch (_) {
      return [];
    }
  }

  function writeOutbox(entries) {
    localStorage.setItem(OUTBOX_KEY, JSON.stringify(entries.slice(0, MAX_OUTBOX)));
    renderOutbox();
  }

  function renderOutbox() {
    const entries = readOutbox();
    const retryable = entries.filter((entry) => !entry.terminal_error).length;
    const failed = entries.length - retryable;
    nodes.outboxCount.textContent = failed
      ? `${retryable} queued • ${failed} blocked`
      : `${retryable} queued`;
  }

  function setNetworkState(state, label) {
    nodes.networkState.dataset.state = state;
    nodes.networkLabel.textContent = label;
  }

  function setFeedNotice(message, style = "") {
    nodes.feedNotice.textContent = message;
    nodes.feedNotice.className = `feed-notice${style ? ` ${style}` : ""}`;
  }

  function safeEntryUrl(value) {
    try {
      const url = new URL(String(value || ""));
      if (
        url.protocol !== "http:" ||
        url.username ||
        url.password ||
        (url.pathname !== "/" && url.pathname !== "") ||
        url.search ||
        url.hash
      ) {
        return "";
      }
      return url.href.replace(/\/$/, "");
    } catch (_) {
      return "";
    }
  }

  async function configureDeployment() {
    let status;
    try {
      const response = await fetch("/api/v1/status", { cache: "no-store" });
      status = await responseJson(response);
      if (!response.ok) return;
    } catch (_) {
      return;
    }
    if (status.mode !== "local-access-point") return;
    const friendly = safeEntryUrl(status.entry && status.entry.friendly_url);
    const fallback = safeEntryUrl(status.entry && status.entry.fallback_url);
    if (!friendly || !fallback) return;

    deploymentMode = "local-access-point";
    document.title = "Shongket — Local Wi-Fi Hub";
    nodes.heroEyebrow.textContent = "ONE WI-FI • ONE LOCAL LINK • PUBLIC CAPSULES";
    nodes.heroTitle.textContent = "Talk nearby without Internet.";
    nodes.heroSummary.textContent =
      "This laptop is the Shongket hub. Anyone connected to the same Wi-Fi can open the Wi-Fi link shown below and join a public incident channel.";
    nodes.routeCard.setAttribute("aria-label", "Local Wi-Fi route diagram");
    nodes.routePeerA.textContent = "LAPTOP";
    nodes.routePeerB.textContent = "PHONE / IPAD";
    nodes.routeHubContext.textContent = "SAME ACCESS POINT";
    nodes.routeSummary.textContent = "laptop ↔ local Wi-Fi ↔ nearby browsers";
    nodes.truthText.textContent =
      "The access point needs no Internet uplink. The laptop must stay running, and the Wi-Fi must permit devices and multicast to reach each other.";
    nodes.localEntry.hidden = false;
    nodes.friendlyLink.href = friendly;
    nodes.friendlyLink.textContent = friendly;
    nodes.fallbackLink.href = fallback;
    nodes.fallbackLink.textContent = fallback;
    const friendlyAvailable = status.entry.friendly_available === true;
    nodes.friendlyLabel.hidden = !friendlyAvailable;
    nodes.friendlyLink.hidden = !friendlyAvailable;
    nodes.bulletinEyebrow.textContent = "LOCAL WI-FI CRISIS BULLETIN";
    nodes.fieldStatus.textContent =
      "Android / iPad friendly-name field validation: NOT RUN";
    nodes.installApp.hidden = true;
    nodes.installHelp.textContent =
      "Local HTTP works while connected. Keep this page bookmarked; installable offline mode requires HTTPS.";
  }

  function newClientId() {
    if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  async function responseJson(response) {
    try {
      return await response.json();
    } catch (_) {
      return { error: "INVALID_RESPONSE", detail: "The hub returned an invalid response." };
    }
  }

  function retryableStatus(status) {
    return status === 429 || status === 500 || status === 503 || status === 507;
  }

  async function flushOutbox() {
    if (outboxFlushing) return;
    const initial = readOutbox();
    if (!initial.some((entry) => !entry.terminal_error)) {
      renderOutbox();
      return;
    }
    outboxFlushing = true;
    let entries = initial;
    let published = 0;
    try {
      for (const entry of [...entries]) {
        if (entry.terminal_error) continue;
        let response;
        try {
          response = await fetch("/api/v1/capsules", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(entry.payload),
          });
        } catch (_) {
          setNetworkState("queued", "Hub unreachable • capsule queued");
          setFeedNotice(
            `The ${hubDescription()} is unreachable. Confirmed public capsules remain queued on this device.`,
            "error",
          );
          break;
        }
        const document = await responseJson(response);
        if (response.ok) {
          entries = entries.filter(
            (candidate) => candidate.payload.client_id !== entry.payload.client_id,
          );
          writeOutbox(entries);
          published += 1;
          setNetworkState("ready", reachableLabel());
          continue;
        }
        if (retryableStatus(response.status)) {
          setNetworkState("queued", "Hub busy • capsule queued");
          setFeedNotice(document.detail || "The hub is temporarily busy. The capsule remains queued.", "error");
          break;
        }
        entries = entries.map((candidate) =>
          candidate.payload.client_id === entry.payload.client_id
            ? { ...candidate, terminal_error: document.error || "PUBLISH_REFUSED" }
            : candidate,
        );
        writeOutbox(entries);
        nodes.publishError.textContent =
          `${document.detail || "The hub refused a queued capsule."} (${document.error || "PUBLISH_REFUSED"})`;
      }
      if (published) {
        nodes.publishSuccess.textContent =
          `${published} confirmed public capsule${published === 1 ? "" : "s"} published.`;
        if (activeChannel) await loadFeed();
      }
    } finally {
      outboxFlushing = false;
      renderOutbox();
    }
  }

  function capsuleCard(capsule) {
    const item = document.createElement("li");
    item.className = "capsule-card";

    const meta = document.createElement("div");
    meta.className = "capsule-meta";
    const urgency = document.createElement("span");
    urgency.className = `urgency ${capsule.urgency}`;
    urgency.textContent = capsule.urgency.toUpperCase();
    const time = document.createElement("time");
    time.dateTime = new Date(capsule.received_at_unix * 1000).toISOString();
    time.textContent =
      `${new Date(capsule.received_at_unix * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} • expires ${new Date(capsule.expires_at_unix * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    meta.append(urgency, time);

    const message = document.createElement("p");
    message.className = "capsule-message";
    message.textContent = capsule.message;
    const location = document.createElement("p");
    location.className = "capsule-location";
    location.textContent = `Location: ${capsule.location}`;
    const identity = document.createElement("div");
    identity.className = "capsule-id";
    identity.textContent = `SHA-256 ${capsule.capsule_id.slice(0, 16)}… • cursor ${capsule.cursor}`;
    item.append(meta, message, location, identity);
    return item;
  }

  async function loadFeed() {
    if (!activeChannel || feedLoading) return;
    feedLoading = true;
    try {
      const query = new URLSearchParams({
        channel: activeChannel,
        after: String(cursor),
        limit: "50",
      });
      const response = await fetch(`/api/v1/capsules?${query.toString()}`, {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      const document = await responseJson(response);
      if (!response.ok) {
        throw new Error(document.detail || "The hub refused the feed request.");
      }
      let added = 0;
      for (const capsule of document.capsules || []) {
        if (seenCapsules.has(capsule.capsule_id)) continue;
        seenCapsules.add(capsule.capsule_id);
        nodes.feed.append(capsuleCard(capsule));
        added += 1;
      }
      cursor = Number(document.next_cursor || cursor);
      setNetworkState("ready", reachableLabel());
      setFeedNotice(
        added
          ? `${added} new public capsule${added === 1 ? "" : "s"} received.`
          : "Connected. Waiting for new public capsules.",
        "success",
      );
    } catch (error) {
      setNetworkState(readOutbox().length ? "queued" : "offline", unreachableLabel());
      setFeedNotice(
        `Cannot reach the ${hubDescription()}. Confirmed outgoing capsules stay queued on this device.`,
        "error",
      );
    } finally {
      feedLoading = false;
    }
  }

  function joinChannel(channel) {
    activeChannel = channel;
    cursor = 0;
    seenCapsules.clear();
    nodes.feed.replaceChildren();
    nodes.activeChannel.textContent = channel;
    nodes.feedSubtitle.textContent = `Polling ${channel} through this ${hubDescription()}.`;
    nodes.channel.value = channel;
    localStorage.setItem(CHANNEL_KEY, channel);
    nodes.channelError.textContent = "";
    setFeedNotice("Connecting to the public channel…");
    loadFeed();
    flushOutbox();
  }

  nodes.channelForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const channel = normalizedChannel(nodes.channel.value);
    if (!channel) {
      nodes.channelError.textContent =
        "Use 3–32 letters, numbers or internal hyphens, for example DHAKA-RELIEF.";
      return;
    }
    joinChannel(channel);
  });

  nodes.capsuleForm.addEventListener("submit", (event) => {
    event.preventDefault();
    nodes.publishError.textContent = "";
    nodes.publishSuccess.textContent = "";
    if (!activeChannel) {
      nodes.publishError.textContent = "Join an incident channel before publishing.";
      return;
    }
    const message = nodes.message.value.trim();
    const location = nodes.location.value.trim();
    if (!message) {
      nodes.publishError.textContent = "Enter a Bengali or English crisis message.";
      return;
    }
    if (!location) {
      nodes.publishError.textContent = "Enter an operator-supplied location description.";
      return;
    }
    if (!nodes.humanConfirmed.checked) {
      nodes.publishError.textContent = "Human review confirmation is required.";
      return;
    }
    if (!nodes.publicConsent.checked) {
      nodes.publishError.textContent = "Confirm that the message and location may be public.";
      return;
    }
    const entries = readOutbox();
    if (entries.length >= MAX_OUTBOX) {
      nodes.publishError.textContent =
        "This device already holds 20 queued capsules. Reconnect before adding another.";
      return;
    }
    entries.push({
      queued_at_unix: Math.floor(Date.now() / 1000),
      payload: {
        schema: SCHEMA,
        client_id: newClientId(),
        channel: activeChannel,
        message,
        location,
        urgency: nodes.urgency.value,
        visibility: "public",
        human_confirmed: true,
        public_forwarding_consent: true,
        expires_in_seconds: Number(nodes.expiry.value),
      },
    });
    writeOutbox(entries);
    nodes.message.value = "";
    nodes.location.value = "";
    nodes.humanConfirmed.checked = false;
    nodes.publicConsent.checked = false;
    nodes.publishSuccess.textContent = "Confirmed capsule saved to this device's outbox.";
    flushOutbox();
  });

  nodes.refreshFeed.addEventListener("click", () => {
    loadFeed();
    flushOutbox();
  });

  window.addEventListener("online", () => {
    setNetworkState("checking", `Reconnecting to ${hubDescription()}`);
    flushOutbox();
    loadFeed();
  });
  window.addEventListener("offline", () => {
    if (isLocalMode()) {
      setNetworkState("checking", "Checking local laptop hub");
      flushOutbox();
      loadFeed();
      return;
    }
    setNetworkState("offline", "Network unavailable");
    setFeedNotice("No network route is currently available. Outgoing capsules remain queued.", "error");
  });

  window.addEventListener("beforeinstallprompt", (event) => {
    if (isLocalMode()) return;
    event.preventDefault();
    installPrompt = event;
    nodes.installHelp.textContent = "This browser can install Shongket. Use the button above.";
  });
  nodes.installApp.addEventListener("click", async () => {
    if (!installPrompt) {
      nodes.installHelp.textContent =
        "iPad/iPhone: Safari → Share → Add to Home Screen. Android/desktop: use the browser Install app menu.";
      return;
    }
    installPrompt.prompt();
    await installPrompt.userChoice;
    installPrompt = null;
  });

  async function registerOfflineShell() {
    if (isLocalMode() && !window.isSecureContext) return;
    if (!("serviceWorker" in navigator)) {
      nodes.installHelp.textContent =
        "This browser cannot cache the app shell. The website still works while connected.";
      return;
    }
    try {
      await navigator.serviceWorker.register("/service-worker.js");
      await navigator.serviceWorker.ready;
    } catch (_) {
      nodes.installHelp.textContent =
        "Offline shell setup failed. Reload once over HTTPS and try again.";
    }
  }

  async function start() {
    await configureDeployment();
    renderOutbox();
    const savedChannel = normalizedChannel(localStorage.getItem(CHANNEL_KEY));
    if (savedChannel) joinChannel(savedChannel);
    else {
      setNetworkState("checking", "Select an incident channel");
      fetch("/healthz", { cache: "no-store" })
        .then((response) => {
          if (!response.ok) throw new Error("health refused");
          setNetworkState("ready", reachableLabel());
        })
        .catch(() => setNetworkState("offline", unreachableLabel()));
    }
    registerOfflineShell();
    window.setInterval(() => {
      flushOutbox();
      loadFeed();
    }, POLL_INTERVAL_MS);
  }
  start();
})();
