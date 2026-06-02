/**
 * Per-theme ambient-synth timbre params. Maps the active theme id to the
 * shaping values AmbientEngine.applyTheme() crossfades the oscillator bank to.
 * Forge = warmer/lower; Iris = airier/higher. No audio files — synth only.
 */
export interface AmbientParams {
  baseFreq: number;    // core hum fundamental (Hz)
  harmonicMix: number; // scales the energy-texture voice gain
  airFreq: number;     // orbital-air oscillator frequency (Hz)
  brightness: number;  // scales the texture-voice frequency (220 Hz * brightness)
}

const TABLE: Record<string, AmbientParams> = {
  forge: { baseFreq: 52, harmonicMix: 1.0, airFreq: 150, brightness: 0.8 },
  iris:  { baseFreq: 64, harmonicMix: 0.7, airFreq: 230, brightness: 1.25 },
};

export function ambientParamsFor(id: string): AmbientParams {
  return TABLE[id] ?? TABLE.forge;
}
