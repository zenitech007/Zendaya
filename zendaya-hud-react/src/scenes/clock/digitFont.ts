// 3×5 dot-matrix font for the DigitsFace clock. "1" = lit cell.
export const FONT: Record<string, string[]> = {
  "0": ["111", "101", "101", "101", "111"],
  "1": ["010", "110", "010", "010", "111"],
  "2": ["111", "001", "111", "100", "111"],
  "3": ["111", "001", "111", "001", "111"],
  "4": ["101", "101", "111", "001", "001"],
  "5": ["111", "100", "111", "001", "111"],
  "6": ["111", "100", "111", "101", "111"],
  "7": ["111", "001", "010", "010", "010"],
  "8": ["111", "101", "111", "101", "111"],
  "9": ["111", "101", "111", "001", "111"],
  ":": ["000", "010", "000", "010", "000"],
};

const CHAR_W = 3;
const CHAR_H = 5;
const GAP = 1; // empty columns between characters
const CELL = 0.14; // world units per matrix cell
const SUB = 2; // sub-particles per cell axis (SUB*SUB particles per lit cell)

/**
 * Build a particle point cloud (length = N*3) tracing `text` in the dot-matrix
 * font, centred on the origin in the XY plane with a small Z jitter for depth.
 * Unknown characters fall back to the "0" glyph so this never throws.
 */
export function buildDigitPoints(text: string): Float32Array {
  const totalCols = text.length * CHAR_W + Math.max(0, text.length - 1) * GAP;
  const pts: number[] = [];
  let cursor = 0;
  for (const ch of text) {
    const glyph = FONT[ch] ?? FONT["0"];
    for (let row = 0; row < CHAR_H; row++) {
      for (let col = 0; col < CHAR_W; col++) {
        if (glyph[row][col] !== "1") continue;
        for (let sx = 0; sx < SUB; sx++) {
          for (let sy = 0; sy < SUB; sy++) {
            const gx = cursor + col + (sx + 0.5) / SUB;
            const gy = row + (sy + 0.5) / SUB;
            const x = (gx - totalCols / 2) * CELL;
            const y = (CHAR_H / 2 - gy) * CELL;
            pts.push(x, y, (Math.random() - 0.5) * 0.04);
          }
        }
      }
    }
    cursor += CHAR_W + GAP;
  }
  return new Float32Array(pts);
}
