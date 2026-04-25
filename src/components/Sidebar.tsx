import React from "react";
import { motion } from "framer-motion";
import { Menu, Plus, Sparkles } from "lucide-react";
import { useChatStore } from "../hooks/useChatStore";
import { ZENDAYA_SESSION_KEY } from "../lib/constants";

/**
 * The collapsible sidebar component.
 */
export const Sidebar: React.FC = () => {
  // ✅ FIX: Select state individually to prevent infinite loop
  const isSidebarOpen = useChatStore((s) => s.isSidebarOpen);
  const toggleSidebar = useChatStore((s) => s.toggleSidebar);

  /**
   * Creates a new chat session by clearing session storage
   * and reloading the page.
   */
  const handleNewChat = () => {
    try {
      localStorage.removeItem(ZENDAYA_SESSION_KEY);
      // Reload the page with no session_id in the URL
      window.location.search = "";
    } catch (e) {
      console.error("Failed to clear session:", e);
      // Fallback: just reload
      window.location.reload();
    }
  };

  return (
    <motion.div
      animate={{ width: isSidebarOpen ? 260 : 60 }}
      transition={{ duration: 0.3, ease: "easeInOut" }}
      className="flex flex-col flex-shrink-0 h-full bg-slate-900/50 border-r border-slate-800 p-3"
    >
      {/* Collapse/Expand Button */}
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={toggleSidebar}
          className="p-2 rounded-md text-slate-300 hover:bg-slate-700/50"
          title={isSidebarOpen ? "Collapse menu" : "Expand menu"}
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>

      {/* New Chat Button */}
      <button
        onClick={handleNewChat}
        className={`flex items-center gap-3 p-3 rounded-lg text-sm font-medium transition-colors
          ${
            isSidebarOpen
              ? "w-full justify-start bg-blue-600 hover:bg-blue-500 text-white"
              : "w-10 justify-center bg-blue-600 hover:bg-blue-500 text-white"
          }
        `}
        title="New Chat"
      >
        <Plus className="w-4 h-4 flex-shrink-0" />
        {isSidebarOpen && <span className="truncate">New Chat</span>}
      </button>

      {/* Placeholder for recent chats */}
      <div className="flex-1 mt-4 overflow-y-auto space-y-2">
        <div className="text-slate-400 text-xs p-3">
          {isSidebarOpen ? "Recent" : ""}
        </div>

        {/* Static "Current Chat" button */}
        <button
          className={`flex items-center gap-3 p-3 rounded-lg text-sm text-left w-full transition-colors text-slate-300 bg-slate-700/50
            ${isSidebarOpen ? "" : "w-10 justify-center"}
          `}
        >
          <Sparkles className="w-4 h-4 flex-shrink-0" />
          {isSidebarOpen && <span className="truncate">Current Chat</span>}
        </button>
        {/* In a real app, this section would be populated dynamically */}
      </div>
    </motion.div>
  );
};
