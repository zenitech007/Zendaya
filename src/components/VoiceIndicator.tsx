// components/VoiceIndicator.tsx
import React from "react";
import { useChatStore } from "../hooks/useChatStore";

export const VoiceIndicator: React.FC = () => {
  const isListening = useChatStore((s) => s.isListening);
  const ws = useChatStore((s) => s.ws);

  return (
    <div className="flex items-center space-x-2">
      <div
        className={`w-4 h-4 rounded-full transition-transform ${
          isListening ? "scale-110 animate-pulse" : "scale-90 opacity-60"
        } ${ws ? "bg-emerald-400" : "bg-gray-400"}`}
        title={isListening ? "Listening" : ws ? "Connected" : "Disconnected"}
      />
      <span className="text-xs text-slate-300">
        {isListening ? "Listening" : ws ? "Ready" : "Offline"}
      </span>
    </div>
  );
};
