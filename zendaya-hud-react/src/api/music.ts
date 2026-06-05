import { backendHttpOrigin } from "./backend";
import type { QueueTrack } from "../music/queue";

/** GET the local library as a queue. Returns [] on any failure. */
export async function fetchTrackList(): Promise<QueueTrack[]> {
  try {
    const res = await fetch(`${backendHttpOrigin()}/music/list`);
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? (data as QueueTrack[]) : [];
  } catch {
    return [];
  }
}

/** Absolute <audio> source URL for a track id or a relative stream_url. */
export function streamUrl(idOrUrl: string): string {
  const origin = backendHttpOrigin();
  return idOrUrl.startsWith("/") ? `${origin}${idOrUrl}` : `${origin}/music/stream/${idOrUrl}`;
}

/** Tell the backend what the HUD is playing now (best-effort; ignores failure). */
export async function postNowPlaying(body: {
  track_id: string | null;
  is_playing: boolean;
  position_ms: number;
}): Promise<void> {
  try {
    await fetch(`${backendHttpOrigin()}/music/now`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    /* ignore */
  }
}
