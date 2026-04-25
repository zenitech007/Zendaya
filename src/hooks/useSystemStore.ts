// src/hooks/useSystemStore.ts
import { create } from "zustand";
import { supabase } from "@/lib/supabaseClient"; // For auth token
import { toast } from "@/hooks/use-toast"; // For user feedback

// --- Configuration ---
const WS_BASE_URL =
  import.meta.env.VITE_WS_BACKEND_URL || "ws://127.0.0.1:8000";
const API_BASE_URL = WS_BASE_URL.replace(/^wss?:\/\//, (m) =>
  m.startsWith("wss") ? "https://" : "http://",
).replace(/\/$/, "");

// --- Types ---
export interface HistoryPoint {
  timestamp: string;
  cpu: number;
  memory: number;
  disk: number;
}

export interface SystemStatus {
  cpu: number;
  memory: number;
  disk: number;
  network: boolean;
  services: Record<string, boolean>;
  discoveredDevices: number;
  registeredUsers?: number;
  history: HistoryPoint[];
}

type LogEntry = { ts: number; level: "info" | "warn" | "error"; text: string };

// --- Module-level singletons ---
// We manage these outside the store's state to prevent re-renders
// and to persist the connection across the app's lifetime.
let socket: WebSocket | null = null;
let reconnectTimer: NodeJS.Timeout | null = null;
let heartbeatTimer: NodeJS.Timeout | null = null;
let reconnectAttempts = 0;

interface SystemStore {
  // State
  status: SystemStatus | null;
  isConnected: boolean;
  isInitialized: boolean;
  isUiActive: boolean;
  lastHeartbeat: number | null;
  logs: LogEntry[];

  // Actions
  setStatus: (s: Partial<SystemStatus>) => void;
  pushHistory: (pt: HistoryPoint) => void;
  pushLog: (entry: Omit<LogEntry, "ts">) => void;
  clearLogs: () => void;

  // Connection Lifecycle (called by useSystemMonitor)
  initSocket: () => Promise<void>;
  stopSocket: () => void; // This will just pause the heavy stream
  setUIActive: (isActive: boolean) => void;

  // API Actions (HTTP)
  performAction: (action: string, body?: any) => Promise<any>;
  restartService: (serviceName: string) => Promise<any>;
}

export const useSystemStore = create<SystemStore>((set, get) => {
  // --- Internal Connection Logic ---
  const internalConnect = (token: string) => {
    // Prevent duplicate connections
    if (socket && socket.readyState === WebSocket.OPEN) {
      get().pushLog({
        level: "warn",
        text: "internalConnect called but socket already open.",
      });
      return;
    }

    // Clean up any existing socket
    if (socket) {
      socket.onclose = null;
      socket.onerror = null;
      socket.close();
    }

    const WS_URL = `${WS_BASE_URL}/ws?token=${token}`;
    socket = new WebSocket(WS_URL);

    socket.onopen = () => {
      set({ isConnected: true, lastHeartbeat: Date.now() });
      reconnectAttempts = 0;
      if (reconnectTimer) clearInterval(reconnectTimer);
      get().pushLog({ level: "info", text: "System socket connected." });

      // If UI became active while we were disconnected, request heavy stream now
      if (get().isUiActive) {
        get().setUIActive(true);
      }
    };

    socket.onmessage = (event) => {
      // Any message counts as a heartbeat
      set({ lastHeartbeat: Date.now() });

      try {
        const msg = JSON.parse(event.data);
        const { setStatus, pushHistory, pushLog } = get();

        switch (msg.type) {
          // "system_status" is the heavy, UI-driven stream
          case "system_status":
            setStatus(msg.data);
            pushHistory({
              timestamp: msg.data.timestamp,
              cpu: msg.data.cpu,
              memory: msg.data.memory,
              disk: msg.data.disk,
            });
            break;

          // "system_heartbeat" is the light, daemon stream
          case "system_heartbeat":
            setStatus(msg.data); // Update services, users, etc.
            break;

          // "action_result" is feedback from a backend action
          case "action_result":
            toast({
              title: msg.data.success ? "Action Completed" : "Action Failed",
              description: msg.data.message || "",
              variant: msg.data.success ? "default" : "destructive",
            });
            pushLog({
              level: msg.data.success ? "info" : "error",
              text: `[Action] ${msg.data.message}`,
            });
            break;

          // "log_entry" allows backend to send logs directly to UI
          case "log_entry":
            pushLog({
              level: msg.data.level || "info",
              text: `[Server] ${msg.data.text}`,
            });
            break;
        }
      } catch (err) {
        get().pushLog({
          level: "error",
          text: `Failed to parse WebSocket message: ${String(err)}`,
        });
      }
    };

    socket.onclose = () => {
      set({ isConnected: false });
      socket = null; // Important: clear the singleton ref
      const { pushLog, initSocket } = get();

      const timeout = Math.min(5000 * 2 ** reconnectAttempts, 30000);
      reconnectAttempts++;

      pushLog({
        level: "warn",
        text: `Socket closed. Reconnecting in ${timeout / 1000}s...`,
      });
      reconnectTimer = setTimeout(() => {
        initSocket(); // This will re-run the full auth + connect flow
      }, timeout);
    };

    socket.onerror = (err) => {
      get().pushLog({
        level: "error",
        text: `Socket error: ${String(err)}. Closing socket.`,
      });
      // A- failed socket will trigger onclose, which handles reconnect
      socket?.close();
    };
  };

  return {
    // --- Initial State ---
    status: null,
    isConnected: false,
    isInitialized: false,
    isUiActive: false,
    lastHeartbeat: null,
    logs: [],

    // --- State Setters ---
    setStatus: (s) =>
      set((st) => ({
        status: {
          ...(st.status ?? {
            cpu: 0,
            memory: 0,
            disk: 0,
            network: true,
            services: {},
            discoveredDevices: 0,
            history: [],
          }),
          ...s,
        },
      })),

    pushHistory: (pt) =>
      set((st) => {
        if (!st.status) return {}; // Guard against no status
        const history = [...st.status.history, pt].slice(-120); // Keep 120 points
        return { status: { ...st.status, history } };
      }),

    pushLog: (entry) =>
      set((st) => ({
        logs: [...st.logs, { ts: Date.now(), ...entry }].slice(-500),
      })),
    clearLogs: () => set({ logs: [] }),

    // --- Connection Lifecycle ---
    setUIActive: (isActive) => {
      set({ isUiActive: isActive });
      const { pushLog } = get();

      if (!socket || socket.readyState !== WebSocket.OPEN) {
        pushLog({
          level: "info",
          text: `UI active set to ${isActive}, but socket not ready.`,
        });
        return;
      }
      try {
        if (isActive) {
          pushLog({ level: "info", text: "Requesting heavy stream..." });
          socket.send(JSON.stringify({ type: "stream_resume" }));
        } else {
          pushLog({ level: "info", text: "Pausing heavy stream..." });
          socket.send(JSON.stringify({ type: "stream_pause" }));
        }
      } catch (err) {
        pushLog({ level: "error", text: `Failed to send stream command: ${err}` });
      }
    },

    initSocket: async () => {
      const { isInitialized, pushLog } = get();
      // The `socket` check prevents re-init if connection is already live
      if (isInitialized || socket) {
        return;
      }
      set({ isInitialized: true });
      pushLog({ level: "info", text: "System socket initializing..." });

      // Start heartbeat check
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      heartbeatTimer = setInterval(() => {
        const { lastHeartbeat, isConnected, initSocket: reInit } = get();
        if (isConnected && Date.now() - (lastHeartbeat || 0) > 15000) {
          pushLog({
            level: "warn",
            text: "Lost server heartbeat. Forcing reconnect.",
          });
          socket?.close(); // This triggers onclose and reconnect logic
        }
      }, 5000);

      // --- Auth ---
      try {
        const { data } = await supabase.auth.getSession();
        const token = data.session?.access_token;
        if (!token) {
          pushLog({
            level: "warn",
            text: "No auth token. System socket not opened.",
          });
          set({ isInitialized: false }); // Allow retry
          return;
        }
        // --- Connect ---
        internalConnect(token);
      } catch (err) {
        pushLog({
          level: "error",
          text: `Failed to get auth token for socket: ${String(err)}`,
        });
        set({ isInitialized: false }); // Allow retry
      }
    },

    stopSocket: () => {
      // This is called by useSystemMonitor on unmount.
      // We interpret it as "UI is no longer active."
      get().setUIActive(false);
    },

    // --- API Actions (HTTP POST) ---
    performAction: async (action: string, body?: any) => {
      const { pushLog } = get();
      try {
        const url = `${API_BASE_URL}/system/${encodeURIComponent(action)}`;
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: body ? JSON.stringify(body) : undefined,
        });
        if (!res.ok)
          throw new Error(`Action ${action} failed (${res.status})`);
        // Try to parse json, fallback to text
        const text = await res.text();
        try {
          return JSON.parse(text);
        } catch {
          return text;
        }
      } catch (err) {
        pushLog({ level: "error", text: String(err) });
        throw err;
      }
    },

    restartService: async (serviceName: string) => {
      const { pushLog, performAction } = get();
      try {
        const data = await performAction("restart", { service: serviceName });
        pushLog({ level: "info", text: `Restarted ${serviceName}` });
        return data;
      } catch (err) {
        pushLog({
          level: "error",
          text: `Restart ${serviceName} failed: ${String(err)}`,
        });
        throw err;
      }
    },
  };
});

// --- Supabase Broadcast Listener ---
// This listens for cross-client events
export const initSystemEvents = () => {
  supabase
    .channel("system_events")
    .on("broadcast", { event: "admin_action" }, (payload) => {
      console.log("⚙️ Admin System Event:", payload);
      // Use the store to log the event
      useSystemStore.getState().pushLog({
        level: "info",
        text: `[Admin Event] ${
          payload.payload?.message || "Received admin_action"
        }`,
      });
      // Optionally, trigger a toast
      toast({
        title: "Admin Event Received",
        description: payload.payload?.message,
      });
    })
    .subscribe();
};

