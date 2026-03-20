let ws = null;
let reconnectTimer = null;
let pingTimer = null;
let latestOnMessage = null;
let manualDisconnect = false;

const typeListeners = new Map();
const anyListeners = new Set();

function clearReconnectTimer() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function clearPingTimer() {
  if (pingTimer) {
    clearInterval(pingTimer);
    pingTimer = null;
  }
}

function normalizeEvent(raw) {
  if (!raw || typeof raw !== "object") {
    return { type: "unknown", version: 1, ts: Date.now(), payload: raw };
  }
  const type = String(raw.type || "unknown");
  const version = Number(raw.version || 1);
  const ts = raw.ts || Date.now();
  const payload = raw.payload ?? raw.data ?? null;
  return { type, version, ts, payload, raw };
}

function emit(rawMessage) {
  const event = normalizeEvent(rawMessage);
  anyListeners.forEach((listener) => listener(event));
  const typed = typeListeners.get(event.type);
  if (typed) {
    typed.forEach((listener) => listener(event));
  }
}

function scheduleReconnect() {
  clearReconnectTimer();
  reconnectTimer = setTimeout(() => {
    connectWS(latestOnMessage);
  }, 3000);
}

export function connectWS(onMessage) {
  latestOnMessage = onMessage || latestOnMessage;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  manualDisconnect = false;

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.hostname;
  ws = new WebSocket(`${protocol}://${host}:8000/ws`);

  ws.onopen = () => {
    clearReconnectTimer();
    clearPingTimer();
    console.log("[WS] Connected");
    pingTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 20000);
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (latestOnMessage) latestOnMessage(msg);
      emit(msg);
    } catch (_) {
      // Ignore malformed payloads from network jitter.
    }
  };

  ws.onclose = () => {
    clearPingTimer();
    ws = null;
    if (manualDisconnect) {
      manualDisconnect = false;
      console.log("[WS] Disconnected manually.");
      return;
    }
    console.log("[WS] Disconnected, reconnecting in 3s...");
    scheduleReconnect();
  };

  ws.onerror = (e) => console.error("[WS] Error", e);
}

export function subscribeWSEvent(type, listener) {
  const key = String(type || "").trim();
  if (!key) return () => {};
  if (!typeListeners.has(key)) {
    typeListeners.set(key, new Set());
  }
  const group = typeListeners.get(key);
  group.add(listener);
  return () => {
    group.delete(listener);
    if (group.size === 0) {
      typeListeners.delete(key);
    }
  };
}

export function subscribeWSAny(listener) {
  anyListeners.add(listener);
  return () => anyListeners.delete(listener);
}

export function disconnectWS() {
  clearReconnectTimer();
  clearPingTimer();
  if (ws) {
    manualDisconnect = true;
    ws.close();
    ws = null;
  }
}
