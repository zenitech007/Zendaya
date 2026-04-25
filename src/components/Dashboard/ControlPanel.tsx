import React, { useState } from "react";
import { Search, Users, Brain, Zap, Power } from "lucide-react";
import { toast } from "@/hooks/use-toast";

interface ControlPanelProps {
  onAction: (action: string) => Promise<void>;
  onManageUsers: () => void;
}

const ControlPanel: React.FC<ControlPanelProps> = ({ onAction, onManageUsers }) => {
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const handleAction = async (action: string) => {
    try {
      setLoadingAction(action);
      await onAction(action);
      toast({ title: "Success", description: `Action '${action}' completed!` });
    } catch (err: any) {
      console.error(err);
      toast({ title: "Error", description: `Action '${action}' failed.`, variant: "destructive" });
    } finally {
      setLoadingAction(null);
    }
  };

  const actions = [
    { name: "Discover Devices", icon: Search, action: "discover-devices", color: "blue" },
    { name: "Register Family Member", icon: Users, action: "register-user", color: "green" },
    { name: "Test Workflow", icon: Brain, action: "test-workflow", color: "purple" },
    { name: "Optimize Performance", icon: Zap, action: "optimize", color: "yellow" },
    { name: "Manage Users", icon: Users, action: "manage-users", color: "pink" },
    { name: "Test Voice", icon: Power, action: "test-voice", color: "cyan" },
  ];

  return (
    <div className="space-y-6">
      <div className="bg-black/20 backdrop-blur-sm border border-blue-500/20 rounded-xl sm:rounded-2xl p-4 sm:p-6">
        <h2 className="text-lg sm:text-xl font-semibold mb-4 sm:mb-6 flex items-center">
          <Users className="w-4 h-4 sm:w-5 sm:h-5 mr-2 text-blue-400" />
          System Actions
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-3 sm:gap-4">
          {actions.map(({ name, icon: Icon, action, color }) => (
            <button
              key={action}
              disabled={loadingAction !== null}
              onClick={action === "manage-users" ? onManageUsers : () => handleAction(action)}
              className={`flex items-center justify-center space-x-2 sm:space-x-3 p-3 bg-${color}-500/20 hover:bg-${color}-500/30 border border-${color}-500/30 rounded-xl transition-all duration-300 hover:scale-[1.02] active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <Icon className={`w-4 h-4 sm:w-5 sm:h-5 text-${color}-400`} />
              <span className="text-xs sm:text-sm">
                {loadingAction === action ? "Processing..." : name}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ControlPanel;
