function createMockWebSocketClass() {
  class MockWebSocket {
    static OPEN = 1;
    static CONNECTING = 0;
    static CLOSED = 3;

    static instances = [];

    constructor(url) {
      this.url = url;
      this.readyState = MockWebSocket.CONNECTING;
      this.send = jest.fn();
      this.onopen = null;
      this.onmessage = null;
      this.onclose = null;
      this.onerror = null;
      MockWebSocket.instances.push(this);
    }

    close() {
      this.readyState = MockWebSocket.CLOSED;
      if (typeof this.onclose === "function") {
        this.onclose();
      }
    }
  }

  return MockWebSocket;
}

describe("services/websocket", () => {
  let wsService;
  let MockWebSocket;
  let logSpy;
  let errorSpy;
  const wsEnvKeys = [
    "REACT_APP_WS_URL",
    "REACT_APP_WS_PATH",
    "REACT_APP_WS_HOST",
    "REACT_APP_WS_PORT",
  ];

  beforeEach(() => {
    jest.resetModules();
    jest.useFakeTimers();

    logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    MockWebSocket = createMockWebSocketClass();
    global.WebSocket = MockWebSocket;
    wsEnvKeys.forEach((key) => {
      delete process.env[key];
    });
    wsService = require("./websocket");
  });

  afterEach(() => {
    wsService.disconnectWS();
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    logSpy.mockRestore();
    errorSpy.mockRestore();
    wsEnvKeys.forEach((key) => {
      delete process.env[key];
    });
    delete global.WebSocket;
  });

  test("resolveWsUrl should default to localhost:8000/ws in local dev", () => {
    expect(wsService.resolveWsUrl()).toBe("ws://localhost:8000/ws");
  });

  test("resolveWsUrl should normalize REACT_APP_WS_URL from https", () => {
    process.env.REACT_APP_WS_URL = "https://api.example.com";
    expect(wsService.resolveWsUrl()).toBe("wss://api.example.com/ws");
  });

  test("connectWS should use configured host/port/path", () => {
    process.env.REACT_APP_WS_HOST = "127.0.0.1";
    process.env.REACT_APP_WS_PORT = "9000";
    process.env.REACT_APP_WS_PATH = "/stream";

    wsService.connectWS();

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe("ws://127.0.0.1:9000/stream");
  });

  test("disconnectWS should not auto-reconnect", () => {
    wsService.connectWS();
    expect(MockWebSocket.instances).toHaveLength(1);

    wsService.disconnectWS();
    jest.advanceTimersByTime(3100);

    expect(MockWebSocket.instances).toHaveLength(1);
  });

  test("unexpected close should schedule reconnect", () => {
    wsService.connectWS();
    expect(MockWebSocket.instances).toHaveLength(1);

    const first = MockWebSocket.instances[0];
    first.readyState = MockWebSocket.CLOSED;
    first.onclose();

    jest.advanceTimersByTime(3000);

    expect(MockWebSocket.instances).toHaveLength(2);
  });
});
