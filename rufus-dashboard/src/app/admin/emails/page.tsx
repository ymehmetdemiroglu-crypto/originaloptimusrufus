"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface EmailStep {
  id: string;
  step_num: number;
  subject: string;
  body: string;
  overlap: number;
}

interface Conversation {
  id: string;
  direction: "outbound" | "inbound";
  subject: string | null;
  body: string;
  status: string;
  created_at: string;
}

interface BrandEmailQueue {
  brand_key: string;
  brand_name: string;
  stage: string;
  contact_email: string;
  contact_first_name: string;
  custom_subject: string | null;
  custom_body: string | null;
  worst_axis_at_send: string | null;
  anchor_asin: string | null;
  email_steps?: EmailStep[];
  conversations?: Conversation[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AdminEmailsPage() {
  const [queue, setQueue] = useState<BrandEmailQueue[]>([]);
  const [loading, setLoading] = useState(true);
  const [stageFilter, setStageFilter] = useState("");
  const [selectedBrand, setSelectedBrand] = useState<BrandEmailQueue | null>(null);
  const router = useRouter();

  const fetchEmailQueue = async () => {
    setLoading(true);
    try {
      let url = `${API_URL}/api/admin/emails`;
      if (stageFilter) url += `?stage=${stageFilter}`;

      const res = await fetch(url, {
        credentials: "include",
      });
      if (res.status === 401) {
        router.push("/admin/login");
        return;
      }
      if (!res.ok) throw new Error("Failed to load email queue");
      const data = await res.json();
      setQueue(data.brands || []);
      
      // Update selected brand details if open
      if (selectedBrand) {
        const updated = (data.brands || []).find((b: any) => b.brand_key === selectedBrand.brand_key);
        if (updated) setSelectedBrand(updated);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmailQueue();
  }, [stageFilter]);

  const handleApprove = async (brandKey: string) => {
    try {
      const res = await fetch(`${API_URL}/api/admin/emails/${brandKey}/approve`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) throw new Error("Approval failed");
      alert("Email draft approved and moved to SEQUENCED!");
      fetchEmailQueue();
    } catch (err: any) {
      alert(err.message || "Approval failed");
    }
  };

  return (
    <div className="min-h-screen bg-[#06060c] text-gray-100 selection:bg-violet-500/30 selection:text-violet-200">
      {/* Background radial glow */}
      <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-violet-600/5 rounded-full blur-[150px] pointer-events-none" />

      {/* Nav */}
      <nav className="max-w-6xl mx-auto w-full px-6 py-5 flex items-center justify-between border-b border-white/5 relative z-10">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-blue-600 flex items-center justify-center">
              <span className="text-white text-xs font-black">OR</span>
            </div>
            <span className="text-sm font-semibold text-white/90">Optimus Control</span>
          </div>
          <div className="flex gap-4 text-xs font-medium text-gray-400">
            <a href="/admin/dashboard" className="hover:text-white transition-colors">Overview</a>
            <a href="/admin/assistant" className="hover:text-cyan-400 transition-colors">Assistant</a>
            <a href="/admin/prospecting" className="hover:text-cyan-400 transition-colors">Prospecting</a>
            <a href="/admin/prospects" className="hover:text-white transition-colors">Prospects</a>
            <a href="/admin/emails" className="text-violet-400 font-bold">Emails Queue</a>
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
          className="text-xs text-gray-500 hover:text-white transition-colors"
        >
          Sign Out
        </button>
      </nav>

      {/* Content */}
      <main className="max-w-6xl mx-auto w-full px-6 py-12 space-y-8 relative z-10">
        {/* Title */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black text-white">AI Email Queue & Threads</h1>
            <p className="text-xs text-gray-500 mt-1">Review AI generated cold sequence drafts or monitor back-and-forth thread logs with prospects.</p>
          </div>

          {/* Filter */}
          <div className="flex gap-2">
            {["", "EMAIL_DRAFTED", "SEQUENCED", "REPLIED"].map((st) => (
              <button
                key={st}
                onClick={() => setStageFilter(st)}
                className={`px-3.5 py-2 rounded-xl text-xs font-semibold border transition-all ${
                  stageFilter === st
                    ? "bg-violet-600 text-white border-violet-500"
                    : "bg-white/5 text-gray-400 border-white/5 hover:border-white/10"
                }`}
              >
                {st === "" ? "All Queue" : st.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>

        {/* Layout Grid */}
        <div className="grid gap-6 lg:grid-cols-[1fr_420px] items-start">
          {/* List Card */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 space-y-4">
            {loading ? (
              <div className="py-12 text-center text-xs text-gray-500 animate-pulse">Loading email queue...</div>
            ) : queue.length === 0 ? (
              <div className="py-12 text-center text-xs text-gray-500">No brands in active email pipeline.</div>
            ) : (
              <div className="space-y-2">
                {queue.map((brand) => (
                  <div
                    key={brand.brand_key}
                    onClick={() => setSelectedBrand(brand)}
                    className={`rounded-xl border p-4 cursor-pointer transition-all duration-200 ${
                      selectedBrand?.brand_key === brand.brand_key
                        ? "border-violet-500 bg-violet-500/5 shadow-md shadow-violet-500/5"
                        : "border-white/5 bg-white/[0.01] hover:border-white/10 hover:bg-white/[0.02]"
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="text-sm font-bold text-white">{brand.brand_name}</h3>
                        <p className="text-[10px] text-gray-500 mt-0.5">{brand.contact_email || "No email"}</p>
                      </div>
                      <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${
                        brand.stage === "SEQUENCED"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : brand.stage === "REPLIED"
                          ? "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20"
                          : "bg-violet-500/10 text-violet-400 border border-violet-500/20"
                      }`}>
                        {brand.stage}
                      </span>
                    </div>

                    <div className="flex gap-4 mt-3 text-[10px] font-mono text-gray-400">
                      <div>ASIN: <span className="text-white font-bold">{brand.anchor_asin}</span></div>
                      <div>Axis: <span className="text-white font-bold">{brand.worst_axis_at_send || "—"}</span></div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Details Sidebar Panel */}
          <div className="space-y-4">
            {selectedBrand ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 space-y-6">
                <div>
                  <h3 className="text-base font-bold text-white">{selectedBrand.brand_name}</h3>
                  <p className="text-xs text-gray-500 mt-1">outreach queue info</p>
                </div>

                {/* Approve draft button */}
                {selectedBrand.stage === "EMAIL_DRAFTED" && (
                  <button
                    onClick={() => handleApprove(selectedBrand.brand_key)}
                    className="w-full py-3 rounded-xl bg-gradient-to-r from-violet-600 to-blue-600 text-white font-bold text-xs hover:shadow-xl hover:shadow-violet-500/20 transition-all flex items-center justify-center gap-2"
                  >
                    Approve AI Draft & Sequence Now
                  </button>
                )}

                {/* Conversation History thread logs */}
                {selectedBrand.conversations && selectedBrand.conversations.length > 0 && (
                  <div className="space-y-3 pt-4 border-t border-white/5">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-gray-500 block">Conversation History</span>
                    <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                      {selectedBrand.conversations.map((msg) => (
                        <div key={msg.id} className={`flex flex-col gap-1 rounded-xl p-3 text-xs leading-relaxed border ${
                          msg.direction === "outbound"
                            ? "bg-violet-950/20 border-violet-500/20 items-end"
                            : "bg-white/[0.02] border-white/5 items-start"
                        }`}>
                          <div className="flex justify-between w-full text-[10px] font-mono text-gray-500 mb-1">
                            <span>{msg.direction === "outbound" ? "Yahya" : selectedBrand.contact_first_name}</span>
                            <span>{new Date(msg.created_at).toLocaleDateString()}</span>
                          </div>
                          <p className="text-gray-300 font-sans">{msg.body}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Email Steps 5-step sequence preview */}
                {selectedBrand.email_steps && selectedBrand.email_steps.length > 0 && (
                  <div className="space-y-3 pt-4 border-t border-white/5">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-gray-500 block">5-Step Sequence Draft Preview</span>
                    <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                      {selectedBrand.email_steps.map((st) => (
                        <details key={st.id} className="rounded-xl border border-white/5 bg-white/[0.01] overflow-hidden group">
                          <summary className="px-4 py-3 text-xs font-semibold text-gray-300 group-open:text-white cursor-pointer select-none flex justify-between items-center hover:bg-white/[0.01]">
                            <span>Step {st.step_num} Draft Preview</span>
                            <span className="text-[10px] text-gray-500 font-mono">Overlap: {Math.round((st.overlap || 0) * 100)}%</span>
                          </summary>
                          <div className="px-4 py-3 border-t border-white/5 text-xs text-gray-400 space-y-2 bg-[#0c0c14]/40 leading-relaxed font-sans whitespace-pre-wrap">
                            <div className="font-bold text-white font-mono mb-1">Subj: {st.subject}</div>
                            {st.body}
                          </div>
                        </details>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.01] p-12 text-center text-xs text-gray-500">
                Select a card from the queue to view approval tools, conversation history, or preview sequence drafts.
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
