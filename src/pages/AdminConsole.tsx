// src/pages/AdminConsole.tsx (or the canvas code you created)
import React, { useMemo, useState } from "react";
import { useSystemStore } from "@/hooks/useSystemStore";
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { supabase } from "@/lib/supabaseClient";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export default function AdminConsole() {
  const status = useSystemStore((s) => s.status);
  const [isWorking, setIsWorking] = useState(false);
  // assume your store keeps history points in status.history
  const chartData = useMemo(() => status?.history ?? [], [status]);

  async function performAction(action: "restart-services" | "reboot" | "test-voice") {
    setIsWorking(true);
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;
      const res = await fetch(`${API_BASE}/system/${action}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || res.statusText);
      }
      const json = await res.json();
      toast({ title: "Action queued", description: `${action} started` });
      return json;
    } catch (err: unknown) {
      toast({ title: "Action failed", description: String(err), variant: "destructive" });
    } finally {
      setIsWorking(false);
    }
  }

  return (
    <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-6 bg-black text-white min-h-screen">
      {/* ...system status card (use status fields) ... */}
      <div>
        <h3>System Controls</h3>
        <div className="space-y-2">
          <Button onClick={() => performAction("restart-services")} disabled={isWorking}>Restart Services</Button>
          <Button variant="destructive" onClick={() => performAction("reboot")} disabled={isWorking}>Reboot Server</Button>
          <Button onClick={() => performAction("test-voice")} disabled={isWorking}>Play Test Voice</Button>
        </div>
      </div>

      {/* Performance Graph using real history */}
      <div>
        <h3>Performance</h3>
        <LineChart width={600} height={200} data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="timestamp" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="cpu" />
          <Line type="monotone" dataKey="memory" />
        </LineChart>
      </div>

      {/* Logs / AI console placeholders — you can wire these to REST endpoints later */}
    </div>
  );
}
