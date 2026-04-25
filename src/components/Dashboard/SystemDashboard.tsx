import React, { useState, useEffect, useRef, Suspense, lazy } from 'react';
import SystemHeader from './SystemHeader';
import SystemPerformance from './SystemPerformance';
import PerformanceHistoryChart from './PerformanceHistoryChart';
import AIServiceStatus from './AIServiceStatus';
import ControlPanel from './ControlPanel';
import UserManagement from './UserManagement';
import SkeletonLoader from './SkeletonLoader';
import { toast } from "@/hooks/use-toast";

const ZendayaOrb = lazy(() => import('./ZendayaOrb'));

const SystemDashboard: React.FC = () => {
  const [systemStatus, setSystemStatus] = useState<any>({...});
  const [wsData, setWsData] = useState<any>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [historicalData, setHistoricalData] = useState<any[]>([]);
  const [showUserManagement, setShowUserManagement] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const socketRef = useRef<WebSocket | null>(null);

  // All WebSocket, metrics simulation, historicalData fetch logic here...
  // Reuse your previous logic but now smaller and modular

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 text-white font-sans pb-20 md:pb-0">
      <SystemHeader isConnected={isConnected} showBackButton={showUserManagement} onBack={() => setShowUserManagement(false)} />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {isLoading ? <SkeletonLoader /> : (
          showUserManagement ? <UserManagement /> :
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
            <section className="lg:col-span-2 space-y-6 sm:space-y-8">
              <SystemPerformance {...systemStatus} />
              <PerformanceHistoryChart data={historicalData} onRefresh={() => { /* fetchHistoricalData */ }} />
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
        <ZendayaOrb size={80} bottom={22} right={22} showChime href="/chat" showWakeWordToggle />
      </Suspense>
    </div>
  );
};

export default SystemDashboard;
