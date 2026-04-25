/**
 * Centralized type definitions for the Zendaya AI application.
 */

export type Message = {
  id: string;
  user_id?: string;
  session_id: string;
  role: "user" | "ai" | "system";
  text: string;
  created_at: string;
  meta?: any;
};

export type ResponseMode = "dual" | "text" | "voice";

export type ChatState = {
  messages: Message[];
  sessionId: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;
  isSending: boolean; // Tracks sending user message + waiting for stream
  isSidebarOpen: boolean;
  responseMode: ResponseMode;
};
