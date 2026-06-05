/**
 * voicePlayer.ts — shared VoiceQueue singleton.
 *
 * useWebSocket feeds wire frames into voicePlayer.handle(); useVoicePlayback
 * calls voicePlayer.unlock() on the first user gesture. The underlying
 * AudioContext is created lazily inside VoiceQueue, so importing this module
 * is side-effect free (safe in tests / SSR).
 */
import { VoiceQueue } from "./VoiceQueue";

export const voicePlayer = new VoiceQueue();
