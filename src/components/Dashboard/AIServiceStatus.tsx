import React from 'react';
import { Brain } from 'lucide-react';

interface AIServiceStatusProps {
  services: Record<string, boolean>;
}

const AIServiceStatus: React.FC<AIServiceStatusProps> = ({ services }) => (
  <div className="bg-black/20 backdrop-blur-sm border border-blue-500/20 rounded-xl sm:rounded-2xl p-4 sm:p-6">
    <h2 className="text-lg sm:text-xl font-semibold mb-4 sm:mb-6 flex items-center">
      <Brain className="w-4 h-4 sm:w-5 sm:h-5 mr-2 text-blue-400" />
      AI Services Status
    </h2>

    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
      {Object.entries(services).map(([service, status]) => (
        <div key={service} className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
          <span className="text-xs sm:text-sm capitalize">{service.replace(/_/g, ' ')}</span>
          <div className={`w-3 h-3 rounded-full ${status ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
        </div>
      ))}
    </div>
  </div>
);

export default AIServiceStatus;
