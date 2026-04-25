// src/utils/audioStreamer.ts
export async function startAudioStream(onChunkBase64: (base64: string) => void) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const audioCtx = new AudioContext();
  const src = audioCtx.createMediaStreamSource(stream);
  const processor = audioCtx.createScriptProcessor(4096, 1, 1);

  src.connect(processor);
  processor.connect(audioCtx.destination);

  processor.onaudioprocess = (e) => {
    const data = e.inputBuffer.getChannelData(0);
    // convert float32 -> 16-bit PCM
    const buffer = new ArrayBuffer(data.length * 2);
    const view = new DataView(buffer);
    let offset = 0;
    for (let i = 0; i < data.length; i++, offset += 2) {
      let s = Math.max(-1, Math.min(1, data[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    // base64 encode
    const blob = new Blob([view], { type: "audio/wav" });
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = (reader.result as string).split(",")[1];
      onChunkBase64(base64);
    };
    reader.readAsDataURL(blob);
  };

  return () => {
    processor.disconnect();
    src.disconnect();
    stream.getTracks().forEach(t => t.stop());
    audioCtx.close();
  };
}
