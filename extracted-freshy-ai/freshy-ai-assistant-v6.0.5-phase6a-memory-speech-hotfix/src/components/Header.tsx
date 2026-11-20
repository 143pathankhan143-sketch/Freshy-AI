import React from "react";
import { Code2, MessageSquare, Sparkles } from "lucide-react";
import { StatusOrb, FreshyStatusType } from "./StatusOrb";

interface HeaderProps {
  activeTab: "chat" | "code";
  setActiveTab: (tab: "chat" | "code") => void;
  status: FreshyStatusType;
  isConnected: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  status,
  isConnected,
}) => {
  return (
    <header className="sticky top-0 z-30 border-b border-cyan-500/20 bg-slate-950/90 px-4 py-3 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 sm:flex-row">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 p-[1px] shadow-lg shadow-cyan-500/20">
            <div className="flex h-full w-full items-center justify-center rounded-[11px] bg-slate-950">
              <Sparkles className="h-5 w-5 text-cyan-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-mono text-lg font-bold tracking-wider text-white">
                FRESHY<span className="text-cyan-400">.AI</span>
              </h1>
              <span className="rounded-md border border-cyan-500/30 bg-cyan-950 px-2 py-0.5 font-mono text-[10px] font-semibold text-cyan-400">
                PHASE 6
              </span>
            </div>
            <p className="text-xs text-slate-400">Windows Desktop Assistant</p>
          </div>
        </div>

        <div className="flex max-w-full items-center gap-1 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 p-1">
          <button
            onClick={() => setActiveTab("chat")}
            className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              activeTab === "chat"
                ? "border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            Desktop Web Preview
          </button>

          <button
            onClick={() => setActiveTab("code")}
            className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              activeTab === "code"
                ? "border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Code2 className="h-3.5 w-3.5" />
            Project Files Explorer
          </button>
        </div>

        <StatusOrb
          status={status}
          isConnected={isConnected}
          connectionLabel="Desktop Web Preview • 127.0.0.1:3000"
        />
      </div>
    </header>
  );
};
