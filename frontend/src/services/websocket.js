let ws = null;
const listeners = {};

export function connectWS(onMessage) {
  if (ws && ws.readyState === WebSocket.OPEN) return;
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.hostname;
  ws = new WebSocket(`${protocol}://${host}:8000/ws`);

  ws.onopen = () => {
    console.log('[WS] Connected');
    // Keep-alive ping
    setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping');
    }, 20000);
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (onMessage) onMessage(msg);
    } catch (_) {}
  };

  ws.onclose = () => {
    console.log('[WS] Disconnected, reconnecting in 3s...');
    setTimeout(() => connectWS(onMessage), 3000);
  };

  ws.onerror = (e) => console.error('[WS] Error', e);
}

export function disconnectWS() {
  if (ws) { ws.close(); ws = null; }
}
