"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useOmniWorkspace } from "./workspace-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ChatMessage {
  id: string;
  role: "human" | "agent" | "system";
  content: string;
  meta?: Record<string, any>;
}

export function AgentChatPanel() {
  const { workspace, setThreadId, addActiveAgent, removeActiveAgent, setStreaming } = useOmniWorkspace();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "agent",
      content:
        "Welcome to the Omni-Dashboard. I can analyze listings, scout competitors, project revenue, draft outreach, and manage your pipeline.\n\nSet an ASIN below and tell me what you'd like to do.",
    },
  ]);
  const [input, setInput] = useState("");
  const [pendingHuman, setPendingHuman] = useState<{
    prompt: string;
    payload: any;
  } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, pendingHuman]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || workspace.isStreaming) return;

    const humanMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "human",
      content: input.trim(),
    };
    setMessages((prev) => [...prev, humanMsg]);
    setInput("");
    setStreaming(true);

    try {
      const res = await fetch(`${API_BASE}/api/omni/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: workspace.threadId,
          message: humanMsg.content,
          workspace: {
            asin: workspace.asin,
            brand_key: workspace.brandKey,
            client_id: workspace.clientId,
          },
        }),
      });

      const newThreadId = res.headers.get("x-thread-id");
      if (newThreadId && !workspace.threadId) {
        setThreadId(newThreadId);
      }

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text);
      }

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const dataMatch = line.match(/^data: (.+)$/m);
          if (!dataMatch) continue;
          const event = JSON.parse(dataMatch[1]);

          if (event.event === "agent_complete") {
            addActiveAgent(event.data.agent);
            setMessages((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "agent",
                content: `**${event.data.agent}** completed.`,
                meta: event.data.output,
              },
            ]);
          }

          if (event.event === "synthesis") {
            setMessages((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "agent",
                content: event.data.content,
              },
            ]);
          }

          if (event.event === "human_input_required") {
            setPendingHuman({
              prompt: event.data.prompt,
              payload: event.data.payload,
            });
          }

          if (event.event === "error") {
            setMessages((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "system",
                content: `Error: ${event.data.message}`,
              },
            ]);
          }
        }
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "system",
          content: `Error: ${err.message || "Unknown error"}`,
        },
      ]);
    } finally {
      setStreaming(false);
    }
  }, [input, workspace, setThreadId, addActiveAgent, setStreaming]);

  const handleHumanResponse = useCallback(
    async (action: "approve" | "reject" | "modify", modifications?: string) => {
      if (!workspace.threadId || !pendingHuman) return;
      setPendingHuman(null);
      setStreaming(true);

      try {
        const res = await fetch(`${API_BASE}/api/omni/resume`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            thread_id: workspace.threadId,
            human_response: { action, modifications },
            prior_state: {}, // Partial impl: backend reconstructs from checkpoint
          }),
        });

        if (!res.ok) {
          const text = await res.text();
          throw new Error(text);
        }

        // Simplified: in full impl we would stream the resume response similarly
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "agent",
            content: `Human input (${action}) processed.`,
            meta: data,
          },
        ]);
      } catch (err: any) {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "system",
            content: `Resume error: ${err.message}`,
          },
        ]);
      } finally {
        setStreaming(false);
      }
    },
    [workspace.threadId, pendingHuman, setStreaming]
  );

  return (
    <div className="flex h-full flex-col border-l border-[#E0E1DD]/10 bg-commandBlueDark/50">
      <div className="flex h-12 items-center gap-2 border-b border-[#E0E1DD]/10 px-4">
        <Bot className="h-4 w-4 text-[#00F5FF]" />
        <span className="text-xs font-display uppercase tracking-wider text-white">Agent Chat</span>
        {workspace.isStreaming && (
          <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin text-[#00F5FF]" />
        )}
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              "flex gap-2.5",
              msg.role === "human" ? "justify-end" : "justify-start"
            )}
          >
            {msg.role !== "human" && (
              <div className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#00F5FF]/10">
                {msg.role === "system" ? (
                  <AlertCircle className="h-3 w-3 text-amber-400" />
                ) : (
                  <Bot className="h-3 w-3 text-[#00F5FF]" />
                )}
              </div>
            )}
            <div
              className={cn(
                "max-w-[85%] rounded-md px-3 py-2 text-xs leading-relaxed",
                msg.role === "human"
                  ? "bg-[#00F5FF]/10 text-white"
                  : msg.role === "system"
                  ? "bg-amber-500/10 text-amber-200"
                  : "bg-white/[0.03] text-[#E0E1DD]"
              )}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
              {msg.meta && (
                <pre className="mt-2 max-h-32 overflow-auto rounded bg-black/20 p-2 text-[10px] text-[#E0E1DD]/60">
                  {JSON.stringify(msg.meta, null, 2)}
                </pre>
              )}
            </div>
            {msg.role === "human" && (
              <div className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/10">
                <User className="h-3 w-3 text-white" />
              </div>
            )}
          </div>
        ))}

        {pendingHuman && (
          <div className="rounded-md border border-amber-500/20 bg-amber-500/5 p-3">
            <div className="flex items-center gap-2 text-xs font-medium text-amber-300">
              <AlertCircle className="h-3.5 w-3.5" />
              Human approval required
            </div>
            <p className="mt-1 text-xs text-amber-200/80">{pendingHuman.prompt}</p>
            <div className="mt-3 flex gap-2">
              <Button
                size="sm"
                variant="outline"
                className="h-7 border-green-500/30 bg-green-500/10 text-[10px] text-green-300 hover:bg-green-500/20"
                onClick={() => handleHumanResponse("approve")}
              >
                <CheckCircle2 className="mr-1 h-3 w-3" /> Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-7 border-red-500/30 bg-red-500/10 text-[10px] text-red-300 hover:bg-red-500/20"
                onClick={() => handleHumanResponse("reject")}
              >
                Reject
              </Button>
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-[#E0E1DD]/10 p-3">
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask the Omni-Dashboard..."
            className="h-9 flex-1 border-[#E0E1DD]/10 bg-white/[0.03] text-xs text-white placeholder:text-[#E0E1DD]/40 focus-visible:ring-[#00F5FF]/30"
          />
          <Button
            size="sm"
            onClick={handleSend}
            disabled={workspace.isStreaming || !input.trim()}
            className="h-9 bg-[#00F5FF]/10 text-[#00F5FF] hover:bg-[#00F5FF]/20"
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
