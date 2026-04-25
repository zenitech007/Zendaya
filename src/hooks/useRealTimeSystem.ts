// useRealTimeSystem.ts
import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "@/hooks/use-toast";
// Get Supabase session token
// (adjust import if needed)
import { supabase } from "@/lib/supabaseClient";

export interface SystemStatus {
  cpu: number;
  memory: number;
  disk: number;
  network: boolean;
  services: Record<string, boolean>;
  discoveredDevices: number;
  registeredUsers: number;
  history: { timestamp: string; cpu: number; memory: number; disk: number }[];
}

// ✅ FIX: Use the .env variable to get the correct backend URL
const WS_BASE_URL =
  import.meta.env.VITE_WS_BACKEND_URL || "ws://127.0.0.1:8000";
const API_BASE_URL = WS_BASE_URL.replace(/^wss?:\/\//, (m) => m.startsWith("wss") ? "https://" : "http://").replace(/\/$/, "");

export const useRealTimeSystem = () => {
  const [status, setStatus] = useState<SystemStatus>({
    cpu: 0,
    memory: 0,
    disk: 0,
    network: true,
    services: {},
    discoveredDevices: 0,
    registeredUsers: 0,
    history: [],
  });

  const [connected, setConnected] = useState(false);
  const [lastPing, setLastPing] = useState<number>(Date.now());
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number>(0);
  const pingTimer = useRef<NodeJS.Timeout | null>(null);

  // ✅ Corrected Line
  const WS_URL = `${WS_BASE_URL}/ws`;

  const connectWebSocket = useCallback(async () => {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;

    if (!token) {
      console.warn("⚠️ No auth token. System Monitor socket not opened.");
      return;
    }

    const socket = new WebSocket(`${WS_URL}?token=${token}`);
    socketRef.current = socket;

    socket.onopen = () => {
      setConnected(true);
      reconnectRef.current = 0;
      toast({
        title: "Connected to System Monitor",
        description: "Real-time system metrics are live.",
      });
    };

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "system_status") {
          setStatus((prev) => {
            const history = [
              ...prev.history,
              {
                timestamp: msg.data.timestamp,
                cpu: msg.data.cpu ?? prev.cpu,
                memory: msg.data.memory ?? prev.memory,
                disk: msg.data.disk ?? prev.disk,
              },
            ].slice(-30);
            return { ...prev, ...msg.data, history };
          });
          setLastPing(Date.now());
        } else if (msg.type === "action_result") {
          toast({
            title: msg.data.success ? "Action Completed" : "Action Failed",
            description: msg.data.message || "",
            variant: msg.data.success ? "default" : "destructive",
          });
        }
      } catch (err) {
        console.error("Failed to parse WebSocket message:", err);
      }
    };

    socket.onclose = () => {
      setConnected(false);
      const attempt = reconnectRef.current++;
      const timeout = Math.min(5000 * 2 ** attempt, 60000);
      console.warn(`[System WS] Closed. Reconnecting in ${timeout / 1000}s...`);
      setTimeout(connectWebSocket, timeout);
    };

    socket.onerror = (err) => {
      console.error("System WebSocket error:", err);
      socket.close();
    };
  }, [WS_URL]);

  // Connection lifecycle
  useEffect(() => {
    connectWebSocket();
    return () => {
      socketRef.current?.close();
      pingTimer.current && clearInterval(pingTimer.current);
    };
  }, [connectWebSocket]);

  // Connection health check (if no ping for >10s, reconnect)
  useEffect(() => {
    pingTimer.current = setInterval(() => {
      // Check if we've lost server ping
      if (Date.now() - lastPing > 15000 && connected) {
        console.warn("⚠️ Lost ping — reconnecting system socket");
        socketRef.current?.close();
        return; // Don't try to send a ping if we're reconnecting
      }

      // Send a client-side ping to keep connection alive
      if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
        try {
          // Server should be configured to ignore this if not needed
          socketRef.current.send(JSON.stringify({ type: "ping" }));
        } catch (err) {
          console.error("Failed to send client ping:", err);
        }
      }
    }, 5000); // Run this check every 5 seconds
    return () => pingTimer.current && clearInterval(pingTimer.current);
  }, [connected, lastPing]);

  const performAction = useCallback(async (action: string) => {
    // ✅ FIX: Point to the correct backend API URL
    const url = `${API_BASE_URL}/system/${action}`;

    if (action === "test-voice") {
    // ... existing code ...
      try {
        const res = await fetch(url, { method: "POST" });
    // ... existing code ...
        if (!res.ok) throw new Error("Voice test failed");
        const blob = await res.blob();
        const audio = new Audio(URL.createObjectURL(blob));
        audio.play().catch((err) => console.error("Audio playback error:", err));
        toast({ title: "Voice Test", description: "Zendaya’s voice test is playing." });
    // ... existing code ...
      } catch (err) {
        toast({ title: "Voice Test Failed", description: String(err), variant: "destructive" });
    // ... existing code ...
      }
    } else {
      const res = await fetch(url, { method: "POST" });
    // ... existing code ...
      if (!res.ok) throw new Error(`Action ${action} failed with status ${res.status}`);
      return res.json();
    }
  }, []);

  return { status, connected, performAction };
};





