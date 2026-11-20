import React, { useEffect, useState } from "react";
import { Header } from "./components/Header";
import { ChatArea, Message } from "./components/ChatArea";
import { InputBar } from "./components/InputBar";
import { CodebaseInspector } from "./components/CodebaseInspector";
import { FreshyStatusType } from "./components/StatusOrb";
import { FreshyVoiceOrb, OrbState } from "./components/FreshyVoiceOrb";

export default function App() {
  const [activeTab, setActiveTab] = useState<"chat" | "code">("chat");
  const [status, setStatus] = useState<FreshyStatusType>("idle");
  const [isConnected, setIsConnected] = useState(true);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      sender: "freshy",
      text: "Freshy Phase 6 desktop web preview is ready. Native Windows voice, microphone, Live Voice, memory, and desktop actions run through the Flutter application and Python Core.",
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      intentName: "SYSTEM_READY",
    },
  ]);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        const res = await fetch("/health");
        setIsConnected(res.ok);
      } catch {
        setIsConnected(false);
      }
    };
    checkConnection();
    const timer = setInterval(checkConnection, 8000);
    return () => clearInterval(timer);
  }, []);

  const handleSendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: "user",
      text: trimmed,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    setMessages((previous) => [...previous, userMsg]);
    setStatus("thinking");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          session_id: "desktop-web-preview",
        }),
      });

      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();

      setMessages((previous) => [
        ...previous,
        {
          id: (Date.now() + 1).toString(),
          sender: "freshy",
          text: data.reply || "Freshy processed your request.",
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
          intentName: data.intent_name,
          actionExecuted: data.action_executed,
        },
      ]);
    } catch {
      setMessages((previous) => [
        ...previous,
        {
          id: (Date.now() + 1).toString(),
          sender: "freshy",
          text: "The desktop web preview could not reach its local server. The main Windows application still uses Flutter with Python Core on 127.0.0.1:8000.",
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
          intentName: "ERROR",
        },
      ]);
    } finally {
      setStatus("idle");
    }
  };

  const getOrbState = (): OrbState => {
    if (!isConnected) return "offline";
    return status;
  };

  const handleOrbTap = () => {
    if (!isConnected) return;
    setStatus((current) => (current === "idle" ? "listening" : "idle"));
  };

  return (
    <div className="flex h-screen w-screen select-none flex-col overflow-hidden bg-slate-950 font-sans text-slate-100">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        status={status}
        isConnected={isConnected}
      />

      {activeTab === "chat" ? (
        <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col overflow-hidden">
          <FreshyVoiceOrb state={getOrbState()} onTap={handleOrbTap} size={110} />
          <ChatArea messages={messages} />
          <InputBar onSendMessage={handleSendMessage} />
        </main>
      ) : (
        <CodebaseInspector />
      )}
    </div>
  );
}
