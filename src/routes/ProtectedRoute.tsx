// src/routes/ProtectedRoute.tsx
import React, { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { supabase } from "@/lib/supabaseClient";

export function ProtectedRoute({ children, requireRole }: { children: JSX.Element; requireRole?: string }) {
  const [loading, setLoading] = useState(true);
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    let mounted = true;
    (async () => {
      const { data } = await supabase.auth.getSession();
      const session = data.session;
      if (!session) {
        if (mounted) { setAllowed(false); setLoading(false); }
        return;
      }
      // Optionally fetch user metadata from supabase
      try {
        const user = session.user;
        // If you store roles in user.user_metadata.role:
        const role = (user.user_metadata as any)?.role || null;
        if (requireRole) {
          setAllowed(role === requireRole);
        } else {
          setAllowed(true);
        }
      } catch {
        setAllowed(false);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [requireRole]);

  if (loading) return <div>Checking permissions...</div>;
  if (!allowed) return <Navigate to="/login" replace />;
  return children;
}
