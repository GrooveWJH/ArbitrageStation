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

  beforeEach(() => {
    jest.resetModules();
    jest.useFakeTimers();

    logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    MockWebSocket = createMockWebSocketClass();
    global.WebSocket = MockWebSocket;
    wsService = require("./websocket");
  });

  afterEach(() => {
    wsService.disconnectWS();
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    logSpy.mockRestore();
    errorSpy.mockRestore();
    delete global.WebSocket;
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
