import React, { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { User, Bot, CheckCircle2, Clock, Sparkles } from "lucide-react";

export interface Message {
  id: string;
  sender: "user" | "freshy" | "system";
  text: string;
  timestamp: string;
  intentName?: string;
  actionExecuted?: boolean;
}

interface ChatAreaProps {
  messages: Message[];
}

export const ChatArea: React.FC<ChatAreaProps> = ({ messages }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 font-sans">
      <AnimatePresence initial={false}>
        {messages.map((msg) => {
          const isUser = msg.sender === "user";

          return (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className={`flex items-start gap-3 max-w-3xl ${
                isUser ? "ml-auto flex-row-reverse" : "mr-auto"
              }`}
            >
              {/* Avatar Icon */}
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 shadow-md ${
                  isUser
                    ? "bg-cyan-500/20 border border-cyan-400/40 text-cyan-300"
                    : "bg-slate-900 border border-slate-700 text-cyan-400"
                }`}
              >
                {isUser ? (
                  <User className="w-4 h-4" />
                ) : (
                  <Bot className="w-4 h-4 text-cyan-400" />
                )}
              </div>

              {/* Bubble Body */}
              <div
                className={`rounded-2xl p-4 shadow-xl border ${
                  isUser
                    ? "bg-cyan-950/60 border-cyan-500/40 text-cyan-50"
                    : "bg-slate-900/90 border-slate-800 text-slate-100"
                }`}
              >
                {/* Header Tag */}
                <div className="flex items-center gap-2 mb-1.5">
                  <span
                    className={`text-[10px] font-mono font-bold tracking-wider uppercase ${
                      isUser ? "text-cyan-400" : "text-blue-400"
                    }`}
                  >
                    {isUser ? "YOU" : "FRESHY AI"}
                  </span>

                  {msg.intentName && (
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold bg-cyan-950/80 text-cyan-300 border border-cyan-500/30 flex items-center gap-1">
                      <Sparkles className="w-2.5 h-2.5 text-cyan-400" />
                      {msg.intentName}
                    </span>
                  )}

                  {msg.actionExecuted && (
                    <span className="text-[10px] text-emerald-400 flex items-center gap-1 font-mono">
                      <CheckCircle2 className="w-3 h-3" />
                      Executed
                    </span>
                  )}
                </div>

                {/* Text Message */}
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {msg.text}
                </p>

                {/* Footer Timestamp */}
                <div className="mt-2 flex items-center gap-1 text-[10px] text-slate-500 font-mono">
                  <Clock className="w-2.5 h-2.5" />
                  <span>{msg.timestamp}</span>
                </div>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>

      <div ref={bottomRef} />
    </div>
  );
};
