import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { supabase } from "../lib/supabaseClient";
import { Loader2, LogIn, ChromeIcon } from "lucide-react";
import { AI_IDENTITY } from "../constants/identity"; // your AI identity file

// Backend base URL (your Python FastAPI / Flask app)
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export default function ZendayaLogin() {
  const [phase, setPhase] = useState<"intro" | "form">("intro");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  // Biometrics UI state
  const [capturingFace, setCapturingFace] = useState(false);
  const [capturingVoice, setCapturingVoice] = useState(false);
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setPhase("form"), 2400);
    return () => clearTimeout(timer);
  }, []);

  // === Supabase email login ===
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);

    try {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      setMessage("✅ Login successful — redirecting...");
      setTimeout(() => (window.location.href = "/dashboard"), 900);
    } catch (err: any) {
      setMessage(err?.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  // === Google OAuth via Supabase ===
  const handleGoogle = async () => {
    try {
      setLoading(true);
      await supabase.auth.signInWithOAuth({ provider: "google" });
      // Supabase will redirect automatically or open popup depending on config
      // After callback, user will land back and auth state will be set.
    } catch (err: any) {
      setMessage(err?.message || "Google sign-in failed");
    } finally {
      setLoading(false);
    }
  };

  // === FACE BIOMETRIC FLOW ===
  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      setCameraStream(stream);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (err) {
      console.error("Camera error", err);
      setMessage("Camera access denied or unavailable.");
    }
  }

  async function stopCamera() {
    try {
      cameraStream?.getTracks().forEach((t) => t.stop());
      setCameraStream(null);
      if (videoRef.current) {
        videoRef.current.pause();
        videoRef.current.srcObject = null;
      }
    } catch (e) {
      console.warn("stopCamera error", e);
    }
  }

  async function captureFaceAndSend() {
    setMessage(null);
    setCapturingFace(true);

    try {
      // Ensure camera started
      if (!cameraStream) await startCamera();
      // small delay to warm camera
      await new Promise((r) => setTimeout(r, 400));

      // create canvas and draw current frame
      const video = videoRef.current!;
      if (!video) throw new Error("Video element unavailable");
      const w = video.videoWidth || 320;
      const h = video.videoHeight || 240;

      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Canvas context unavailable");
      ctx.drawImage(video, 0, 0, w, h);

      // convert to blob (jpeg)
      const blob: Blob = await new Promise((resolve) =>
        canvas.toBlob((b) => b && resolve(b), "image/jpeg", 0.9)
      );

      // POST to backend biometric endpoint
      const fd = new FormData();
      fd.append("image", blob, "face.jpg");

      const res = await fetch(`${API_BASE}/biometric/face`, {
        method: "POST",
        body: fd,
      });

      const json = await res.json();
      if (!res.ok || !json.success) {
        throw new Error(json.message || "Face verification failed");
      }

      // Backend should return something like { success: true, user_id: "..." } or token
      setMessage("✅ Face recognized. Signing you in...");
      // OPTIONAL: If backend provides a token or supabase user id, handle it here.
      // For now, redirect to dashboard
      setTimeout(() => (window.location.href = "/dashboard"), 900);
    } catch (err: any) {
      console.error("Face biometric error", err);
      setMessage(err?.message || "Face recognition failed");
    } finally {
      setCapturingFace(false);
      // stop camera for privacy
      await stopCamera();
    }
  }

  // === VOICE BIOMETRIC FLOW ===
  async function startVoiceCapture() {
    setMessage(null);
    audioChunksRef.current = [];
    setCapturingVoice(true);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mr;

      mr.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) {
          audioChunksRef.current.push(ev.data);
        }
      };

      mr.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });

        // send to backend
        const fd = new FormData();
        fd.append("audio", audioBlob, "voice.webm");

        try {
          const res = await fetch(`${API_BASE}/biometric/voice`, {
            method: "POST",
            body: fd,
          });
          const json = await res.json();
          if (!res.ok || !json.success) {
            throw new Error(json.message || "Voice verification failed");
          }

          setMessage("✅ Voice recognized. Signing you in...");
          setTimeout(() => (window.location.href = "/dashboard"), 900);
        } catch (err: any) {
          console.error("Voice biometric error", err);
          setMessage(err?.message || "Voice recognition failed");
        } finally {
          setCapturingVoice(false);
          // stop tracks
          stream.getTracks().forEach((t) => t.stop());
        }
      };

      // record for ~3 seconds
      mr.start();
      setMessage("Listening... please say your verification phrase (e.g., 'Hey Zendaya')");
      setTimeout(() => {
        if (mr.state === "recording") mr.stop();
      }, 3000);
    } catch (err) {
      console.error("startVoiceCapture error", err);
      setCapturingVoice(false);
      setMessage("Microphone access denied or unavailable.");
    }
  }

  // UI helpers
  const showFullName = `${AI_IDENTITY.fullName}`; // ensure visible somewhere

  return (
    <div className="relative flex flex-col items-center justify-center min-h-screen overflow-hidden bg-[#04050a] text-white">
      {/* Background / subtle animated orb */}
      <div className="absolute inset-0 -z-10">
        <div className="w-full h-full bg-gradient-to-br from-indigo-900/30 via-slate-900 to-black animate-gradient-x" />
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <motion.div
            initial={{ scale: 0.94, opacity: 0.6 }}
            animate={{ scale: [0.94, 1.02, 0.94], opacity: [0.6, 0.85, 0.6] }}
            transition={{ repeat: Infinity, duration: 9, ease: "easeInOut" }}
            className="w-[420px] h-[420px] rounded-full bg-[radial-gradient(circle_at_center,#7c3aed_0%,transparent_70%)] blur-3xl opacity-60"
          />
        </div>
      </div>

      {/* Title */}
      <motion.h1
        initial={{ y: -8, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.8 }}
        className="text-4xl md:text-5xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-purple-500 to-pink-500"
      >
        {AI_IDENTITY.shortName}
      </motion.h1>

      <p className="mt-1 text-sm text-slate-400 max-w-xl text-center px-4">
        {showFullName}
      </p>

      <AnimatePresence mode="wait">
        {phase === "intro" ? (
          <motion.p
            key="intro"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.9 }}
            className="text-slate-300 text-center max-w-lg px-6 mt-4"
          >
            {AI_IDENTITY.introductions.mission}
          </motion.p>
        ) : (
          <motion.div
            key="form"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="mt-8 w-full max-w-2xl px-4"
          >
            <div className="grid md:grid-cols-2 gap-6 items-start">
              {/* Left: Login form */}
              <div className="bg-black/40 backdrop-blur-lg border border-white/8 p-6 rounded-2xl">
                <form onSubmit={handleLogin} className="space-y-4">
                  <div className="text-sm text-slate-300">Sign in with email</div>
                  <input
                    className="w-full px-3 py-2 bg-transparent border border-slate-700 rounded-lg focus:outline-none focus:border-cyan-400 text-white placeholder-slate-400"
                    placeholder="Email address"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                  <input
                    className="w-full px-3 py-2 bg-transparent border border-slate-700 rounded-lg focus:outline-none focus:border-purple-400 text-white placeholder-slate-400"
                    placeholder="Password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                  <div className="flex gap-3">
                    <button
                      type="submit"
                      disabled={loading}
                      className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-600 font-semibold"
                    >
                      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogIn className="w-4 h-4" />}
                      <span>{loading ? "Authenticating..." : "Sign in"}</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleGoogle}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg border border-white/10"
                    >
                      <Google className="w-4 h-4" />
                      <span>Sign in with Google</span>
                    </button>
                  </div>
                  <p className="text-xs text-slate-400">
                    Need an account? <a className="text-cyan-400 hover:underline" href="/signup">Sign up</a>
                  </p>
                </form>

                <div className="mt-6 border-t border-white/5 pt-4">
                  <div className="text-xs text-slate-300 mb-2">Biometric login</div>

                  {/* Face biometric */}
                  <div className="flex items-center gap-3">
                    <div className="flex-1">
                      <div className="text-sm text-slate-200">Face recognition</div>
                      <div className="text-xs text-slate-400">Use your camera to authenticate securely</div>
                    </div>
                    <div>
                      {!capturingFace ? (
                        <button
                          onClick={async () => {
                            await startCamera();
                            // small delay then capture
                            setTimeout(captureFaceAndSend, 700);
                          }}
                          className="px-3 py-1 rounded bg-emerald-500/90 text-black font-medium"
                        >
                          Use Face
                        </button>
                      ) : (
                        <div className="px-3 py-1 rounded bg-amber-400 text-black">Processing…</div>
                      )}
                    </div>
                  </div>

                  {/* Hidden video element for camera preview (for accessibility/test) */}
                  <div className="mt-3">
                    <video ref={videoRef} className="rounded-md w-48 h-32 object-cover hidden" />
                  </div>

                  {/* Voice biometric */}
                  <div className="flex items-center gap-3 mt-4">
                    <div className="flex-1">
                      <div className="text-sm text-slate-200">Voice recognition</div>
                      <div className="text-xs text-slate-400">Speak a short phrase — “Hey Zendaya”</div>
                    </div>
                    <div>
                      {!capturingVoice ? (
                        <button
                          onClick={startVoiceCapture}
                          className="px-3 py-1 rounded bg-cyan-400/90 text-black font-medium"
                        >
                          Use Voice
                        </button>
                      ) : (
                        <div className="px-3 py-1 rounded bg-amber-400 text-black">Listening…</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Right: Illustration / Orb + status */}
              <div className="flex flex-col items-center p-6 rounded-2xl bg-gradient-to-b from-black/30 to-black/10 border border-white/6">
                <div className="mb-4">
                  <div className="w-36 h-36 rounded-full bg-[linear-gradient(135deg,#06b6d4,#7c3aed,#ec4899)] shadow-[0_8px_40px_rgba(124,58,237,0.14)] flex items-center justify-center">
                    {/* small stylized orb */}
                    <div className="w-24 h-24 rounded-full bg-black/40 border border-white/6 backdrop-blur-md flex items-center justify-center">
                      <div className="text-white font-semibold">Z.E.N.D.A.Y.A.</div>
                    </div>
                  </div>
                </div>

                <div className="text-center">
                  <div className="text-xs text-slate-300 mb-1">Neural engine</div>
                  <div className="text-sm text-slate-100 mb-3">{AI_IDENTITY.shortName}</div>
                  <div className="text-xs text-slate-400 max-w-[220px] text-center">
                    {AI_IDENTITY.introductions.friendly}
                  </div>

                  <div className="mt-6 w-full">
                    <div className="text-xs text-slate-400 mb-2">Status</div>
                    <div className="flex items-center justify-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                      <div className="text-xs text-slate-300">Online</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* messages */}
            {message && (
              <div className="mt-5 text-center text-sm text-slate-200">{message}</div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="absolute bottom-6 text-xs text-slate-600">
        © {new Date().getFullYear()} Z.E.N.D.A.Y.A. Neural Systems
      </div>
    </div>
  );
}
