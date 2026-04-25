import React, { Suspense, lazy } from "react";
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
import { supabase } from "./lib/supabaseClient";
import { useSystemMonitor } from "./hooks/useSystemMonitor"; // ✅ GLOBAL SYSTEM WS DAEMON

// ✅ Voice hooks
//import { useVoiceInterface } from "./hooks/useVoiceInterface";// ✨ VOICE INTERFACE IMPORT FIXED
import { useWakeWord } from "./hooks/useWakeWord";

// Lazy Pages
const Index = lazy(() => import("./pages/Index"));
const Devices = lazy(() => import("./pages/Devices"));
const Voice = lazy(() => import("./pages/Voice"));
const Settings = lazy(() => import("./pages/Settings"));
const NotFound = lazy(() => import("./pages/NotFound"));
const ZendayaLogin = lazy(() => import("./components/ZendayaLogin"));
const ZendayaChat = lazy(() => import("./pages/ZendayaChat"));
const SystemDashboard = lazy(() => import("./components/SystemDashboard"));
const UserManagement = lazy(() => import("./components/UserManagement"));
const AdminConsole = lazy(() => import("./pages/AdminConsole"));

// UI Globals
import { BottomNav } from "./components/BottomNav";
import { AICommandConsole } from "./components/AICommandConsole";
// import { ZendayaOrb } from "./components/ZendayaOrb"; // ✨ ORB REMOVED

const queryClient = new QueryClient();

// ✅ Auth Guard
const ProtectedRoute = ({ children }: { children: JSX.Element }) => {
  const [session, setSession] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
      }
    );

    return () => listener?.subscription.unsubscribe();
  }, []);

  if (loading)
    return (
      <div className="flex h-screen items-center justify-center text-slate-200 text-lg">
        Initializing Z.E.N.D.A.Y.A...
      </div>
    );

  if (!session) return <Navigate to="/login" replace />;

  return children;
};

// ✅ App Root
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

// ✅ Route wrapper: Voice + Wake Word + Routes
const RouteWrapper = () => {
  // const location = useLocation(); // ✨ ORB LOGIC REMOVED
  // const showOrb =
  //   location.pathname !== "/login" && location.pathname !== "/chat"; // ✨ ORB LOGIC REMOVED

  // ✅ voice + wakeword engine initialization
  // useVoiceInterface(); // ⛔️ THIS IS NOW COMMENTED OUT
  useWakeWord(); // Note: You may want to comment this out too if you don't want wake word running without the orb
  useSystemMonitor(); // ✅ GLOBAL SYSTEM WS DAEMON

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

// ✅ Animated Routing
const AnimatedRoutes = () => {
  const location = useLocation();

  return (
    <>
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route path="/login" element={<ZendayaLogin />} />

          <Route
            path="/"
            element={
              <ProtectedRoute>
                <AnimatedPage>
                  <Index />
                </AnimatedPage>
              </ProtectedRoute>
            }
          />

          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <AnimatedPage>
                  <SystemDashboard />
                </AnimatedPage>
              </ProtectedRoute>
            }
          />

          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <AnimatedPage>
                  <ZendayaChat />
                </AnimatedPage>
              </ProtectedRoute>
            }
          />

          <Route
            path="/devices"
            element={
              <ProtectedRoute>
                <AnimatedPage>
                  <Devices />
                </AnimatedPage>
              </ProtectedRoute>
            }
          />

          <Route
            path="/voice"
            element={
              <ProtectedRoute>
                <AnimatedPage>
                  <Voice />
                </AnimatedPage>
              </ProtectedRoute>
            }
          />

          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <AnimatedPage>
                  <Settings />
                </AnimatedPage>
              </ProtectedRoute>
            }
          />

          <Route
            path="/users"
            element={
              <ProtectedRoute>
                <AnimatedPage>
                  <UserManagement />
                </AnimatedPage>
              </ProtectedRoute>
            }
          />

          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <AnimatedPage>
                  <AdminConsole />
                </AnimatedPage>
              </ProtectedRoute>
            }
          />

          <Route
            path="*"
            element={
              <AnimatedPage>
                <NotFound />
              </AnimatedPage>
            }
          />
        </Routes>
      </AnimatePresence>

      <BottomNav />
      <AICommandConsole />
    </>
  );
};

// ✅ Page Animation
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
