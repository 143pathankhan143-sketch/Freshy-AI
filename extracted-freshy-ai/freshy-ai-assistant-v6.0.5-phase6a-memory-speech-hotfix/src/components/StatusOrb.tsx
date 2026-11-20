import React from "react";
import { motion } from "motion/react";
import { Mic, Radio, Brain, Volume2 } from "lucide-react";

export type FreshyStatusType = "idle" | "listening" | "thinking" | "speaking";

interface StatusOrbProps {
  status: FreshyStatusType;
  isConnected: boolean;
  connectionLabel?: string;
}

export const StatusOrb: React.FC<StatusOrbProps> = ({
  status,
  isConnected,
  connectionLabel = "Freshy Core • 127.0.0.1:8000",
}) => {
  const getStatusDetails = () => {
    if (!isConnected) {
      return {
        label: "CORE OFFLINE",
        color: "#ff4b4b",
        icon: Radio,
        bgGlow: "rgba(255, 75, 75, 0.2)",
      };
    }
    switch (status) {
      case "listening":
        return {
          label: "LISTENING...",
          color: "#ff416c",
          icon: Mic,
          bgGlow: "rgba(255, 65, 108, 0.25)",
        };
      case "thinking":
        return {
          label: "THINKING...",
          color: "#ffb703",
          icon: Brain,
          bgGlow: "rgba(255, 183, 3, 0.25)",
        };
      case "speaking":
        return {
          label: "SPEAKING",
          color: "#38ef7d",
          icon: Volume2,
          bgGlow: "rgba(56, 239, 125, 0.25)",
        };
      case "idle":
      default:
        return {
          label: "IDLE - READY",
          color: "#00f2fe",
          icon: Radio,
          bgGlow: "rgba(0, 242, 254, 0.2)",
        };
    }
  };

  const details = getStatusDetails();
  const IconComponent = details.icon;

  return (
    <div className="flex items-center gap-3 px-4 py-2 rounded-full bg-slate-900/80 border border-slate-700/60 backdrop-blur-md shadow-lg">
      {/* Reactor Orb */}
      <div className="relative flex items-center justify-center w-7 h-7">
        <motion.div
          animate={{
            scale: status === "listening" || status === "speaking" ? [1, 1.4, 1] : [1, 1.15, 1],
            opacity: [0.4, 0.8, 0.4],
          }}
          transition={{
            duration: status === "thinking" ? 0.8 : 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="absolute inset-0 rounded-full"
          style={{ backgroundColor: details.color, filter: "blur(6px)" }}
        />
        <div
          className="relative z-10 w-4 h-4 rounded-full flex items-center justify-center shadow-md"
          style={{ backgroundColor: details.color }}
        >
          <IconComponent className="w-2.5 h-2.5 text-slate-950 stroke-[3]" />
        </div>
      </div>

      <div className="flex flex-col">
        <span
          className="text-xs font-bold tracking-wider uppercase font-mono"
          style={{ color: details.color }}
        >
          {details.label}
        </span>
        <span className="text-[10px] text-slate-400 font-sans">
          {isConnected ? connectionLabel : "Attempting connection..."}
        </span>
      </div>
    </div>
  );
};
