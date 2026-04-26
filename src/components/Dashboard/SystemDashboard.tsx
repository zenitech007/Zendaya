import React, { useState, useEffect, useRef, useCallback, Suspense, lazy } from 'react';
import SystemPerformance from './SystemPerformance';
import PerformanceHistoryChart from './PerformanceHistoryChart';
import AIServiceStatus from './AIServiceStatus';
import ControlPanel from './ControlPanel';
import UserManagement from '../UserManagement';
import { supabase } from "@/lib/supabaseClient";

const ZendayaOrb = lazy(() =>
  import('../ZendayaOrb').then((m) => ({ default: m.ZendayaOrb }))
);

const WS_BASE = (
  import.meta.env.VITE_WS_BACKEND_URL || "ws://127.0.0.1:8000"
).replace(/\/$/, "");

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const MAX_HISTORY = 30;

interface SystemData {
  cpu: number;
  memory: number;
  disk: number;
  network: boolean;
  services: Record<string, boolean>;
  discoveredDevices: number;
  registeredUsers: number;
}

const defaultSystemData: SystemData = {
  cpu: 0,
  memory: 0,
  disk: 0,
  network: false,
  services: {},
  discoveredDevices: 0,
  registeredUsers: 0,
};

const SystemDashboard: React.FC = () => {
  const [systemStatus, setSystemStatus] = useState<SystemData>(defaultSystemData);
  const [isConnected, setIsConnected] = useState(false);
  const [historicalData, setHistoricalData] = useState<
    { timestamp: string; cpu: number; memory: number; disk: number }[]
  >([]);
  const [showUserManagement, setShowUserManagement] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number | null>(null);
  const backoff = useRef(2000);

  const connect = useCallback(async () => {
    // Get Supabase JWT for auth
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) {
      console.warn("[Dashboard WS] No auth token — skipping connect");
      setIsLoading(false);
      return;
    }

    if (socketRef.current) {
      try { socketRef.current.close(); } catch {}
    }

    const ws = new WebSocket(`${WS_BASE}/ws/system?token=${token}`);
    socketRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setIsLoading(false);
      backoff.current = 2000;
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === "ping") return;

        if (msg.type === "system" || msg.cpu !== undefined) {
          const next: SystemData = {
            cpu: msg.cpu ?? 0,
            memory: msg.memory ?? 0,
            disk: msg.disk ?? 0,
            network: msg.network ?? false,
            services: msg.services ?? {},
            discoveredDevices: msg.discoveredDevices ?? 0,
            registeredUsers: msg.registeredUsers ?? 0,
          };
          setSystemStatus(next);

          setHistoricalData((prev) => {
            const point = {
              timestamp: new Date().toLocaleTimeString(),
              cpu: next.cpu,
              memory: next.memory,
              disk: next.disk,
            };
            const updated = [...prev, point];
            return updated.length > MAX_HISTORY ? updated.slice(-MAX_HISTORY) : updated;
          });
        }
      } catch (e) {
        console.warn("[Dashboard WS] parse error", e);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      socketRef.current = null;
      scheduleReconnect();
    };

    ws.onerror = () => {
      setIsConnected(false);
    };
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimer.current) return;
    reconnectTimer.current = window.setTimeout(() => {
      reconnectTimer.current = null;
      backoff.current = Math.min(backoff.current * 2, 30000);
      connect();
    }, backoff.current);
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (socketRef.current) socketRef.current.close();
    };
  }, [connect]);

  const handleSystemAction = useCallback(async (action: string) => {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    const res = await fetch(`${API_BASE}/system/${action}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!res.ok) throw new Error(`Action failed: ${res.statusText}`);
    return res.json();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 text-white font-sans pb-20 md:pb-0">
      {/* Inline header with connection indicator */}
      <header className="sticky top-0 z-30 backdrop-blur-md bg-slate-900/70 border-b border-blue-500/20 px-4 sm:px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {showUserManagement && (
            <button
              onClick={() => setShowUserManagement(false)}
              className="text-xs px-3 py-1 rounded-md border border-blue-500/30 hover:bg-blue-500/10 transition"
            >
              &larr; Back
            </button>
          )}
          <h1 className="text-lg sm:text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-300 bg-clip-text text-transparent">
            Zendaya System Dashboard
          </h1>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
          <span className="text-slate-400">{isConnected ? "Live" : "Disconnected"}</span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-10 h-10 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : showUserManagement ? (
          <UserManagement />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
            <section className="lg:col-span-2 space-y-6 sm:space-y-8">
              <SystemPerformance
                cpu={systemStatus.cpu}
                memory={systemStatus.memory}
                disk={systemStatus.disk}
              />
              <PerformanceHistoryChart data={historicalData} />
              <AIServiceStatus services={systemStatus.services} />
            </section>
            <ControlPanel
              onAction={handleSystemAction}
              onManageUsers={() => setShowUserManagement(true)}
            />
          </div>
        )}
      </main>

      <Suspense fallback={null}>
        <ZendayaOrb />
      </Suspense>
    </div>
  );
};

export default SystemDashboard;
