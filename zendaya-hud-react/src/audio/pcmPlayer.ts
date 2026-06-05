/**
 * pcmPlayer.ts — pure PCM decode helpers (no Web Audio dependency).
 *
 * The backend tees ElevenLabs pcm_22050 (signed 16-bit little-endian, mono)
 * over the WebSocket as base64. These two functions turn one base64 window
 * into the Float32Array a Web Audio AudioBuffer wants.
 */

/** Decode base64 → little-endian Int16Array. A trailing odd byte is dropped. */
export function decodeBase64ToInt16(b64: string): Int16Array {
  if (!b64) return new Int16Array(0);
  const binary = atob(b64);
  const len = binary.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);
  // View as Int16 over the whole-sample byte length (drop a trailing odd byte).
  const sampleCount = len >> 1;
  const out = new Int16Array(sampleCount);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < sampleCount; i++) {
    out[i] = view.getInt16(i * 2, true /* little-endian */);
  }
  return out;
}

/** Normalize Int16 PCM into Web-Audio float range [-1, 1]. */
export function int16ToFloat32(samples: Int16Array): Float32Array {
  const out = new Float32Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    out[i] = samples[i] / 32768;
  }
  return out;
}
