import React, { useCallback } from "react";
import {
  Download,
  Sparkles,
  Speaker,
  File as FileIcon,
  Mic,
  Sun,
  Moon,
} from "lucide-react";
import { useChatStore } from "../hooks/useChatStore";
import { ResponseMode } from "../types";
import { useTheme } from "@/hooks/useTheme";

// --- Configuration for response mode toggle
const RESPONSE_MODES: Record<
  ResponseMode,
  { next: ResponseMode; icon: React.ElementType; label: string; title: string }
> = {
  dual: {
    next: "text",
    icon: Speaker,
    label: "Dual",
    title: "Mode: Text & Voice. Click to switch to Text-Only.",
  },
  text: {
    next: "voice",
    icon: FileIcon,
    label: "Text",
    title: "Mode: Text-Only. Click to switch to Voice-Only.",
  },
  voice: {
    next: "dual",
    icon: Mic,
    label: "Voice",
    title: "Mode: Voice-Only. Click to switch to Dual.",
  },
};

// --- Fallback safe store values (prevents null store crash)
const fallbackChatStore = {
  responseMode: "dual" as ResponseMode,
  setResponseMode: () => {},
  addSystemMessage: () => {},
  messages: [],
};

/**
 * Main header for the dashboard/chat system.
 * Now theme-aware and store-safe.
 */
export const Header: React.FC = () => {
  // 🧠 Prevent crash if store isn't ready
  let store;
  try {
    // ✅ BULLETPROOF FIX: Select each value individually
    // This prevents the infinite "Maximum update depth" loop.
    const responseMode = useChatStore((s) => s.responseMode);
    const setResponseMode = useChatStore((s) => s.setResponseMode);
    const addSystemMessage = useChatStore((s) => s.addSystemMessage);
    const messages = useChatStore((s) => s.messages);

    store = { responseMode, setResponseMode, addSystemMessage, messages };
  } catch (err) {
    console.warn("⚠️ useChatStore unavailable – using fallback store.");
    store = fallbackChatStore;
  }

  const { responseMode, setResponseMode, addSystemMessage, messages } = store;

  // This check is needed in case the store isn't fully initialized
  const currentMode = RESPONSE_MODES[responseMode] || RESPONSE_MODES.dual;
  const { theme, toggleTheme } = useTheme();

  /**
   * Toggles to the next response mode.
   */
  const toggleResponseMode = useCallback(() => {
    const nextMode = currentMode.next;
    setResponseMode(nextMode);
    addSystemMessage(`Switched to ${RESPONSE_MODES[nextMode].label} mode.`);
  }, [currentMode, setResponseMode, addSystemMessage]);

  /**
   * Exports the current chat history as a .txt file.
   */
  const exportChat = useCallback(() => {
    if (!messages?.length) {
      addSystemMessage("Nothing to export.");
      return;
    }

    try {
      const chatText = messages
        .filter((m) => m.role !== "system" || !m.id?.startsWith("temp_"))
        .map(
          (m) =>
            `[${new Date(m.created_at).toLocaleString()}] ${m.role.toUpperCase()}:\n${
              m.text
            }`
        )
        .join("\n\n");

      const blob = new Blob([chatText], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ZendayaChat_${new Date().toISOString().split("T")[0]}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      addSystemMessage("Chat history exported.");
    } catch (err: any) {
      console.error("Export chat error:", err);
      addSystemMessage(`Failed to export chat: ${err.message}`, true);
    }
  }, [messages, addSystemMessage]);

  return (
    <header className="flex items-center justify-between mb-4 flex-shrink-0">
      {/* Title */}
      <div className="flex items-center gap-4 min-w-0">
        <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br from-cyan-500/30 to-blue-700/30 border border-cyan-500/20 flex items-center justify-center shadow-lg flex-shrink-0">
          <Sparkles className="w-5 h-5 md:w-6 md:h-6 text-cyan-200 animate-pulse" />
        </div>
        <div className="min-w-0">
          <h1 className="text-xl md:text-2xl font-semibold bg-gradient-to-r from-cyan-400 to-blue-300 bg-clip-text text-transparent truncate">
            Zendaya AI Terminal
          </h1>
          <p className="text-xs md:text-sm text-slate-400 truncate">
            Professional Multimodal Intelligence Interface
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2 md:gap-3 flex-shrink-0">
        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-md border border-slate-700 text-slate-300 hover:bg-slate-800/30 transition"
          title={`Switch to ${theme === "dark" ? "Light" : "Dark"} Mode`}
        >
          {theme === "dark" ? (
            <Sun className="w-4 h-4 text-amber-300" />
          ) : (
            <Moon className="w-4 h-4 text-blue-400" />
          )}
        </button>

        {/* Export Chat */}
        <button
          onClick={exportChat}
          className="flex items-center gap-1 md:gap-2 px-2 py-1 md:px-3 md:py-2 border border-slate-700 rounded-md text-xs md:text-sm hover:bg-slate-800/30 transition text-slate-300"
          title="Export chat history"
        >
          <Download className="w-3 h-3 md:w-4 md:h-4 text-slate-400" />
          <span className="hidden sm:inline">Export</span>
        </button>

        {/* Response Mode */}
        <button
          onClick={toggleResponseMode}
          className={`px-2 py-1 md:px-3 md:py-2 rounded-md flex items-center gap-1 md:gap-2 text-xs md:text-sm border transition-colors border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10`}
          title={currentMode.title}
        >
          <currentMode.icon className="w-3 h-3 md:w-4 md:h-4" />
          <span className="hidden sm:inline">{currentMode.label}</span>
        </button>
      </div>
    </header>
  );
};
