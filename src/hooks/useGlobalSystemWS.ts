// src/hooks/useGlobalSystemWS.tsx
import { useEffect, useRef, useCallback } from "react";
import { useSystemStore } from "@/hooks/useSystemStore";
import { supabase } from "@/lib/supabaseClient";
import { v4 as uuidv4 } from "uuid";

const WS_BASE = (import.meta.env.VITE_WS_BACKEND_URL || "ws://localhost:8000").replace(/\/$/, "");
const WS_PATH = `${WS_BASE}/ws/system`;

// exponential backoff w/ jitter
function backoffMs(attempt: number, base = 1000, max = 60000) {
  const expo = Math.min(max, base * 2 ** attempt);
  // jitter between 0.5-1x
  return Math.floor(expo * (0.5 + Math.random() * 0.5));
}

export function useGlobalSystemWS() {
  const setStatus = useSystemStore((s) => s.setStatus);
  const pushHistory = useSystemStore((s) => s.pushHistory);
  const setConnected = useSystemStore((s) => s.setConnected);
  const setHeartbeat = useSystemStore((s) => s.setHeartbeat);
  const pushLog = useSystemStore((s) => s.pushLog);
  const enqueueCommand = useSystemStore((s) => s.enqueueCommand);
  const dequeueCommand = useSystemStore((s) => s.dequeueCommand);

  const wsRef = useRef<WebSocket | null>(null);
  const attemptsRef = useRef(0);
  const pingTimerRef = useRef<number | null>(null);
  const aliveRef = useRef(false);
  const pendingAcksRef = useRef<Record<string, (ok:boolean)=>void>>({});

  const connect = useCallback(async () => {
    if (wsRef.current) return;
    try {
      // include Supabase token if available for auth validation on server
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      const url = token ? `${WS_PATH}?token=${encodeURIComponent(token)}` : WS_PATH;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        attemptsRef.current = 0;
        aliveRef.current = true;
        setConnected(true);
        pushLog({ level: "info", text: "System WS connected" });
        // flush command queue if any (optimistic)
        const queue = (useSystemStore.getState().commandQueue || []);
        queue.forEach((cmd) => {
          try {
            const envelope = { type: "command", id: cmd.id, action: cmd.action, meta: cmd.meta ?? {} };
            ws.send(JSON.stringify(envelope));
          } catch (e) { /* ignore */ }
        });
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          // msg examples: { type: 'system_status', data: {...} } or { type: 'history_point', data: {...} } or { type: 'ack', id: '...' }
          if (msg.type === "system_status") {
            setStatus(msg.data);
            setHeartbeat(Date.now());
          } else if (msg.type === "history_point") {
            pushHistory(msg.data);
          } else if (msg.type === "event") {
            pushLog({ level: msg.data.level || "info", text: msg.data.message || JSON.stringify(msg.data) });
          } else if (msg.type === "ack" && msg.id) {
            const cb = pendingAcksRef.current[msg.id];
            if (cb) { cb(true); delete pendingAcksRef.current[msg.id]; }
          } else if (msg.type === "pong") {
            setHeartbeat(Date.now());
          }
        } catch (err) {
          pushLog({ level: "error", text: "WS parse error" });
          console.error("ws parse", err);
        }
      };

      ws.onclose = () => {
        aliveRef.current = false;
        wsRef.current = null;
        setConnected(false);
        pushLog({ level: "warn", text: "System WS closed, will reconnect" });
        // schedule reconnect
        const delay = backoffMs(attemptsRef.current++);
        setTimeout(() => connect(), delay);
      };

      ws.onerror = (err) => {
        pushLog({ level: "error", text: "System WS error" });
        try { ws.close(); } catch {}
      };

      // set ping interval
      if (pingTimerRef.current) window.clearInterval(pingTimerRef.current);
      pingTimerRef.current = window.setInterval(() => {
        try {
          if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
          // if no heartbeat recently, force reconnect
          const last = useSystemStore.getState().lastHeartbeat ?? 0;
          if (Date.now() - last > 20000) {
            pushLog({ level: "warn", text: "Missed heartbeat, forcing reconnect" });
            wsRef.current.close();
            return;
          }
          wsRef.current.send(JSON.stringify({ type: "ping" }));
        } catch (e) { /* ignore */ }
      }, 8000);
    } catch (err) {
      pushLog({ level: "error", text: "WS connect failed" });
      const delay = backoffMs(attemptsRef.current++);
      setTimeout(() => connect(), delay);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const disconnect = useCallback(() => {
    if (pingTimerRef.current) { window.clearInterval(pingTimerRef.current); pingTimerRef.current = null; }
    try { wsRef.current?.close(); } catch {}
    wsRef.current = null;
    setConnected(false);
    pushLog({ level: "info", text: "System WS disconnected by client" });
  }, []);

  // command bus: send a command and return a promise that resolves when ack received or times out
  const sendCommand = useCallback((action: string, meta: any = {}) : Promise<void> => {
    const id = uuidv4();
    const envelope = { type: "command", id, action, meta };
    // optimistic enqueue
    enqueueCommand({ id, action, meta });
    return new Promise((resolve, reject) => {
      // setup ack handler
      const timeout = window.setTimeout(() => {
        delete pendingAcksRef.current[id];
        dequeueCommand(id);
        pushLog({ level: "error", text: `Command ${action} timed out` });
        reject(new Error("timeout"));
      }, 20000);

      pendingAcksRef.current[id] = (ok:boolean) => {
        window.clearTimeout(timeout);
        dequeueCommand(id);
        if (ok) resolve(); else reject(new Error("command failed"));
      };

      try {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify(envelope));
        } else {
          // not connected: queueing is already done; attempt immediate reconnect
          connect();
        }
      } catch (err) {
        delete pendingAcksRef.current[id];
        dequeueCommand(id);
        reject(err);
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // mount/unmount behaviour: auto connect once
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  // Respond to explicit init/stop events dispatched by the store
  useEffect(() => {
    const onInit = () => connect();
    const onStop = () => disconnect();
    window.addEventListener("system-init-socket", onInit as EventListener);
    window.addEventListener("system-stop-socket", onStop as EventListener);
    return () => {
      window.removeEventListener("system-init-socket", onInit as EventListener);
      window.removeEventListener("system-stop-socket", onStop as EventListener);
    };
  }, [connect, disconnect]);

  // expose a tiny API via window for debug (optional)
  useEffect(() => {
    (window as any).__SYSTEM_WS_SEND = sendCommand;
    return () => { delete (window as any).__SYSTEM_WS_SEND; };
  }, [sendCommand]);

  return { sendCommand, connect, disconnect, isAlive: () => aliveRef.current };
}
