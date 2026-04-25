import Opus from "opusscript";

export class OpusRecorderWrapper {
  private encoder: any;
  sampleRate = 48000;
  channels = 1;
  frameSize = 960;

  constructor() {
    this.encoder = new (Opus as any)(this.sampleRate, this.channels, 2049);
  }

  encode(pcm16: Int16Array): Uint8Array {
    // encode returns Buffer
    const encoded = this.encoder.encode(pcm16);
    return new Uint8Array(encoded);
  }
}
