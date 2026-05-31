"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";

interface Message {
  role: "user" | "assistant";
  content: string;
  triggered?: string | null;
  timestamp: Date;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AdminAssistantPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hello! I am Optimus Assistant, your administrative co-pilot. I can query our Supabase listing analytics, fetch computational linguistics diagnostics, or execute pipeline runs directly. How can I assist you today?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const router = useRouter();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSendMessage = async (text: string) => {
    if (!text.trim() || sending) return;

    const userMsg: Message = {
      role: "user",
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);
    setIsTyping(true);

    try {
      const chatHistory = [...messages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await fetch(`${API_URL}/api/admin/assistant`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: chatHistory }),
        credentials: "include",
      });

      if (res.status === 401) {
        router.push("/admin/login");
        return;
      }
      if (!res.ok) throw new Error("Failed to receive response from agent");

      const data = await res.json();
      
      // Artificial slight delay to simulate "agent thinking"
      setTimeout(() => {
        setIsTyping(false);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.response,
            triggered: data.triggered,
            timestamp: new Date(),
          },
        ]);
        setSending(false);
      }, 1000);

    } catch (err: any) {
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "I apologize, I hit a brief communication error. Please ensure the backend server is running and try again.",
          timestamp: new Date(),
        },
      ]);
      setSending(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#050B14] text-gray-100 selection:bg-cyan-500/30 selection:text-cyan-200 overflow-hidden relative flex flex-col font-sans">
      {/* Background radial glows */}
      <div className="absolute top-[-100px] left-[-100px] w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-0 right-[-100px] w-[600px] h-[600px] bg-violet-600/5 rounded-full blur-[150px] pointer-events-none" />

      {/* Nav */}
      <nav className="max-w-6xl mx-auto w-full px-6 py-5 flex items-center justify-between border-b border-white/5 relative z-10 shrink-0">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 via-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <span className="text-white text-xs font-black tracking-tighter">OR</span>
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-bold text-white tracking-wider uppercase">Optimus Copilot</span>
              <span className="text-[9px] text-cyan-400 font-mono tracking-widest uppercase">Agent Hub</span>
            </div>
          </div>
          <div className="flex gap-5 text-xs font-semibold text-gray-400">
            <a href="/admin/dashboard" className="hover:text-white transition-colors">Overview</a>
            <a href="/admin/assistant" className="text-cyan-400 border-b-2 border-cyan-400 pb-1">Assistant</a>
            <a href="/admin/prospecting" className="hover:text-white transition-colors">Prospecting</a>
            <a href="/admin/prospects" className="hover:text-white transition-colors">Prospects</a>
            <a href="/admin/emails" className="hover:text-white transition-colors">Emails Queue</a>
            <a href="/admin/settings" className="hover:text-white transition-colors">Settings</a>
          </div>
        </div>
        <button
          onClick={async () => {
            await fetch(`${API_URL}/api/admin/logout`, {
              method: "POST",
              credentials: "include",
            });
            router.push("/admin/login");
          }}
          className="text-xs font-mono text-gray-500 hover:text-white transition-colors"
        >
          LOGOUT // EXIT
        </button>
      </nav>

      {/* Main chat cockpit */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-8 flex flex-col min-h-0 relative z-10 gap-4">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/5 shrink-0">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping absolute inset-0" />
              <div className="w-2.5 h-2.5 rounded-full bg-cyan-500 relative" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-white tracking-wider uppercase">Administrative Copilot Console</h1>
              <p className="text-[10px] text-gray-500 font-mono">Agent state: Listening & Ready</p>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded-full text-[9px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-bold uppercase tracking-wider">
            Gemini Core v1
          </span>
        </div>

        {/* Chat Feed */}
        <div className="flex-1 rounded-2xl border border-white/5 bg-[#060C16]/40 p-6 overflow-y-auto min-h-0 flex flex-col gap-4">
          {messages.map((msg, index) => (
            <div
              key={index}
              className={`flex flex-col max-w-[80%] ${
                msg.role === "user" ? "ml-auto items-end" : "mr-auto items-start"
              }`}
            >
              <div
                className={`rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                  msg.role === "user"
                    ? "bg-cyan-500 text-[#050B14] font-semibold rounded-br-none shadow-lg shadow-cyan-500/10"
                    : "bg-[#0A1220] border border-white/5 text-gray-300 rounded-bl-none"
                }`}
              >
                {msg.content}
                
                {msg.triggered && (
                  <div className="mt-3 p-2 rounded-lg border border-emerald-500/25 bg-emerald-500/5 text-[9px] font-mono text-emerald-400 flex items-center gap-1.5 uppercase font-bold tracking-wider">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    Triggered stage: {msg.triggered}
                  </div>
                )}
              </div>
              <span className="text-[9px] text-gray-500 font-mono mt-1 px-1">
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          ))}

          {isTyping && (
            <div className="flex flex-col mr-auto items-start max-w-[80%]">
              <div className="rounded-2xl rounded-bl-none px-4 py-3 bg-[#0A1220] border border-white/5 flex gap-1.5 items-center">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Quick Trigger Chips */}
        <div className="shrink-0 flex flex-wrap gap-2 py-1">
          {[
            { text: "Trigger Lead Enrichment", cmd: "Run Apollo enrichment sync" },
            { text: "Analyze Listing Scores", cmd: "Trigger listing scoring to calculate ALII" },
            { text: "Generate Outreach Sequences", cmd: "Generate cold outreach sequences" },
            { text: "Get Pipeline Averages", cmd: "Get aggregate pipeline telemetry averages" },
          ].map((chip, idx) => (
            <button
              key={idx}
              disabled={sending}
              onClick={() => handleSendMessage(chip.cmd)}
              className="px-3 py-1.5 rounded-full border border-white/5 bg-white/[0.01] hover:border-cyan-500/30 hover:bg-cyan-500/[0.02] text-[10px] text-gray-400 hover:text-cyan-400 font-medium transition-all"
            >
              {chip.text}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="shrink-0 flex gap-2">
          <input
            type="text"
            value={input}
            disabled={sending}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message or trigger pipeline action..."
            className="flex-1 rounded-xl bg-[#060C16] border border-white/5 hover:border-white/10 px-4 py-3 text-xs focus:outline-none focus:border-cyan-500/50 text-gray-300 font-sans"
            onKeyDown={(e) => e.key === "Enter" && handleSendMessage(input)}
          />
          <button
            onClick={() => handleSendMessage(input)}
            disabled={sending}
            className="px-5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-[#050B14] font-bold text-xs shadow-lg shadow-cyan-500/10 hover:shadow-cyan-500/20 transition-all"
          >
            Send
          </button>
        </div>
      </main>
    </div>
  );
}
