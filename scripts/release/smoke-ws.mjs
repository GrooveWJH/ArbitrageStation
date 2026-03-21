const wsBase = process.env.WS_BASE || "ws://127.0.0.1:8000/ws";
const timeoutMs = Number(process.env.WS_TIMEOUT_MS || 15000);
const minEvents = Number(process.env.WS_MIN_EVENTS || 1);

if (typeof WebSocket === "undefined") {
  console.error("[smoke-ws] global WebSocket is unavailable. Use Node.js 20+.");
  process.exit(127);
}

let validatedCount = 0;
let finished = false;
const types = new Set();

const finish = (code, message) => {
  if (finished) return;
  finished = true;
  console.log(message);
  process.exit(code);
};

const timer = setTimeout(() => {
  finish(
    1,
    `[smoke-ws] timeout waiting for events (validated=${validatedCount}, required=${minEvents})`,
  );
}, timeoutMs);

const ws = new WebSocket(wsBase);

ws.onopen = () => {
  console.log(`[smoke-ws] connected ${wsBase}`);
};

ws.onerror = (event) => {
  clearTimeout(timer);
  const errorMessage = event?.message ? String(event.message) : "websocket error";
  finish(1, `[smoke-ws] ${errorMessage}`);
};

ws.onmessage = (event) => {
  let payload;
  try {
    payload = JSON.parse(String(event.data || ""));
  } catch {
    return;
  }

  const hasType = typeof payload.type === "string" && payload.type.trim().length > 0;
  const hasVersion = Number.isFinite(Number(payload.version));
  const hasTs = payload.ts !== undefined && payload.ts !== null;
  const hasPayloadField =
    Object.prototype.hasOwnProperty.call(payload, "payload") ||
    Object.prototype.hasOwnProperty.call(payload, "data");

  if (hasType && hasVersion && hasTs && hasPayloadField) {
    validatedCount += 1;
    types.add(payload.type);
  }

  if (validatedCount >= minEvents) {
    clearTimeout(timer);
    ws.close();
    finish(
      0,
      `[smoke-ws] envelope validation passed (events=${validatedCount}, types=${[...types].join(",")})`,
    );
  }
};

ws.onclose = () => {
  if (!finished && validatedCount < minEvents) {
    clearTimeout(timer);
    finish(1, "[smoke-ws] closed before receiving enough valid events");
  }
};
