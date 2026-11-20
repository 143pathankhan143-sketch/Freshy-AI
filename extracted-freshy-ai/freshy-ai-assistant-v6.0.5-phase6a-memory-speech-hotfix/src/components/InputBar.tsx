import React, { useState } from "react";
import { Calculator, Clock, FileText, Globe, Send, Sparkles } from "lucide-react";

interface InputBarProps {
  onSendMessage: (text: string) => void;
}

export const InputBar: React.FC<InputBarProps> = ({ onSendMessage }) => {
  const [input, setInput] = useState("");

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!input.trim()) return;
    onSendMessage(input);
    setInput("");
  };

  const presetChips = [
    { label: "👋 Hello Freshy", command: "Hello Freshy", icon: Sparkles },
    { label: "⏰ What time is it?", command: "What time is it?", icon: Clock },
    { label: "📝 Open Notepad", command: "Open Notepad", icon: FileText },
    { label: "🧮 Open Calculator", command: "Open Calculator", icon: Calculator },
    { label: "🌐 Open Google", command: "Open Google", icon: Globe },
  ];

  return (
    <div className="space-y-3 border-t border-slate-800 bg-slate-950/90 p-4">
      <div className="no-scrollbar flex items-center gap-2 overflow-x-auto pb-1">
        <span className="mr-1 shrink-0 font-mono text-[11px] uppercase tracking-wider text-slate-500">
          Quick Actions:
        </span>
        {presetChips.map((chip) => {
          const ChipIcon = chip.icon;
          return (
            <button
              key={chip.command}
              onClick={() => onSendMessage(chip.command)}
              className="flex shrink-0 items-center gap-1.5 rounded-full border border-cyan-500/30 bg-slate-900 px-3 py-1.5 text-xs text-cyan-300 transition-all hover:border-cyan-400 hover:bg-cyan-950/50"
            >
              <ChipIcon className="h-3.5 w-3.5 text-cyan-400" />
              <span>{chip.label}</span>
            </button>
          );
        })}
      </div>

      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Type a desktop preview command or AI question..."
          className="flex-1 rounded-xl border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 transition-all focus:border-cyan-500/50 focus:outline-none"
        />

        <button
          type="submit"
          disabled={!input.trim()}
          className="rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 p-3 font-bold text-slate-950 shadow-md shadow-cyan-500/20 transition-all hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Send className="h-5 w-5" />
        </button>
      </form>
    </div>
  );
};
