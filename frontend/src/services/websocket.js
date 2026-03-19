let ws = null;
let reconnectTimer = null;
let pingTimer = null;
let latestOnMessage = null;
let manualDisconnect = false;

const typeListeners = new Map();
const anyListeners = new Set();
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "0.0.0.0"]);
const DEFAULT_WS_PATH = "/ws";
const DEFAULT_DEV_BACKEND_PORT = "8000";

function normalizeWsPath(path) {
  const trimmed = String(path || "").trim();
  if (!trimmed) {
    return DEFAULT_WS_PATH;
  }
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
}

function normalizeExplicitWsUrl(rawUrl) {
  const raw = String(rawUrl || "").trim();
  if (!raw) {
    return "";
  }
  const wsPath = normalizeWsPath(process.env.REACT_APP_WS_PATH || DEFAULT_WS_PATH);
  try {
    if (raw.startsWith("ws://") || raw.startsWith("wss://")) {
      const parsed = new URL(raw);
      if (!parsed.pathname || parsed.pathname === "/") {
        parsed.pathname = wsPath;
      }
      return parsed.toString();
    }
    if (raw.startsWith("http://") || raw.startsWith("https://")) {
      const parsed = new URL(raw);
      parsed.protocol = parsed.protocol === "https:" ? "wss:" : "ws:";
      if (!parsed.pathname || parsed.pathname === "/" || parsed.pathname === "/api") {
        parsed.pathname = wsPath;
      }
      return parsed.toString();
    }
    const parsed = new URL(`ws://${raw}`);
    if (!parsed.pathname || parsed.pathname === "/") {
      parsed.pathname = wsPath;
    }
    return parsed.toString();
  } catch (_) {
    return "";
  }
}

function inferWsPort(locationPort, hostname) {
  const overridePort = String(process.env.REACT_APP_WS_PORT || "").trim();
  if (overridePort) {
    return overridePort;
  }
  if (locationPort && locationPort !== "3000") {
    return locationPort;
  }
  if (LOCAL_HOSTS.has(hostname)) {
    return DEFAULT_DEV_BACKEND_PORT;
  }
  return locationPort || "";
}

export function resolveWsUrl() {
  const explicitUrl = normalizeExplicitWsUrl(process.env.REACT_APP_WS_URL);
  if (explicitUrl) {
    return explicitUrl;
  }

  const wsPath = normalizeWsPath(process.env.REACT_APP_WS_PATH || DEFAULT_WS_PATH);
  if (typeof window === "undefined" || !window.location) {
    return `ws://127.0.0.1:${DEFAULT_DEV_BACKEND_PORT}${wsPath}`;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const configuredHost = String(process.env.REACT_APP_WS_HOST || "").trim();
  const hostname = configuredHost || window.location.hostname;
  const port = inferWsPort(window.location.port, hostname);
  const host = port ? `${hostname}:${port}` : hostname;
  return `${protocol}://${host}${wsPath}`;
}

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

  ws = new WebSocket(resolveWsUrl());

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
