import React, { useState, useRef, useEffect } from "react";
import { ArrowUp, Mic, MicOff, Paperclip } from "lucide-react";
import { useChatStore } from "../hooks/useChatStore";

interface ChatInputBarProps {
  onSend: (text: string, files: File[]) => void;
  onToggleListening: () => void;
  listening: boolean;
  speechSupported: boolean;
}

export const ChatInputBar: React.FC<ChatInputBarProps> = ({
  onSend,
  onToggleListening,
  listening,
  speechSupported,
}) => {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // ✅ FIX: Atomically select only the state you need.
  // This fixes the "getSnapshot" warning.
  const isSending = useChatStore((s) => s.isSending);

  const handleSendClick = () => {
    if ((text.trim() || files.length > 0) && !isSending) {
      onSend(text, files);
      setText("");
      setFiles([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendClick();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${scrollHeight}px`;
    }
  }, [text]);

  const isDisabled = isSending || listening;

  return (
    <div className="border-t border-slate-800 p-4 bg-black/20 backdrop-blur-sm sticky bottom-0">
      <div className="flex items-end gap-2">
        {speechSupported && (
          <button
            onClick={onToggleListening}
            disabled={isSending}
            className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-colors ${
              listening
                ? "bg-red-500 text-white"
                : "bg-slate-700 text-slate-200 hover:bg-slate-600"
            }`}
            aria-label={listening ? "Stop listening" : "Start listening"}
          >
            {listening ? <MicOff size={20} /> : <Mic size={20} />}
          </button>
        )}

        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              listening
                ? "Listening..."
                : isSending
                ? "Zendaya is thinking..."
                : "Type or speak..."
            }
            className="w-full bg-slate-800 border border-slate-700 rounded-lg text-slate-100 p-3 pr-20 resize-none overflow-y-auto max-h-40"
            disabled={isDisabled}
          />
          <label
            className={`absolute right-12 top-1/2 -translate-y-1/2 p-2 rounded-full cursor-pointer ${
              isDisabled
                ? "text-slate-600"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-700"
            }`}
          >
            <Paperclip size={18} />
            <input
              type="file"
              multiple
              onChange={handleFileChange}
              className="hidden"
              disabled={isDisabled}
            />
          </label>
        </div>

        <button
          onClick={handleSendClick}
          disabled={(!text.trim() && files.length === 0) || isDisabled}
          className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-colors bg-cyan-600 text-white disabled:bg-slate-700 disabled:text-slate-500 hover:bg-cyan-500"
          aria-label="Send message"
        >
          <ArrowUp size={20} />
        </button>
      </div>
      {files.length > 0 && (
        <div className="text-xs text-slate-400 mt-2">
          Attached: {files.map((f) => f.name).join(", ")}
          <button
            onClick={() => setFiles([])}
            className="ml-2 text-red-400 hover:text-red-300"
          >
            [Clear]
          </button>
        </div>
      )}
    </div>
  );
};

export default ChatInputBar;