import React, { useState, useEffect } from 'react';
import { Cpu, Mic, MicOff, Volume2, Wifi, Battery, HardDrive, Activity, Zap, Shield, Home, Calendar, Mail, Search, Settings, Power } from 'lucide-react';

interface SystemStatus {
  cpu: number;
  memory: number;
  disk: number;
  network: boolean;
  services: {
    gemini: boolean;
    elevenlabs: boolean;
    rag: boolean;
    agent: boolean;
    offline_intelligence: boolean;
    error_understanding: boolean;
  };
}

function App() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    cpu: 0,
    memory: 0,
    disk: 0,
    network: true,
    services: {
      gemini: false,
      elevenlabs: false,
      rag: false,
      agent: false,
      offline_intelligence: false,
      error_understanding: false
    }
  });

  const [isListening, setIsListening] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'online' | 'offline' | 'degraded'>('online');

  useEffect(() => {
    // Simulate system monitoring
    const interval = setInterval(() => {
      setSystemStatus(prev => ({
        ...prev,
        cpu: Math.random() * 100,
        memory: Math.random() * 100,
        disk: Math.random() * 100,
        services: {
          gemini: Math.random() > 0.1,
          elevenlabs: Math.random() > 0.05,
          rag: Math.random() > 0.1,
          agent: Math.random() > 0.1,
          offline_intelligence: true,
          error_understanding: true
        }
      }));
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (value: number) => {
    if (value < 30) return 'text-green-400';
    if (value < 70) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getServiceStatus = (isOnline: boolean) => {
    return isOnline ? 'text-green-400' : 'text-red-400';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 text-white">
      {/* Header */}
      <div className="border-b border-blue-500/20 bg-black/20 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="relative">
                <div className="w-12 h-12 rounded-full bg-gradient-to-r from-blue-400 to-cyan-400 flex items-center justify-center">
                  <Zap className="w-6 h-6 text-white" />
                </div>
                <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-400 rounded-full animate-pulse"></div>
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                  ZENDAYA AI SYSTEM
                </h1>
                <p className="text-sm text-blue-300">JARVIS Architecture • Distributed Intelligence</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-6">
              <div className={`flex items-center space-x-2 px-3 py-1 rounded-full border ${
                connectionStatus === 'online' ? 'border-green-400/50 bg-green-400/10' :
                connectionStatus === 'degraded' ? 'border-yellow-400/50 bg-yellow-400/10' :
                'border-red-400/50 bg-red-400/10'
              }`}>
                <div className={`w-2 h-2 rounded-full ${
                  connectionStatus === 'online' ? 'bg-green-400' :
                  connectionStatus === 'degraded' ? 'bg-yellow-400' :
                  'bg-red-400'
                } animate-pulse`}></div>
                <span className="text-sm font-medium capitalize">{connectionStatus}</span>
              </div>
              
              <button
                onClick={() => setIsListening(!isListening)}
                className={`p-3 rounded-full transition-all duration-300 ${
                  isListening 
                    ? 'bg-red-500 hover:bg-red-600 shadow-lg shadow-red-500/25' 
                    : 'bg-blue-500 hover:bg-blue-600 shadow-lg shadow-blue-500/25'
                }`}
              >
                {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* System Status */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-black/20 backdrop-blur-sm border border-blue-500/20 rounded-2xl p-6">
              <h2 className="text-xl font-semibold mb-6 flex items-center">
                <Activity className="w-5 h-5 mr-2 text-blue-400" />
                System Performance
              </h2>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Cpu className="w-4 h-4 text-blue-400" />
                      <span className="text-sm">CPU Usage</span>
                    </div>
                    <span className={`text-sm font-mono ${getStatusColor(systemStatus.cpu)}`}>
                      {systemStatus.cpu.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className="bg-gradient-to-r from-blue-400 to-cyan-400 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${systemStatus.cpu}%` }}
                    ></div>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Battery className="w-4 h-4 text-green-400" />
                      <span className="text-sm">Memory</span>
                    </div>
                    <span className={`text-sm font-mono ${getStatusColor(systemStatus.memory)}`}>
                      {systemStatus.memory.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className="bg-gradient-to-r from-green-400 to-emerald-400 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${systemStatus.memory}%` }}
                    ></div>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <HardDrive className="w-4 h-4 text-purple-400" />
                      <span className="text-sm">Storage</span>
                    </div>
                    <span className={`text-sm font-mono ${getStatusColor(systemStatus.disk)}`}>
                      {systemStatus.disk.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className="bg-gradient-to-r from-purple-400 to-pink-400 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${systemStatus.disk}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            {/* AI Services Status */}
            <div className="bg-black/20 backdrop-blur-sm border border-blue-500/20 rounded-2xl p-6">
              <h2 className="text-xl font-semibold mb-6 flex items-center">
                <Shield className="w-5 h-5 mr-2 text-blue-400" />
                AI Services Status
              </h2>
              
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {Object.entries(systemStatus.services).map(([service, status]) => (
                  <div key={service} className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
                    <span className="text-sm capitalize">{service.replace('_', ' ')}</span>
                    <div className={`w-3 h-3 rounded-full ${status ? 'bg-green-400' : 'bg-red-400'} animate-pulse`}></div>
                  </div>
                ))}
              </div>
            </div>

            {/* Capabilities Overview */}
            <div className="bg-black/20 backdrop-blur-sm border border-blue-500/20 rounded-2xl p-6">
              <h2 className="text-xl font-semibold mb-6 flex items-center">
                <Zap className="w-5 h-5 mr-2 text-blue-400" />
                Enhanced Capabilities
              </h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-3">
                  <h3 className="font-medium text-blue-300">Communication</h3>
                  <ul className="space-y-2 text-sm text-gray-300">
                    <li className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span>Advanced Noise Cancellation</span>
                    </li>
                    <li className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span>Error Understanding & Correction</span>
                    </li>
                    <li className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span>Context-Aware Clarification</span>
                    </li>
                    <li className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span>Emotional Intelligence</span>
                    </li>
                  </ul>
                </div>
                
                <div className="space-y-3">
                  <h3 className="font-medium text-blue-300">Intelligence</h3>
                  <ul className="space-y-2 text-sm text-gray-300">
                    <li className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span>Offline Knowledge Base</span>
                    </li>
                    <li className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span>Perfect Device Control</span>
                    </li>
                    <li className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span>Zero-Error Execution</span>
                    </li>
                    <li className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span>Anticipatory Intelligence</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          {/* Control Panel */}
          <div className="space-y-6">
            <div className="bg-black/20 backdrop-blur-sm border border-blue-500/20 rounded-2xl p-6">
              <h2 className="text-xl font-semibold mb-6 flex items-center">
                <Settings className="w-5 h-5 mr-2 text-blue-400" />
                Quick Controls
              </h2>
              
              <div className="space-y-4">
                <button className="w-full p-3 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/30 rounded-lg transition-all duration-200 flex items-center space-x-3">
                  <Home className="w-5 h-5 text-blue-400" />
                  <span>Smart Home Control</span>
                </button>
                
                <button className="w-full p-3 bg-green-500/20 hover:bg-green-500/30 border border-green-500/30 rounded-lg transition-all duration-200 flex items-center space-x-3">
                  <Calendar className="w-5 h-5 text-green-400" />
                  <span>Calendar Management</span>
                </button>
                
                <button className="w-full p-3 bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/30 rounded-lg transition-all duration-200 flex items-center space-x-3">
                  <Mail className="w-5 h-5 text-purple-400" />
                  <span>Email Assistant</span>
                </button>
                
                <button className="w-full p-3 bg-yellow-500/20 hover:bg-yellow-500/30 border border-yellow-500/30 rounded-lg transition-all duration-200 flex items-center space-x-3">
                  <Search className="w-5 h-5 text-yellow-400" />
                  <span>Web Intelligence</span>
                </button>
              </div>
            </div>

            {/* Voice Status */}
            <div className="bg-black/20 backdrop-blur-sm border border-blue-500/20 rounded-2xl p-6">
              <h2 className="text-xl font-semibold mb-4 flex items-center">
                <Volume2 className="w-5 h-5 mr-2 text-blue-400" />
                Voice System
              </h2>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm">ElevenLabs TTS</span>
                  <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-sm">Noise Cancellation</span>
                  <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-sm">Voice ID Lock</span>
                  <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
                </div>
                
                <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                  <p className="text-xs text-blue-300">
                    Voice ID: mxTlDrtKZzOqgjtBw4hM
                    <br />
                    <span className="text-gray-400">Zendaya's Signature Voice - Locked</span>
                  </p>
                </div>
              </div>
            </div>

            {/* System Actions */}
            <div className="bg-black/20 backdrop-blur-sm border border-blue-500/20 rounded-2xl p-6">
              <h2 className="text-xl font-semibold mb-4 flex items-center">
                <Power className="w-5 h-5 mr-2 text-blue-400" />
                System Actions
              </h2>
              
              <div className="space-y-3">
                <button className="w-full p-2 bg-green-500/20 hover:bg-green-500/30 border border-green-500/30 rounded-lg transition-all duration-200 text-sm">
                  Optimize Performance
                </button>
                
                <button className="w-full p-2 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/30 rounded-lg transition-all duration-200 text-sm">
                  Update Knowledge Base
                </button>
                
                <button className="w-full p-2 bg-yellow-500/20 hover:bg-yellow-500/30 border border-yellow-500/30 rounded-lg transition-all duration-200 text-sm">
                  Run Diagnostics
                </button>
                
                <button className="w-full p-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 rounded-lg transition-all duration-200 text-sm">
                  Emergency Protocols
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;