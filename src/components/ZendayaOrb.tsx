// components/ZendayaOrb.tsx
import React, { useState } from "react";
import { useChatStore } from "@/hooks/useChatStore";
import { useAIStream } from "@/hooks/useAIStream";
import { shallow } from "zustand/shallow";
import { useWakeWord } from "@/hooks/useWakeWord";
import { useLocation, Link } from "react-router-dom";
import {
  Maximize2,
  Minimize2,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Send,
  X,
} from "lucide-react";

// 🎭 Z.E.N.D.A.Y.A persona identity
const personaIdentity = `Z.E.N.D.A.Y.A — Zettascale Engine for Neural Decision-making and Autonomous Yield Augmentation`;

const OrbVisual = ({
  state,
  amplitude,
}: {
  state: string;
  amplitude: number;
}) => {
  const scale = 1 + amplitude * 0.4;
  const color =
    state === "listening"
      ? "#ec4899"
      : state === "speaking"
      ? "#7c3aed"
      : "#06b6d4";

  return (
    <div
      className="w-full h-full rounded-full transition-all duration-150"
      style={{
        background: `radial-gradient(circle, ${color} 0%, rgba(0,0,0,0.4) 70%)`,
        transform: `scale(${scale})`,
        boxShadow: `0 0 22px ${color}55`,
        border: "2px solid rgba(255,255,255,0.25)",
      }}
    />
  );
};

export const ZendayaOrb: React.FC = () => {
  const location = useLocation();
  const { startStream } = useAIStream();
  const [showControls, setShowControls] = useState(false);
  const [showChatInput, setShowChatInput] = useState(false);
  const [chatInputValue, setChatInputValue] = useState("");

  // ✅ Single Zustand selector + shallow for performance
  // This useCallback + shallow pattern fixes the infinite loop
  // ✅ subscribe only to primitives
const {
  isListening,
  isSpeaking,
  isMuted,
  isSpeakerMuted,
  currentAmplitude,
  sessionId,
} = useChatStore(
  (s) => ({
    isListening: s.isListening,
    isSpeaking: s.isSpeaking,
    isMuted: s.isMicMuted,
    isSpeakerMuted: s.isSpeakerMuted,
    currentAmplitude: s.currentAmplitude,
    sessionId: s.sessionId,
  }),
  shallow
);

// ✅ actions must be extracted *outside* the selector
const startListening = useChatStore((s) => s.startListening);
const stopListening = useChatStore((s) => s.stopListening);
const toggleMute = useChatStore((s) => s.toggleMicMute);
const toggleSpeakerMute = useChatStore((s) => s.toggleSpeakerMute);
const synthesizeAndPlay = useChatStore((s) => s.synthesizeAndPlay);
const addOptimisticMessage = useChatStore((s) => s.addOptimisticMessage);

  // 🎧 Wake-word runs only when idle
  useWakeWord(!isListening && !isSpeaking);

  // Hide orb on full chat
  if (location.pathname.startsWith("/chat")) return null;

  const handleOrbClick = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const sendMiniMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = chatInputValue.trim();
    if (!text) return;
    setChatInputValue("");
    setShowChatInput(false);

    const userMsg = addOptimisticMessage({ role: "user", text });
    const formData = new FormData();

    formData.append("persona", personaIdentity);
    formData.append("message", text);
    formData.append("stream", "true");
    formData.append("session_id", sessionId || "");

    const reply = await startStream(formData, userMsg.id + "_ai", "text");
    if (reply) synthesizeAndPlay(reply);
  };

  const orbState = isListening ? "listening" : isSpeaking ? "speaking" : "idle";

  return (
    <div
      className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2"
      onMouseEnter={() => setShowControls(true)}
      onMouseLeave={() => !showChatInput && setShowControls(false)}
    >
      {showChatInput && (
        <form
          onSubmit={sendMiniMessage}
          className="flex items-center gap-2 bg-black/70 p-2 border border-gray-700 rounded-lg backdrop-blur-md w-64"
        >
          <input
            className="flex-1 bg-transparent text-white text-sm placeholder-gray-400 outline-none"
            placeholder="Speak to Zendaya's core..."
            value={chatInputValue}
            onChange={(e) => setChatInputValue(e.target.value)}
            autoFocus
          />
          <button type="submit" className="text-cyan-400">
            <Send size={17} />
          </button>
          <X
            size={17}
            className="text-gray-300 cursor-pointer"
            onClick={() => setShowChatInput(false)}
          />
        </form>
      )}

      {showControls && (
        <div className="flex bg-black/70 p-2 border border-gray-700 rounded-full backdrop-blur-md gap-2">
          {/* ✅ Correctly uses <Link to="..."> */}
          <Link to="/chat">
            <button className="p-2 text-gray-300 hover:text-white">
              <Maximize2 size={16} />
            </button>
          </Link>
          <button
            onClick={() => setShowChatInput((s) => !s)}
            className="p-2 text-gray-300 hover:text-white"
          >
            <Minimize2 size={16} />
          </button>
          <button onClick={toggleMute} className="p-2">
            {isMuted ? <MicOff size={16} /> : <Mic size={16} />}
          </button>
          <button onClick={toggleSpeakerMute} className="p-2">
            {isSpeakerMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
          </button>
        </div>
      )}

      <button
        onClick={handleOrbClick}
        className="w-20 h-20 rounded-full border transition-all"
        style={{
          borderColor:
            orbState === "listening"
              ? "#ec4899"
              : orbState === "speaking"
              ? "#7c3aed"
              : "#06b6d4",
        }}
      >
        <OrbVisual state={orbState} amplitude={currentAmplitude} />
      </button>
    </div>
  );
};