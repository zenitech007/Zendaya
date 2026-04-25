import Opus from "opusscript";

export class OpusRecorderWrapper {
  private encoder: any;
  sampleRate = 48000;
  channels = 1;
  frameSize = 960; // 20ms @ 48kHz

  constructor() {
    this.encoder = new (Opus as any)(
      this.sampleRate,
      this.channels,
      2049 // OPUS_APPLICATION_AUDIO
    );
  }

  encodePCM(float32: Float32Array): Uint8Array {
    const pcm16 = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
      pcm16[i] = Math.max(-1, Math.min(1, float32[i])) * 0x7fff;
    }
    return new Uint8Array(this.encoder.encode(pcm16));
  }
}
