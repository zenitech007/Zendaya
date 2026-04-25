// src/utils/localWakeModel.ts
import * as tf from "@tensorflow/tfjs";

let model: tf.LayersModel | null = null;
let tokenizer: { [k: string]: number } | null = null;

// Load model + tokenizer (assume you host under /models/wake_model)
export async function loadLocalWakeModel() {
  if (model) return model;
  try {
    model = await tf.loadLayersModel("/models/wake_model/model.json");
    // load tokenizer mapping JSON from /models/wake_model/tokenizer.json
    const resp = await fetch("/models/wake_model/tokenizer.json");
    tokenizer = await resp.json();
    return model;
  } catch (err) {
    console.warn("[localWakeModel] load failed", err);
    return null;
  }
}

// Simple tokenizer -> pad/truncate to length
function encode(text: string, maxLen = 32) {
  if (!tokenizer) return new Array(maxLen).fill(0);
  const t = text.toLowerCase().replace(/[^\w\s]/g, "");
  const words = t.split(/\s+/);
  const ids = words.map((w) => tokenizer![w] || 1).slice(0, maxLen);
  while (ids.length < maxLen) ids.push(0);
  return ids;
}

// returns {score: 0..1}
export async function inferLocalWake(text: string) {
  const m = await loadLocalWakeModel();
  if (!m) return null;
  const ids = encode(text);
  const input = tf.tensor2d([ids], [1, ids.length], "int32");
  // model expects int32 or float; cast if needed
  const out = m.predict(input) as tf.Tensor;
  const data = await out.data();
  const score = data[0]; // assume sigmoid output
  tf.dispose([input, out]);
  return { score };
}
