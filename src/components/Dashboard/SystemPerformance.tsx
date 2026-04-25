import React from "react";
import { Activity, Brain, Network } from "lucide-react";

interface Props {
  cpu: number;
  memory: number;
  disk: number;
}

const getColor = (value: number) => (value < 50 ? "bg-green-400" : value < 75 ? "bg-yellow-400" : "bg-red-400");

const SystemPerformance: React.FC<Props> = ({ cpu, memory, disk }) => (
  <div className="bg-black/20 backdrop-blur-sm border border-blue-500/20 rounded-xl p-4 sm:p-6 space-y-4">
    <h2 className="text-lg sm:text-xl font-semibold flex items-center text-blue-400">
      <Activity className="w-4 h-4 mr-2" /> Real-Time System Performance
    </h2>

    {[
      { label: "CPU Usage", value: cpu, icon: Activity, color: getColor(cpu) },
      { label: "Memory Usage", value: memory, icon: Brain, color: getColor(memory) },
      { label: "Disk Usage", value: disk, icon: Network, color: getColor(disk) },
    ].map(({ label, value, icon: Icon, color }) => (
      <div key={label} className="space-y-1">
        <div className="flex justify-between items-center text-xs sm:text-sm font-mono">
          <div className="flex items-center space-x-1"><Icon className="w-4 h-4" /><span>{label}</span></div>
          <span>{value.toFixed(1)}%</span>
        </div>
        <div className="w-full bg-gray-700/50 h-2 rounded">
          <div className={`${color} h-2 rounded transition-all duration-500`} style={{ width: `${value}%` }}></div>
        </div>
      </div>
    ))}
  </div>
);

export default SystemPerformance;
