// Mirrors the WS URL resolution in useWebSocket.ts so the HTTP origin always
// matches the socket the HUD is connected to.
const WS_URL =
  new URLSearchParams(location.search).get("ws") || "ws://127.0.0.1:7475/ws";

/** The http(s) origin of the state server, derived from the WS URL. */
export function backendHttpOrigin(): string {
  try {
    const u = new URL(WS_URL);
    const proto = u.protocol === "wss:" ? "https:" : "http:";
    return `${proto}//${u.host}`;
  } catch {
    return "http://127.0.0.1:7475";
  }
}

/** POST a natural-language command to the backend's /chat handler. */
export async function sendChat(text: string): Promise<void> {
  const res = await fetch(`${backendHttpOrigin()}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text }),
  });
  if (!res.ok) throw new Error(`chat failed: ${res.status}`);
}

/** Ask the backend to shut down cleanly (used by the /quit command). Never throws. */
export async function quit(): Promise<void> {
  await fetch(`${backendHttpOrigin()}/quit`, { method: "POST" }).catch(() => {});
}
