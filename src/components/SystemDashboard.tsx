import React, {
  useState,
  useEffect,
  useCallback,
  Suspense,
  lazy,
  memo,
} from "react";
import { Link } from "react-router-dom";
import { Header as SystemHeader } from "./SystemHeader";
import { useSystemStore } from "@/hooks/useSystemStore";
import { useSystemMonitor } from "@/hooks/useSystemMonitor";
import {
  Loader2,
  Wifi,
  WifiOff,
  Sun,
  Moon,
  Users,
  MessageSquare,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";


// Lazy load heavy components
const SystemPerformance = lazy(() => import("./Dashboard/SystemPerformance"));
const PerformanceHistoryChart = lazy(
  () => import("./Dashboard/PerformanceHistoryChart")
);
const AIServiceStatus = lazy(() => import("./Dashboard/AIServiceStatus"));
const ControlPanel = lazy(() => import("./Dashboard/ControlPanel"));
const UserManagement = lazy(() => import("./UserManagement"));

// Minimal reusable loader
const Loader: React.FC<{ message?: string }> = memo(({ message }) => (
  <div className="flex flex-col items-center justify-center py-16 text-slate-400 animate-pulse">
    <Loader2 className="w-8 h-8 mb-2 animate-spin" />
    <p className="text-sm">{message || "Loading Dashboard..."}</p>
  </div>
));

const SystemDashboard: React.FC = () => {
  const { status, isConnected: connected, performAction } = useSystemStore();
  useSystemMonitor(true);
  const [showUsers, setShowUsers] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const savedTheme = localStorage.getItem("theme") as "light" | "dark" | null;
    if (savedTheme) {
      setTheme(savedTheme);
      document.documentElement.classList.toggle("dark", savedTheme === "dark");
    } else {
      const prefersDark = window.matchMedia(
        "(prefers-color-scheme: dark)"
      ).matches;
      setTheme(prefersDark ? "dark" : "light");
      document.documentElement.classList.toggle("dark", prefersDark);
    }

    const listener = (e: MediaQueryListEvent) => {
      const newTheme = e.matches ? "dark" : "light";
      setTheme(newTheme);
      document.documentElement.classList.toggle("dark", e.matches);
    };

    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    mql.addEventListener("change", listener);
    return () => mql.removeEventListener("change", listener);
  }, []);

  const toggleTheme = useCallback(() => {
    const newTheme = theme === "dark" ? "light" : "dark";
    setTheme(newTheme);
    document.documentElement.classList.toggle("dark", newTheme === "dark");
    localStorage.setItem("theme", newTheme);
  }, [theme]);

  const handleSystemAction = useCallback(
    (detail: string) => {
      try {
        if (typeof performAction === "function") performAction(detail);
      } catch (err) {
        console.error("SystemDashboard: handleSystemAction failed", err);
      }
    },
    [performAction]
  );

  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent;
      handleSystemAction(ce?.detail);
    };
    window.addEventListener("dashboard-action", handler as EventListener);
    return () =>
      window.removeEventListener("dashboard-action", handler as EventListener);
  }, [handleSystemAction]);

  return (
    <div
      className={`min-h-screen transition-colors duration-500 ${
        theme === "dark"
          ? "bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 text-white"
          : "bg-gradient-to-br from-slate-50 via-blue-100 to-slate-50 text-slate-800"
      } overflow-hidden`}
    >
      <SystemHeader
        isConnected={connected}
        showBackButton={showUsers}
        onBack={() => setShowUsers(false)}
      />

      <div className="flex items-center justify-between px-6 pt-2 text-xs">
        <div className="flex items-center gap-1">
          {connected ? (
            <span className="flex items-center gap-1 text-emerald-400">
              <Wifi className="w-3 h-3" /> Connected
            </span>
          ) : (
            <span className="flex items-center gap-1 text-rose-400">
              <WifiOff className="w-3 h-3" /> Disconnected
            </span>
          )}
        </div>

        <button
          onClick={toggleTheme}
          className="flex items-center gap-2 px-3 py-1.5 border border-slate-600/40 rounded-md text-xs hover:bg-slate-700/10 transition"
          title={`Switch to ${theme === "dark" ? "Light" : "Dark"} Mode`}
        >
          {theme === "dark" ? (
            <>
              <Sun className="w-3.5 h-3.5 text-yellow-400" /> Light
            </>
          ) : (
            <>
              <Moon className="w-3.5 h-3.5 text-slate-600" /> Dark
            </>
          )}
        </button>
      </div>

      <main className="max-w-7xl mx-auto px-4 py-6 relative z-10">
        <AnimatePresence mode="sync">
          {showUsers ? (
            <motion.div
              key="users"
              initial={{ opacity: 0, x: 40 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -40 }}
              transition={{ duration: 0.3 }}
            >
              <Suspense fallback={<Loader message="Loading User Management..." />}>
                <UserManagement />
              </Suspense>
            </motion.div>
          ) : (
            <motion.div
              key="dashboard"
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -30 }}
              transition={{ duration: 0.35 }}
            >
              <Suspense fallback={<Loader message="Loading System Data..." />}>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <section className="lg:col-span-2 space-y-6">
                    <SystemPerformance
                      cpu={status?.cpu ?? 0}
                      memory={status?.memory ?? 0}
                      disk={status?.disk ?? 0}
                    />
                    <PerformanceHistoryChart data={status?.history ?? []} />
                    <AIServiceStatus services={status?.services ?? {}} />
                  </section>

                  <div className="space-y-4">
                    <ControlPanel
                      onAction={performAction}
                      onManageUsers={() => setShowUsers(true)}
                    />

                    <Link to="/chat">
                      <button
                        className={`flex items-center gap-2 w-full justify-center rounded-lg py-2 text-sm border transition ${
                          theme === "dark"
                            ? "bg-slate-800/40 hover:bg-slate-700/50 border-slate-700 text-slate-300"
                            : "bg-white hover:bg-slate-100 border-slate-300 text-slate-700"
                        }`}
                      >
                        <MessageSquare className="w-4 h-4" /> Open Zendaya Chat
                      </button>
                    </Link>

                    <button
                      onClick={() => setShowUsers(true)}
                      className={`flex items-center gap-2 w-full justify-center rounded-lg py-2 text-sm border transition ${
                        theme === "dark"
                          ? "bg-slate-800/40 hover:bg-slate-700/50 border-slate-700 text-slate-300"
                          : "bg-white hover:bg-slate-100 border-slate-300 text-slate-700"
                      }`}
                    >
                      <Users className="w-4 h-4" /> Manage Users
                    </button>
                  </div>
                </div>
              </Suspense>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <div
        className={`absolute inset-0 -z-10 transition-opacity duration-700 ${
          theme === "dark"
            ? "opacity-10 bg-[radial-gradient(ellipse_at_center,rgba(56,189,248,0.4),transparent_60%)]"
            : "opacity-20 bg-[radial-gradient(ellipse_at_center,rgba(37,99,235,0.2),transparent_70%)]"
        }`}
      />

    </div>
  );
};

export default memo(SystemDashboard);
