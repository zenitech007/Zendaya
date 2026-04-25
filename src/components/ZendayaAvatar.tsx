import React from "react";
import { motion } from "framer-motion";

interface AvatarProps {
  isSpeaking: boolean;
}

/**
 * The animated Zendaya AI avatar.
 */
export const ZendayaAvatar: React.FC<AvatarProps> = React.memo(
  ({ isSpeaking }) => {
    return (
      <div className="w-full h-full flex items-center justify-center p-8 bg-black/20 rounded-2xl border border-slate-800 backdrop-blur-sm">
        <motion.svg
          width="100%"
          viewBox="0 0 300 300"
          xmlns="http://www.w3.org/2000/svg"
          className="max-w-xs"
        >
          {/* Definitions for gradient and glow */}
          <defs>
            <linearGradient id="avatarGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#06b6d4" />
              <stop offset="100%" stopColor="#3b82f6" />
            </linearGradient>
            <filter
              id="avatarGlow"
              x="-50%"
              y="-50%"
              width="200%"
              height="200%"
            >
              <feGaussianBlur
                stdDeviation={isSpeaking ? "12" : "8"}
                result="blur"
              />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Outer glowing ring */}
          <motion.circle
            cx="150"
            cy="150"
            r="130"
            fill="none"
            stroke="url(#avatarGrad)"
            strokeWidth="2"
            filter="url(#avatarGlow)"
            animate={{
              scale: isSpeaking ? 1.05 : 1,
              opacity: isSpeaking ? 1 : 0.3,
            }}
            transition={{
              duration: 0.5,
              repeat: isSpeaking ? Infinity : 0,
              repeatType: "reverse",
              ease: "easeInOut",
            }}
          />

          {/* Inner rotating ring */}
          <motion.circle
            cx="150"
            cy="150"
            r="100"
            fill="none"
            stroke="url(#avatarGrad)"
            strokeWidth="1"
            opacity="0.5"
            animate={{ rotate: 360 }}
            transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
          />

          {/* Center "eye" shape */}
          <motion.path
            d="M 100 130 Q 150 100 200 130 Q 150 160 100 130 Z"
            fill="url(#avatarGrad)"
            opacity={isSpeaking ? 0.9 : 0.7}
            animate={{
              scaleY: isSpeaking ? [1, 1.1, 1] : 1,
              y: isSpeaking ? [0, -5, 0] : 0,
            }}
            transition={{
              duration: 0.7,
              repeat: isSpeaking ? Infinity : 0,
              repeatType: "reverse",
              ease: "circOut",
            }}
          />

          {/* "Mouth" lines */}
          <g stroke="#06b6d4" strokeWidth="2" strokeLinecap="round">
            {[...Array(5)].map((_, i) => (
              <motion.line
                key={i}
                x1={120 + i * 15}
                y1="180"
                x2={120 + i * 15}
                y2="180"
                animate={{
                  y2: isSpeaking ? 185 : 180,
                  opacity: isSpeaking ? 0.8 : 0.3,
                }}
                transition={{
                  duration: 0.05,
                  repeat: Infinity,
                  repeatType: "reverse",
                  ease: "linear",
                }}
              />
            ))}
          </g>
        </motion.svg>
      </div>
    );
  }
);
