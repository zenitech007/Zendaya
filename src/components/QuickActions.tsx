import React from "react";
import {
  Search,
  Zap,
  Home,
  Wifi,
  WifiOff,
  Bluetooth,
  UserCheck,
  UserPlus,
  BrainCircuit,
  AppWindow,
  PhoneCall,
} from "lucide-react";
import { useChatStore } from "../hooks/useChatStore";
import { useSupabaseChat } from "../hooks/useSupabaseChat";
import { supabase } from "../lib/supabaseClient";

/**
 * A panel of quick action buttons to send commands to the AI.
 */
export const QuickActions: React.FC = () => {
  // Get user for auth token and session ID
  const { user } = useSupabaseChat();
  const sessionId = useChatStore((s) => s.sessionId);
  
  // Get store actions
  const { addSystemMessage, addOptimisticMessage, updateMessage, removeMessage } =
    useChatStore.getState();

  const actions = [
    { label: "Discover Devices", action: "discover-devices", icon: Search, color: "cyan" },
    { label: "Optimize System", action: "optimize", icon: Zap, color: "blue" },
    { label: "Control Home", action: "smart-home", icon: Home, color: "green" },
    { label: "Toggle WiFi", action: "toggle-wifi", icon: Wifi, color: "blue" },
    { label: "Toggle Bluetooth", action: "toggle-bluetooth", icon: Bluetooth, color: "indigo" },
    { label: "Recognize User", action: "biometric-recognize", icon: UserCheck, color: "pink" },
    { label: "Search Knowledge", action: "rag-search", icon: BrainCircuit, color: "amber" },
    { label: "Register User", action: "register-user", icon: UserPlus, color: "violet" },
    { label: "Open App", action: "open-app", icon: AppWindow, color: "gray" },
    { label: "Make Call", action: "make-call", icon: PhoneCall, color: "green" },
    { label: "Offline Status", action: "offline-status", icon: WifiOff, color: "gray" },
  ];

  const colorClasses = {
    cyan: { bg: "bg-cyan-600/30", border: "border-cyan-500/30", text: "text-cyan-300" },
    blue: { bg: "bg-blue-600/30", border: "border-blue-500/30", text: "text-blue-300" },
    indigo: { bg: "bg-indigo-600/30", border: "border-indigo-500/30", text: "text-indigo-300" },
    violet: { bg: "bg-violet-600/30", border: "border-violet-500/30", text: "text-violet-300" },
    green: { bg: "bg-green-600/30", border: "border-green-500/30", text: "text-green-300" },
    pink: { bg: "bg-pink-600/30", border: "border-pink-500/30", text: "text-pink-300" },
    amber: { bg: "bg-amber-600/30", border: "border-amber-500/30", text: "text-amber-300" },
    gray: { bg: "bg-gray-600/30", border: "border-gray-500/30", text: "text-gray-300" },
  };

  /**
   * Executes a command by sending it to the backend API.
   * @param {string} action The command action string.
   * @param {any} payload Optional payload for the command.
   */
  const executeAction = async (action: string, payload: any = {}) => {
    if (!sessionId) {
      addSystemMessage("Session not initialized. Cannot execute action.", true);
      return;
    }
    
    addSystemMessage(`Executing action: ${action}...`);

    // Add optimistic placeholder for the AI response
    const tempMsg = addOptimisticMessage({
      role: "ai",
      text: `Action response: ${action}\n...`,
    });

    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      // Get the latest auth token
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
      }

      const res = await fetch(`/api/command`, {
        method: "POST",
        headers: headers,
        body: JSON.stringify({
          action: action,
          payload: payload,
          session_id: sessionId,
          user_id: user?.id,
        }),
      });

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Action failed (${res.status}): ${errorText || res.statusText}`);
      }

      const data = await res.json();
      const formattedData = "```json\n" + JSON.stringify(data, null, 2) + "\n```";
      
      // Update the placeholder with the real data
      updateMessage(tempMsg.id, `Action response: ${action}\n${formattedData}`);
      
      // Persist the AI response
       const { error } = await supabase.from("zendaya_messages").insert({
          role: "ai",
          text: `Action response: ${action}\n${formattedData}`,
          session_id: sessionId
       });
       if(error) throw error;
       
       // Remove optimistic message, realtime will add the persisted one
       removeMessage(tempMsg.id);

    } catch (err: any) {
      addSystemMessage(`Action failed for '${action}': ${err.message}`, true);
      // Remove the optimistic placeholder on error
      removeMessage(tempMsg.id);
    }
  };

  /**
   * Handles the click event, prompting for input if necessary.
   * @param {string} action The action to perform.
   */
  const handleActionClick = (action: string) => {
    let payload: any = {};
    
    // NOTE: Uses browser `prompt`. For a real production app, 
    // this should be replaced with a custom modal component.
    try {
      switch (action) {
        case "smart-home":
          const homeCommand = prompt("Enter smart home command (e.g., 'turn on living room lights'):");
          if (homeCommand === null) return; // User cancelled
          payload = { command: homeCommand };
          break;
        case "rag-search":
          const query = prompt("Enter search query for knowledge base:");
          if (query === null) return; // User cancelled
          payload = { query: query };
          break;
        case "open-app":
          const appName = prompt("Which application to open?");
          if (appName === null) return; // User cancelled
          payload = { details: appName };
          break;
        case "make-call":
          const callNumber = prompt("Who do you want to call (name or number)?");
          if (callNumber === null) return; // User cancelled
          payload = { details: callNumber };
          break;
      }
    } catch (e) {
      console.error("Error using prompt (e.g., in headless environment):", e);
      return; // Abort action
    }
    
    // Execute with or without payload
    executeAction(action, payload);
  };

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-sm">
      {actions.map(({ label, action, icon: Icon, color }) => {
        const colors =
          colorClasses[color as keyof typeof colorClasses] || colorClasses.gray;
        return (
          <button
            key={action}
            onClick={() => handleActionClick(action)}
            className={`px-3 py-2 rounded-lg ${colors.bg} border ${colors.border} hover:scale-105 active:scale-95 transition flex items-center gap-2 text-white text-left`}
            title={`Execute action: ${label}`}
          >
            <Icon className={`w-4 h-4 ${colors.text} flex-shrink-0`} />
            <span className="truncate">{label}</span>
          </button>
        );
      })}
    </div>
  );
};
