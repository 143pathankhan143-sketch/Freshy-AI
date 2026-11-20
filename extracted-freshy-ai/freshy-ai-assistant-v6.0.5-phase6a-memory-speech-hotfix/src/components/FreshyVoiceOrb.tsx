import React from "react";
import { motion } from "motion/react";
import { Mic, Brain, Volume2, Radio, AlertCircle } from "lucide-react";

export type OrbState = "idle" | "listening" | "thinking" | "speaking" | "offline";

interface FreshyVoiceOrbProps {
  state: OrbState;
  onTap?: () => void;
  size?: number;
}

export const FreshyVoiceOrb: React.FC<FreshyVoiceOrbProps> = ({
  state,
  onTap,
  size = 120,
}) => {
  const getOrbDetails = () => {
    switch (state) {
      case "listening":
        return {
          label: "LISTENING...",
          color: "#38bdf8",
          secondaryColor: "#00f2fe",
          icon: Mic,
        };
      case "thinking":
        return {
          label: "THINKING...",
          color: "#a855f7",
          secondaryColor: "#c084fc",
          icon: Brain,
        };
      case "speaking":
        return {
          label: "FRESHY IS SPEAKING",
          color: "#10b981",
          secondaryColor: "#34d399",
          icon: Volume2,
        };
      case "offline":
        return {
          label: "CORE OFFLINE",
          color: "#ef4444",
          secondaryColor: "#f87171",
          icon: AlertCircle,
        };
      case "idle":
      default:
        return {
          label: "FRESHY READY",
          color: "#00f2fe",
          secondaryColor: "#38bdf8",
          icon: Radio,
        };
    }
  };

  const details = getOrbDetails();
  const IconComponent = details.icon;

  return (
    <div className="flex flex-col items-center justify-center select-none my-3">
      <div
        onClick={onTap}
        style={{ width: size, height: size }}
        className="relative flex items-center justify-center cursor-pointer group"
      >
        {/* 1. Outward ripple rings for listening or speaking */}
        {(state === "listening" || state === "speaking") && (
          <>
            <motion.div
              animate={{ scale: [1, 1.8], opacity: [0.6, 0] }}
              transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
              className="absolute inset-0 rounded-full border-2"
              style={{ borderColor: details.color }}
            />
            <motion.div
              animate={{ scale: [1, 2.2], opacity: [0.4, 0] }}
              transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut", delay: 0.6 }}
              className="absolute inset-0 rounded-full border"
              style={{ borderColor: details.secondaryColor }}
            />
          </>
        )}

        {/* 2. Rotating Segmented Ring for Thinking */}
        {state === "thinking" && (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            className="absolute -inset-2 rounded-full border-2 border-dashed border-purple-400 opacity-80"
          />
        )}

        {/* 3. Outer Glowing Breathing Atmosphere */}
        <motion.div
          animate={{
            scale: state === "speaking" ? [1, 1.15, 1] : state === "offline" ? [1] : [1, 1.08, 1],
            opacity: state === "offline" ? [0.3] : [0.4, 0.7, 0.4],
          }}
          transition={{
            duration: state === "thinking" ? 1 : state === "speaking" ? 0.8 : 3,
            repeat: state === "offline" ? 0 : Infinity,
            ease: "easeInOut",
          }}
          className="absolute inset-0 rounded-full"
          style={{
            background: `radial-gradient(circle, ${details.color} 0%, transparent 70%)`,
            filter: "blur(12px)",
          }}
        />

        {/* 4. Core Inner Reactor Sphere */}
        <div
          className="relative z-10 w-20 h-20 rounded-full flex flex-col items-center justify-center shadow-2xl border border-white/20 transition-all duration-300 group-hover:scale-105"
          style={{
            background: `radial-gradient(circle at 35% 35%, #ffffff 0%, ${details.color} 50%, #0f172a 100%)`,
            boxShadow: `0 0 25px ${details.color}80`,
          }}
        >
          {state === "speaking" ? (
            /* Animated Waveform Bars */
            <div className="flex items-center gap-1 h-6">
              {[0, 1, 2, 3, 4].map((i) => (
                <motion.div
                  key={i}
                  animate={{ height: ["8px", "20px", "8px"] }}
                  transition={{
                    duration: 0.6,
                    repeat: Infinity,
                    delay: i * 0.12,
                    ease: "easeInOut",
                  }}
                  className="w-1 bg-white rounded-full"
                />
              ))}
            </div>
          ) : (
            <IconComponent className="w-8 h-8 text-slate-950 drop-shadow-md stroke-[2.5]" />
          )}
        </div>
      </div>

      {/* Label Banner */}
      <motion.div
        initial={{ opacity: 0, y: 5 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-2 px-3 py-1 rounded-full bg-slate-900/90 border border-slate-800 shadow-md flex items-center gap-1.5"
      >
        <span
          className="w-2 h-2 rounded-full"
          style={{ backgroundColor: details.color }}
        />
        <span
          className="text-[11px] font-bold tracking-widest font-mono"
          style={{ color: details.color }}
        >
          {details.label}
        </span>
      </motion.div>
    </div>
  );
};
