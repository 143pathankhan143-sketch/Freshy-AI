import React, { useState } from "react";
import { FileCode, FileText, Folder, Terminal } from "lucide-react";

interface FileNode {
  path: string;
  name: string;
  type: "file" | "dir";
  language?: string;
  content?: string;
  children?: FileNode[];
}

const PROJECT_TREE: FileNode[] = [
  {
    path: "freshy_app",
    name: "freshy_app (Flutter Windows UI)",
    type: "dir",
    children: [
      {
        path: "freshy_app/lib/main.dart",
        name: "lib/main.dart",
        type: "file",
        language: "dart",
        content:
          "// Flutter Windows entry point\n// Hosts the desktop chat, animated voice core, Memory Center, Voice Studio, and Live Voice settings.",
      },
      {
        path: "freshy_app/lib/services/freshy_api_service.dart",
        name: "lib/services/freshy_api_service.dart",
        type: "file",
        language: "dart",
        content:
          "// Typed desktop API client\n// Connects the Flutter application to Python FastAPI Core on 127.0.0.1:8000.",
      },
      {
        path: "freshy_app/lib/widgets/freshy_voice_orb.dart",
        name: "lib/widgets/freshy_voice_orb.dart",
        type: "file",
        language: "dart",
        content:
          "// Voice-reactive desktop orb\n// Displays idle, listening, thinking, speaking, interrupted, and offline states.",
      },
    ],
  },
  {
    path: "freshy_core",
    name: "freshy_core (Python Desktop Core)",
    type: "dir",
    children: [
      {
        path: "freshy_core/main.py",
        name: "main.py",
        type: "file",
        language: "python",
        content:
          "# FastAPI desktop backend\n# Exposes chat, voice, TTS, memory, Live Voice, provider status, and safe tool endpoints.",
      },
      {
        path: "freshy_core/ai/assistant_orchestrator.py",
        name: "ai/assistant_orchestrator.py",
        type: "file",
        language: "python",
        content:
          "# Central Freshy brain\n# Runs local-rule-first routing, memory recall, Tavily search, provider fallback, and safe tool handling.",
      },
      {
        path: "freshy_core/live/session_manager.py",
        name: "live/session_manager.py",
        type: "file",
        language: "python",
        content:
          "# Phase 6 Gemini Live manager\n# Maintains the warm session, streams PCM audio, handles interruption, reconnects, and tool responses.",
      },
      {
        path: "freshy_core/memory/service.py",
        name: "memory/service.py",
        type: "file",
        language: "python",
        content:
          "# Phase 5 persistent memory service\n# Applies privacy filtering, confirmation modes, relevant recall, and bounded SQLite persistence.",
      },
      {
        path: "freshy_core/tools/registry.py",
        name: "tools/registry.py",
        type: "file",
        language: "python",
        content:
          "# Typed safe-tool registry\n# Allows only validated Freshy actions and rejects arbitrary shell or unsafe arguments.",
      },
    ],
  },
  {
    path: "src",
    name: "src (Optional Desktop Web Preview)",
    type: "dir",
    children: [
      {
        path: "src/App.tsx",
        name: "App.tsx",
        type: "file",
        language: "typescript",
        content:
          "// Optional React desktop web preview\n// Provides a non-native chat preview and project-file explorer.",
      },
      {
        path: "src/server/ai/providerRouter.ts",
        name: "server/ai/providerRouter.ts",
        type: "file",
        language: "typescript",
        content:
          "// Web-preview multi-provider router\n// Preserves Groq, Mistral, Gemini, and SambaNova failover for the optional preview server.",
      },
      {
        path: "src/server/memory/persistentMemoryStore.ts",
        name: "server/memory/persistentMemoryStore.ts",
        type: "file",
        language: "typescript",
        content:
          "// Local memory used only by the optional desktop web preview.\n// The main Windows application uses the Python SQLite memory implementation.",
      },
    ],
  },
  {
    path: "index.html",
    name: "index.html (Desktop Web Preview)",
    type: "file",
    language: "html",
    content:
      "<!doctype html>\n<html>\n  <head><title>Freshy AI Desktop Web Preview</title></head>\n  <body><div id=\"root\"></div></body>\n</html>",
  },
  {
    path: "start_freshy.bat",
    name: "start_freshy.bat (Windows Launcher)",
    type: "file",
    language: "bat",
    content:
      "@echo off\nREM Starts Python Core and the Flutter Windows application.\nREM The optional React preview is not required for normal Freshy desktop use.",
  },
];

export const CodebaseInspector: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<FileNode>(
    PROJECT_TREE[1].children![0],
  );

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-slate-950 font-mono text-xs md:flex-row">
      <div className="w-full overflow-y-auto border-b border-slate-800 bg-slate-900/60 p-4 md:w-80 md:border-b-0 md:border-r">
        <h3 className="mb-3 flex items-center gap-2 font-bold uppercase tracking-wider text-slate-400">
          <Terminal className="h-4 w-4 text-cyan-400" />
          freshy_ai Workspace
        </h3>

        <div className="space-y-1">
          {PROJECT_TREE.map((node) => (
            <div key={node.path} className="space-y-1">
              {node.type === "dir" ? (
                <div>
                  <div className="flex items-center gap-1.5 py-1 font-semibold text-slate-300">
                    <Folder className="h-4 w-4 text-cyan-400" />
                    <span>{node.name}</span>
                  </div>
                  <div className="ml-2 space-y-1 border-l border-slate-800 pl-4">
                    {node.children?.map((child) => (
                      <button
                        key={child.path}
                        onClick={() => setSelectedFile(child)}
                        className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left transition-all ${
                          selectedFile.path === child.path
                            ? "border border-cyan-500/30 bg-cyan-500/10 text-cyan-400"
                            : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                        }`}
                      >
                        <FileCode className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{child.name}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setSelectedFile(node)}
                  className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left transition-all ${
                    selectedFile.path === node.path
                      ? "border border-cyan-500/30 bg-cyan-500/10 text-cyan-400"
                      : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                  }`}
                >
                  <FileText className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{node.name}</span>
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden bg-slate-950">
        <div className="flex items-center gap-2 border-b border-cyan-800/40 bg-cyan-950/40 px-4 py-2 text-[11px] text-cyan-300">
          This panel shows concise architectural summaries. The full source remains in the project files.
        </div>
        <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/40 px-4 py-3">
          <div className="flex items-center gap-2 text-slate-300">
            <FileCode className="h-4 w-4 text-cyan-400" />
            <span className="font-bold">{selectedFile.path}</span>
          </div>
          <span className="rounded bg-slate-800 px-2.5 py-1 font-sans text-xs text-slate-400">
            Architectural Overview
          </span>
        </div>
        <div className="flex-1 overflow-auto bg-slate-950/80 p-4 text-xs leading-relaxed text-slate-300">
          <pre className="whitespace-pre-wrap">{selectedFile.content}</pre>
        </div>
      </div>
    </div>
  );
};
