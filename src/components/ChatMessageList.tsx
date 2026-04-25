import React, { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { useChatStore } from "../hooks/useChatStore";
import { Message } from "../types";

/**
 * Renders a single chat message.
 */
const ChatMessage: React.FC<{ message: Message }> = React.memo(({ message }) => {
  const m = message; // shorter alias
  const isUser = m.role === "user";
  const isSystem = m.role === "system";
  const hasError = m.meta?.error;

  const getInitials = (name = "User") => name.charAt(0).toUpperCase();

  if (isSystem) {
    return (
      <div key={m.id} className="px-3 py-2">
        <div
          className={`text-center text-xs italic rounded-lg py-1 px-3 mx-auto max-w-md ${
            hasError
              ? "bg-red-900/50 text-red-300"
              : "bg-black/30 text-slate-400"
          }`}
        >
          {hasError ? `System Error: ${m.meta.error}` : m.text}
        </div>
      </div>
    );
  }

  return (
    <motion.div
      key={m.id}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex ${
        isUser ? "justify-end" : "justify-start"
      } items-end gap-2 p-3`}
    >
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center flex-shrink-0 shadow-lg self-end mb-1">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
      )}
      <div
        className={`relative group max-w-[85%] inline-block p-3 px-4 rounded-xl text-sm leading-relaxed shadow-md ${
          isUser
            ? "bg-gradient-to-r from-cyan-600/60 to-blue-600/60 text-white rounded-br-lg"
            : "bg-slate-800/70 text-slate-200 whitespace-pre-wrap rounded-bl-lg"
        }`}
      >
        {m.text}
        {/* Timestamp on hover */}
        <div className="absolute bottom-full mb-1 right-0 hidden group-hover:block px-2 py-1 bg-black/60 text-white text-xs rounded shadow-lg whitespace-nowrap">
          {new Date(m.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center flex-shrink-0 self-end mb-1">
          {getInitials()}
        </div>
      )}
    </motion.div>
  );
});

/**
 * Renders the "Thinking..." indicator.
 */
const ThinkingIndicator: React.FC = () => (
  <div className="p-3 flex justify-start items-end gap-2">
    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center flex-shrink-0 shadow-lg">
      <Sparkles className="w-4 h-4 text-white" />
    </div>
    <div className="bg-slate-800/70 text-slate-200 rounded-xl p-3 px-4">
      <div className="flex gap-1.5 items-center">
        <span
          className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
          style={{ animationDelay: "0ms" }}
        />
        <span
          className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
          style={{ animationDelay: "150ms" }}
        />
        <span
          className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
          style={{ animationDelay: "300ms" }}
        />
      </div>
    </div>
  </div>
);

/**
 * Renders the list of chat messages and handles auto-scrolling.
 */
export const ChatMessageList: React.FC = () => {
  // Select state from the store
  const messages = useChatStore((s) => s.messages);
  const isThinking = useChatStore((s) => s.isStreaming || s.isSending);
  
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Scroll to bottom when messages change or thinking status changes
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, isThinking]);

  return (
    <div ref={listRef} className="flex-1 h-0 overflow-y-auto">
      {messages.map((message) => (
        <ChatMessage key={message.id} message={message} />
      ))}
      {isThinking && <ThinkingIndicator />}
    </div>
  );
};
