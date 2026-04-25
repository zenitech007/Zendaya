import React from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface Props {
  data: { timestamp: string; cpu: number; memory: number; disk: number }[];
  onRefresh?: () => void;
}

const PerformanceHistoryChart: React.FC<Props> = ({ data, onRefresh }) => (
  <div className="bg-black/20 backdrop-blur-sm border border-blue-500/20 rounded-xl sm:rounded-2xl p-4 sm:p-6">
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-lg sm:text-xl font-semibold text-blue-400">Performance History (Last 30 Entries)</h2>
      {onRefresh && (
        <button
          onClick={onRefresh}
          className="px-3 py-1 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/30 rounded-lg text-xs sm:text-sm"
        >
          Refresh
        </button>
      )}
    </div>
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(55,65,81,0.5)" />
          <XAxis dataKey="timestamp" stroke="#9CA3AF" fontSize={10} />
          <YAxis stroke="#9CA3AF" fontSize={10} unit="%" />
          <Tooltip
            contentStyle={{ backgroundColor: 'rgba(31,41,55,0.8)', borderRadius: 8 }}
            itemStyle={{ color: '#E5E7EB', fontSize: 12 }}
          />
          <Line type="monotone" dataKey="cpu" stroke="#3B82F6" strokeWidth={2} dot={false} name="CPU" />
          <Line type="monotone" dataKey="memory" stroke="#10B981" strokeWidth={2} dot={false} name="Memory" />
          <Line type="monotone" dataKey="disk" stroke="#8B5CF6" strokeWidth={2} dot={false} name="Disk" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  </div>
);

export default PerformanceHistoryChart;
