import { useRef } from "react";
import { useChatStore } from "./useChatStore";
import { ResponseMode } from "../types";

/**
 * Hook to manage the AI response stream.
 * Encapsulates fetch, streaming, and abort logic.
 */
export const useAIStream = () => {
  // Get session ID from the store
  const sessionId = useChatStore((s) => s.sessionId);
  
  // Get actions from the store (not reactive)
  const { addSystemMessage, updateMessage, setIsStreaming, setIsSending } =
    useChatStore.getState();
    
  const abortControllerRef = useRef<AbortController | null>(null);

  /**
   * Starts the AI chat stream.
   * @param {FormData} formData The form data containing the prompt and files.
   * @param {string} aiPlaceholderMessageId The temporary ID of the AI message.
   * @param {ResponseMode} responseMode The current response mode (dual, text, voice).
   * @returns {Promise<string | null>} The final streamed text, or null on error.
   */
  const startStream = async (
    formData: FormData,
    aiPlaceholderMessageId: string,
    responseMode: ResponseMode
  ): Promise<string | null> => {
    if (!sessionId) {
      addSystemMessage("Session not initialized. Cannot stream.", true);
      return null;
    }

    // Prevent multiple streams
    if (abortControllerRef.current) {
      console.warn("Stream already in progress. Aborting new request.");
      return null;
    }

    setIsStreaming(true);
    setIsSending(true); // isSending is true for the duration
    abortControllerRef.current = new AbortController();

    let streamedText = "";
    try {
      const res = await fetch(`/api/chat`, {
        method: "POST",
        body: formData,
        signal: abortControllerRef.current.signal,
      });

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Backend error (${res.status}): ${errorText || res.statusText}`);
      }
      if (!res.body) throw new Error("Response has no body for streaming.");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        streamedText += chunk;
        
        // Update UI only if not in voice-only mode
        if (responseMode !== "voice") {
          // TODO: Batch updates for performance
          updateMessage(aiPlaceholderMessageId, streamedText);
        }
      }
      
      const finalChunk = decoder.decode();
      streamedText += finalChunk;

      // Final update with complete text
      updateMessage(aiPlaceholderMessageId, streamedText || "...");

      return streamedText; // Return final text for voice playback
    } catch (err: any) {
      if (err.name === "AbortError") {
        console.log("Stream aborted by user.");
        const errorMessage = `${streamedText || "..."} [Response stopped]`;
        updateMessage(aiPlaceholderMessageId, errorMessage);
        addSystemMessage("Response generation stopped.");
      } else {
        console.error("Chat stream error:", err);
        const errorMessage = `Error: ${err.message}`;
        updateMessage(aiPlaceholderMessageId, errorMessage);
        addSystemMessage(`Chat error: ${err.message}`, true);
      }
      return null; // Indicate error
    } finally {
      setIsStreaming(false);
      setIsSending(false); // No longer sending/streaming
      abortControllerRef.current = null;
    }
  };

  /**
   * Aborts the currently active stream, if one exists.
   */
  const abortStream = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      console.log("Stream abort requested.");
    }
  };

  return { startStream, abortStream };
};
