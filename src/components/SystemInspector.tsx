// src/components/SystemInspector.tsx
import React from "react";
import { useSystemStore } from "@/hooks/useSystemStore";

export function SystemInspector() {
  const logs = useSystemStore((s) => s.logs);
  const isConnected = useSystemStore((s) => s.isConnected);
  const lastHeartbeat = useSystemStore((s) => s.lastHeartbeat);
  const queue = useSystemStore((s) => s.commandQueue);

  return (
    <div className="fixed bottom-4 right-4 w-96 max-h-96 overflow-auto bg-black/80 border border-gray-700 p-3 rounded-lg text-sm text-white z-50">
      <div className="flex justify-between items-center mb-2">
        <div>System Inspector</div>
        <div className={`px-2 py-0.5 rounded ${isConnected ? "bg-green-700" : "bg-red-700"}`}>
          {isConnected ? "Online" : "Offline"}
        </div>
      </div>

      <div className="mb-2 text-xs text-gray-300">Heartbeat: {lastHeartbeat ? new Date(lastHeartbeat).toLocaleTimeString() : "never"}</div>

      <div className="mb-2">
        <strong>Queued Commands</strong>
        {queue.length === 0 ? <div className="text-gray-400">—</div> :
          queue.map((c) => <div key={c.id} className="text-xs text-yellow-300">{c.action} ({c.id.slice(0,8)})</div>)}
      </div>

      <div>
        <strong>Logs</strong>
        <div className="space-y-1 mt-2">
          {logs.slice().reverse().slice(0,50).map((l) => (
            <div key={l.ts} className="text-xs">
              <span className={`mr-2 ${l.level === "error" ? "text-red-400" : (l.level === "warn" ? "text-yellow-300" : "text-green-300")}`}>[{l.level}]</span>
              <span className="text-gray-200">{l.text}</span>
              <span className="text-gray-500 ml-2">({new Date(l.ts).toLocaleTimeString()})</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
