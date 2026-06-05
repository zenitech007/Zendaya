import { describe, expect, it } from "vitest";
import { decodeBase64ToInt16, int16ToFloat32 } from "../audio/pcmPlayer";

// Little-endian int16 [256, 513] => bytes [0x00,0x01, 0x01,0x02] => base64 "AAEBAg=="
const B64_TWO_SAMPLES = "AAEBAg==";

describe("decodeBase64ToInt16", () => {
  it("decodes base64 PCM into little-endian Int16", () => {
    const out = decodeBase64ToInt16(B64_TWO_SAMPLES);
    expect(Array.from(out)).toEqual([256, 513]);
  });

  it("returns an empty array for empty input", () => {
    expect(decodeBase64ToInt16("").length).toBe(0);
  });

  it("drops a trailing odd byte rather than throwing", () => {
    // 3 bytes -> only one whole int16 sample
    const b64 = btoa(String.fromCharCode(0x00, 0x01, 0x7f));
    const out = decodeBase64ToInt16(b64);
    expect(out.length).toBe(1);
    expect(out[0]).toBe(256);
  });
});

describe("int16ToFloat32", () => {
  it("normalizes into [-1, 1]", () => {
    const out = int16ToFloat32(Int16Array.from([0, 32767, -32768]));
    expect(out[0]).toBeCloseTo(0, 5);
    expect(out[1]).toBeCloseTo(0.99997, 4);
    expect(out[2]).toBeCloseTo(-1, 5);
  });

  it("preserves length", () => {
    expect(int16ToFloat32(Int16Array.from([1, 2, 3, 4])).length).toBe(4);
  });
});
