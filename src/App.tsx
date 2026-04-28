import { Suspense, lazy } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Toaster } from "./components/ui/toaster";
import { Toaster as Sonner } from "sonner";
import { TooltipProvider } from "./components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useSystemMonitor } from "./hooks/useSystemMonitor";
import { useWakeWord } from "./hooks/useWakeWord";

// Lazy Pages
const Index = lazy(() => import("./pages/Index"));
const Devices = lazy(() => import("./pages/Devices"));
const Voice = lazy(() => import("./pages/Voice"));
const Settings = lazy(() => import("./pages/Settings"));
const NotFound = lazy(() => import("./pages/NotFound"));
const ZendayaChat = lazy(() => import("./pages/ZendayaChat"));
const SystemDashboard = lazy(() => import("./components/SystemDashboard"));
const UserManagement = lazy(() => import("./components/UserManagement"));
const AdminConsole = lazy(() => import("./pages/AdminConsole"));

// UI Globals
import { BottomNav } from "./components/BottomNav";
import { AICommandConsole } from "./components/AICommandConsole";

const queryClient = new QueryClient();

const App = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />

        <BrowserRouter>
          <RouteWrapper />
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

const RouteWrapper = () => {
  useWakeWord(true);
  useSystemMonitor();

  return (
    <>
      <Suspense
        fallback={
          <div className="text-center text-slate-400 mt-20">Loading...</div>
        }
      >
        <AnimatedRoutes />
      </Suspense>
    </>
  );
};

const AnimatedRoutes = () => {
  const location = useLocation();

  return (
    <>
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<AnimatedPage><Index /></AnimatedPage>} />
          <Route path="/dashboard" element={<AnimatedPage><SystemDashboard /></AnimatedPage>} />
          <Route path="/chat" element={<AnimatedPage><ZendayaChat /></AnimatedPage>} />
          <Route path="/devices" element={<AnimatedPage><Devices /></AnimatedPage>} />
          <Route path="/voice" element={<AnimatedPage><Voice /></AnimatedPage>} />
          <Route path="/settings" element={<AnimatedPage><Settings /></AnimatedPage>} />
          <Route path="/users" element={<AnimatedPage><UserManagement /></AnimatedPage>} />
          <Route path="/admin" element={<AnimatedPage><AdminConsole /></AnimatedPage>} />
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route path="*" element={<AnimatedPage><NotFound /></AnimatedPage>} />
        </Routes>
      </AnimatePresence>

      <BottomNav />
      <AICommandConsole />
    </>
  );
};

const AnimatedPage = ({ children }: { children: React.ReactNode }) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -10 }}
    transition={{ duration: 0.15 }}
    className="h-full w-full"
  >
    {children}
  </motion.div>
);

export default App;
