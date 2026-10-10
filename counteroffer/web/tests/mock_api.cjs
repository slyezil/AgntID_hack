// MOCK API for browser interaction tests only. This never calls real providers.
const http = require("node:http");

const state = {
  authenticated: false,
  turnPosts: 0,
  eventConnections: 0,
  lastEventId: "",
  complete: false,
};
const session = {
  buyer_id: "BUYER-A",
  merchant_id: "MERCHANT-01",
  buyer_display_name: "Primary buyer",
  csrf_token: "mock-csrf-token",
  expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
};

function json(response, status, value, extraHeaders = {}) {
  response.writeHead(status, { "Content-Type": "application/json", ...extraHeaders });
  response.end(JSON.stringify(value));
}

const server = http.createServer((request, response) => {
  const url = new URL(request.url ?? "/", "http://127.0.0.1:8000");
  if (url.pathname === "/test-state") {
    return json(response, 200, state);
  }
  if (url.pathname === "/api/session" && request.method === "GET") {
    if (!state.authenticated) {
      return json(response, 401, { error: { message: "Sign in with an invitation code." } });
    }
    return json(response, 200, session);
  }
  if (url.pathname === "/api/session" && request.method === "POST") {
    state.authenticated = true;
    request.resume();
    json(response, 200, session, {
      "Set-Cookie": "counteroffer_session=mock-session; Path=/; HttpOnly; SameSite=Lax",
    });
    return;
  }
  if (url.pathname === "/api/conversations" && request.method === "POST") {
    return json(response, 201, { conversation_id: "00000000-0000-4000-8000-000000000001" });
  }
  if (url.pathname === "/api/conversations/00000000-0000-4000-8000-000000000001") {
    return json(response, 200, { conversation_id: "00000000-0000-4000-8000-000000000001", messages: [], quotes: [] });
  }
  if (url.pathname.endsWith("/turns") && request.method === "POST") {
    state.turnPosts += 1;
    return json(response, 202, {
      turn_id: "00000000-0000-4000-8000-000000000002",
      status: "QUEUED",
      events_url: "/api/turns/00000000-0000-4000-8000-000000000002/events",
      status_url: "/api/turns/00000000-0000-4000-8000-000000000002",
    });
  }
  if (url.pathname === "/api/turns/00000000-0000-4000-8000-000000000002/events") {
    state.eventConnections += 1;
    state.lastEventId = request.headers["last-event-id"] ?? "";
    response.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" });
    if (state.eventConnections === 1) {
      response.write("retry: 250\nid: 1\nevent: turn_started\ndata: {\"turn_id\":\"00000000-0000-4000-8000-000000000002\",\"sequence\":1,\"type\":\"turn_started\",\"data\":{}}\n\n");
      setTimeout(() => response.end(), 80);
      return;
    }
    state.complete = true;
    response.write("id: 2\nevent: assistant_delta\ndata: {\"turn_id\":\"00000000-0000-4000-8000-000000000002\",\"sequence\":2,\"type\":\"assistant_delta\",\"data\":{\"text\":\"Your draft is ready for review.\"}}\n\n");
    response.write("id: 3\nevent: turn_completed\ndata: {\"turn_id\":\"00000000-0000-4000-8000-000000000002\",\"sequence\":3,\"type\":\"turn_completed\",\"data\":{\"status\":\"COMPLETED\"}}\n\n");
    response.end();
    return;
  }
  if (url.pathname === "/api/turns/00000000-0000-4000-8000-000000000002") {
    return json(response, 200, {
      turn_id: "00000000-0000-4000-8000-000000000002",
      status: state.complete ? "COMPLETED" : "RUNNING",
      quotes: [],
      error: null,
      last_sequence: state.complete ? 3 : 1,
    });
  }
  json(response, 404, { error: { message: "Not found" } });
});

server.listen(8000, "127.0.0.1");
