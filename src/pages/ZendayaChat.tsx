import React, {
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useState,
} from "react";
import { Loader2, AlertCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { User } from "@supabase/supabase-js"; // Import User type

// --- Core Hooks ---
import { useSupabaseChat } from "../hooks/useSupabaseChat";
import { useAIStream } from "../hooks/useAIStream";
import { useChatStore } from "../hooks/useChatStore";

// --- Core Libs ---
import { supabase } from "../lib/supabaseClient";
import { ZENDAYA_SYSTEM_PROMPT } from "../ai/systemPrompts/zendaya";
import { ResponseMode, Message } from "../types"; // Import Message type

// --- UI Components ---
import { ErrorBoundary } from "../components/ErrorBoundary";
import { Header } from "../components/SystemHeader";
import { Sidebar } from "../components/Sidebar";
import { ZendayaAvatar } from "../components/ZendayaAvatar";
import { QuickActions } from "../components/QuickActions";
import { ChatListSkeleton } from "../components/Skeletons";

// --- Lazy-loaded Components ---
const ChatMessageList = lazy(() =>
  import("../components/ChatMessageList").then((module) => ({
    default: module.ChatMessageList,
  }))
);
const ChatInputBar = lazy(() =>
  import("../components/ChatInputBar").then((module) => ({
    default: module.ChatInputBar,
  }))
);

// --- Main Chat Component Logic ---
const ZendayaChatContent: React.FC = () => {
  const navigate = useNavigate();

  // --- 1. Get Authentication & AI Stream Hooks ---
  const { user } = useSupabaseChat(); // Manages auth and session sync
  const { startStream } = useAIStream(); // Manages the AI text fetch

  // --- 2. Get ALL State from the Global Store (Individually) ---
  const isLoading = useChatStore((s) => s.isLoading);
  const error = useChatStore((s) => s.error);
  const sessionId = useChatStore((s) => s.sessionId);
  const responseMode = useChatStore((s) => s.responseMode);
  const isSending = useChatStore((s) => s.isSending);
  const isListening = useChatStore((s) => s.isListening);
  const isSpeaking = useChatStore((s) => s.isSpeaking);
  const messages = useChatStore((s) => s.messages); // Get messages for context

  // --- 3. Get ALL Actions from the Global Store ---
  const {
    addOptimisticMessage,
    updateMessage, // Keep this for potential future use (e.g., editing)
    addSystemMessage,
    setResponseMode,
    setError,
    // removeMessage, // ✅ FIX: No longer needed here
    startListening,
    stopListening,
    synthesizeAndPlay,
  } = useChatStore.getState();

  // --- 4. Local State for Speech Support ---
  const [speechSupported, setSpeechSupported] = useState(false);
  useEffect(() => {
    setSpeechSupported(
      !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
    );
  }, []);

  const [zenMode, setZenMode] = useState(false);

  // --- 5. Core Logic (wrapped in useCallback for stability) ---

  const getIntroduction = () => "This is Z.E.N.D.A.Y.A. How can I assist?";

  // This logic can be simplified as it's now part of the main handleSend
  // But we keep it separate for clarity
  const checkAndHandleIdentity = useCallback(
    async (text: string): Promise<boolean> => {
      const lowerText = text.toLowerCase().trim();
      const identityKeywords = [
        "who are you",
        "what are you",
        "your name",
        "about yourself",
        "about zendaya",
        "z.e.n.d.a.y.a",
      ];

      if (identityKeywords.some((keyword) => lowerText.includes(keyword))) {
        addOptimisticMessage({ role: "user", text });
        const introReply = getIntroduction();
        addOptimisticMessage({ role: "ai", text: introReply });

        if (responseMode === "dual" || responseMode === "voice") {
          synthesizeAndPlay(introReply);
        }
        return true; // Query was handled
      }
      return false; // Query not handled
    },
    [responseMode, addOptimisticMessage, synthesizeAndPlay]
  );

  const checkAndSetResponseMode = useCallback(
    (text: string): boolean => {
      const lowerText = text.toLowerCase();
      if (!lowerText.includes("zendaya")) return false;

      const RESPONSE_MODES_CONFIG: Record<
        ResponseMode,
        { label: string; keywords: string[] }
      > = {
        voice: { label: "Voice-Only", keywords: ["voice only"] },
        text: { label: "Text-Only", keywords: ["text only"] },
        dual: {
          label: "Dual",
          keywords: ["type and speak", "dual mode", "default mode"],
        },
      };

      for (const [mode, config] of Object.entries(RESPONSE_MODES_CONFIG)) {
        if (config.keywords.some((kw) => lowerText.includes(kw))) {
          setResponseMode(mode as ResponseMode);
          addSystemMessage(`Switched to ${config.label} mode.`);
          return true;
        }
      }
      return false;
    },
    [setResponseMode, addSystemMessage]
  );

  const handleSend = useCallback(
    async (textInput: string, filesInput: File[]) => {
      if (isSending || !sessionId || !user) {
        if (!sessionId || !user)
          addSystemMessage(
            "Session not initialized. Please wait.",
            true
          );
        return;
      }

      if (checkAndSetResponseMode(textInput)) return;
      if (await checkAndHandleIdentity(textInput)) return;

      if (isListening) stopListening(false); // Stop listening, don't send transcript

      // ✅ FIX: 1. Create unique optimistic IDs
      const optimisticUserId = `temp_user_${Date.now()}`;
      const optimisticAiId = `temp_ai_${Date.now() + 1}`;

      // 2. Add optimistic user message
      addOptimisticMessage({
        role: "user",
        text: textInput,
        meta: { optimisticId: optimisticUserId, userId: user.id },
      });

      // 3. Create AI placeholder
      addOptimisticMessage({
        role: "ai",
        text: "...",
        meta: { optimisticId: optimisticAiId, userId: user.id },
      });

      // 4. Build system prompt & messages context
      const conversationHistory = messages || []; // Get latest messages
      const systemPrompt = zenMode
        ? ZENDAYA_SYSTEM_PROMPT
        : "You are a helpful assistant.";
      
      const messagesForApi = [
        { role: "system", content: systemPrompt },
        ...conversationHistory
          .filter(m => m.role === 'user' || m.role === 'ai') // Only send user/ai roles
          .map((m: Message) => ({
            role: m.role,
            content: m.text,
          })),
        // Add the new user message
        { role: 'user', content: textInput }
      ];

      // 5. Prepare form data
      const formData = new FormData();
      formData.append("message", textInput); // The most recent message
      formData.append("stream", "true");
      formData.append("user_id", user.id);
      formData.append("session_id", sessionId);
      // ✅ FIX: Pass optimistic IDs to the backend
      formData.append("optimistic_user_id", optimisticUserId);
      formData.append("optimistic_ai_id", optimisticAiId);

      // Attach messages context for the streaming API
      try {
        formData.append("messages", JSON.stringify(messagesForApi));
      } catch (e) {
        console.warn("Could not serialize messages for API", e);
      }
      filesInput.forEach((f, index) => formData.append(`file_${index}`, f));

      // 6. Start stream
      const streamedText = await startStream(
        formData,
        optimisticAiId, // Send temp ID for store update
        responseMode
      );

      // 7. Play voice (if enabled)
      if (streamedText && (responseMode === "dual" || responseMode === "voice")) {
        synthesizeAndPlay(streamedText);
      }

      // 8. Persist final messages
      // This now happens on the backend, triggered by the `startStream` call.
      // The backend MUST insert the messages with the optimistic IDs in their meta.
      // ✅ FIX: We no longer remove the messages. The realtime listener
      // in useSupabaseChat will "upsert" them seamlessly.
      // removeMessage(userMessage.id); // <-- REMOVED
      // removeMessage(aiPlaceholderMessage.id); // <-- REMOVED

    },
    [
      isSending,
      sessionId,
      user,
      responseMode,
      isListening,
      zenMode,
      messages, // Added messages to dependency array
      checkAndSetResponseMode,
      checkAndHandleIdentity,
      addOptimisticMessage,
      stopListening,
      startStream,
      synthesizeAndPlay,
      addSystemMessage,
    ]
  );

  // --- 6. Effect to listen for voice transcripts ---
  useEffect(() => {
    const handleTranscript = (event: Event) => {
      const text = (event as CustomEvent).detail;
      if (text) {
        handleSend(text, []); // Send the transcribed text
      }
    };
    window.addEventListener("newTranscriptForAI", handleTranscript);
    return () =>
      window.removeEventListener("newTranscriptForAI", handleTranscript);
  }, [handleSend]); // Re-subscribe if handleSend changes

  // --- 7. Toggle Listening Function ---
  const handleToggleListening = () => {
    if (isListening) {
      stopListening(true); // Stop listening AND send transcript
    } else {
      startListening();
    }
  };

  // --- Render ---

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-zinc-900 text-slate-100 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
        <span className="ml-3 text-lg">Connecting to Zendaya AI...</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-zinc-900 text-slate-100 font-sans relative overflow-hidden flex h-screen">
      {/* Background decoration */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60vw] h-[60vw] max-w-2xl max-h-2xl rounded-full bg-cyan-500/10 blur-3xl" />
      
      {/* Error Popup */}
      {error && (
        <div className="absolute top-4 right-4 max-w-sm bg-red-800/80 backdrop-blur-md border border-red-600 text-white p-4 rounded-lg shadow-lg z-50">
          <div className="flex items-center">
            <AlertCircle className="w-6 h-6 text-red-300 mr-3" />
            <div>
              <p className="font-semibold">An Error Occurred</p>
              <p className="text-sm text-red-200">{error.message}</p>
            </div>
            <button
              onClick={() => setError("")}
              className="ml-4 p-1 text-red-200 hover:text-white"
            >
              &times;
            </button>
          </div>
        </div>
      )}

      <Sidebar />

      <div className="flex-1 h-full overflow-hidden">
        <div className="flex h-full w-full max-w-screen-2xl mx-auto p-4 md:p-8 gap-8">
          <div className="hidden md:flex flex-col w-full max-w-sm lg:max-w-md space-y-6 flex-shrink-0">
            <ZendayaAvatar isSpeaking={isSpeaking} />
            <div className="overflow-y-auto pr-2">
              <QuickActions />
            </div>
          </div>

          <div className="flex flex-col flex-1 h-full min-w-0">
            <div className="flex items-center">
              <Header
                showBackButton={true}
                onBack={() => navigate("/dashboard")}
              />
              <button
                onClick={() => setZenMode(!zenMode)}
                className={`ml-4 px-3 py-1 rounded-2xl border text-sm ${
                  zenMode
                    ? "bg-purple-600 text-white border-purple-500"
                    : "bg-neutral-800 text-gray-300 border-gray-700"
                }`}
              >
                {zenMode
                  ? "Z.E.N.D.A.Y.A Mode: ON ✨"
                  : "Enable Z.E.N.D.A.Y.A Mode"}
              </button>
            </div>

            <main className="rounded-2xl border border-slate-800 bg-black/30 backdrop-blur-sm p-0 flex flex-col flex-1 h-0 min-h-0 overflow-hidden shadow-lg mt-4">
              <Suspense fallback={<ChatListSkeleton />}>
                <ChatMessageList />
                <ChatInputBar
                  onSend={handleSend}
                  onToggleListening={handleToggleListening}
                  listening={isListening}
                  speechSupported={speechSupported}
                />
              </Suspense>
            </main>

            <div className="md:hidden mt-4 overflow-y-auto max-h-24 pr-1">
              <QuickActions />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// --- Main App Component with Error Boundary ---
export default function ZendayaChat(): JSX.Element {
  return (
    <ErrorBoundary
      fallback={
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-zinc-900 text-slate-100 flex items-center justify-center flex-col">
          <AlertCircle className="w-12 h-12 text-red-400" />
          <h2 className="mt-4 text-xl font-semibold text-red-300">
            A critical error occurred
          </h2>
          <p className="text-slate-400">Please refresh the application.</p>
        </div>
      }
    >
      <ZendayaChatContent />
    </ErrorBoundary>
  );
}