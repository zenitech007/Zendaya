export interface QueueTrack {
  id: string;
  title: string;
  artist: string;
  duration_ms: number;
  stream_url: string;
}

/** The track after `currentId` (wraps to first). Empty → null; unknown id → first. */
export function nextTrack(list: QueueTrack[], currentId: string | null | undefined): QueueTrack | null {
  if (list.length === 0) return null;
  const i = list.findIndex((t) => t.id === currentId);
  if (i === -1) return list[0];
  return list[(i + 1) % list.length];
}

/** The track before `currentId` (wraps to last). Empty → null; unknown id → first. */
export function prevTrack(list: QueueTrack[], currentId: string | null | undefined): QueueTrack | null {
  if (list.length === 0) return null;
  const i = list.findIndex((t) => t.id === currentId);
  if (i === -1) return list[0];
  return list[(i - 1 + list.length) % list.length];
}
