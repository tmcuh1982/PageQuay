// Use in a trusted client. A client key is supplied by the caller, never hardcoded.
export async function subscribe(baseUrl, project, apiKey, onEvent) {
  const response = await fetch(`${baseUrl}/v1/projects/${encodeURIComponent(project)}/ws-ticket`, {
    method: "POST", headers: {Authorization: `Bearer ${apiKey}`}
  });
  if (!response.ok) throw new Error(`Ticket refused: ${response.status}`);
  const {ticket, websocket_path} = await response.json();
  const url = new URL(websocket_path, baseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(url);
  socket.addEventListener("open", () => socket.send(JSON.stringify({ticket})));
  socket.addEventListener("message", event => onEvent(JSON.parse(event.data)));
  return socket;
}
