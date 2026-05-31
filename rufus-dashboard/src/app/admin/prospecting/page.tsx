"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface ProspectingTelemetry {
  avg_lqs: number;
  max_lqs: number;
  avg_ri: number;
  max_ri: number;
  avg_cqs: number;
  avg_flesch: number;
  avg_ttr: number;
  avg_cosmo: number;
  total_scored_listings: number;
  total_scored_brands: number;
  stage_counts: Record<string, number>;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AdminProspectingPage() {
  const [data, setData] = useState<ProspectingTelemetry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState<string | null>(null);
  const router = useRouter();

  const fetchTelemetry = async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/prospecting`, {
        credentials: "include",
      });
      if (res.status === 401) {
        router.push("/admin/login");
        return;
      }
      if (!res.ok) throw new Error("Failed to load prospecting telemetry");
      const d = await res.json();
      setData(d);
    } catch (err: any) {
      setError(err.message || "Failed to fetch telemetry data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
  }, []);

  const handleTrigger = async (stage: string) => {
    setTriggering(stage);
    try {
      const res = await fetch(`${API_URL}/api/admin/trigger/${stage}`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to trigger pipeline stage");
      alert(`Pipeline stage '${stage}' successfully queued for execution!`);
      await fetchTelemetry();
    } catch (err: any) {
      alert(err.message || "Pipeline trigger failed");
    } finally {
      setTriggering(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#050B14] flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-10 h-10 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mx-auto" />
          <p className="text-xs text-gray-500 font-mono tracking-widest uppercase">Loading Mission Control...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#050B14] flex items-center justify-center text-center">
        <div className="space-y-4 max-w-md p-6 rounded-2xl border border-red-500/20 bg-red-500/5">
          <p className="text-sm font-semibold text-red-400">Database/API Sync Failed</p>
          <p className="text-xs text-gray-400">{error || "Could not connect to Supabase backend API"}</p>
          <button onClick={() => window.location.reload()} className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-xs hover:bg-white/10 transition-colors">
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050B14] text-gray-100 selection:bg-cyan-500/30 selection:text-cyan-200 overflow-x-hidden relative font-sans">
      {/* Visual background glows */}
      <div className="absolute top-[-100px] left-[-100px] w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-0 right-[-100px] w-[600px] h-[600px] bg-violet-600/5 rounded-full blur-[150px] pointer-events-none" />

      {/* Nav */}
      <nav className="max-w-6xl mx-auto w-full px-6 py-5 flex items-center justify-between border-b border-white/5 relative z-10">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 via-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <span className="text-white text-xs font-black tracking-tighter">OR</span>
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-bold text-white tracking-wider uppercase">Optimus Rufus</span>
              <span className="text-[9px] text-cyan-400 font-mono tracking-widest uppercase">Admin Deck</span>
            </div>
          </div>
          <div className="flex gap-5 text-xs font-semibold text-gray-400">
            <a href="/admin/dashboard" className="hover:text-white transition-colors">Overview</a>
            <a href="/admin/assistant" className="hover:text-cyan-400 transition-colors">Assistant</a>
            <a href="/admin/prospecting" className="text-cyan-400 border-b-2 border-cyan-400 pb-1">Prospecting</a>
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

      {/* Content */}
      <main className="max-w-6xl mx-auto w-full px-6 py-12 space-y-8 relative z-10">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-white/5">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] text-emerald-400 font-mono tracking-widest uppercase">Telemetry Stream Active</span>
            </div>
            <h1 className="text-3xl font-black tracking-tight text-white">Prospecting & Mission Control Deck</h1>
            <p className="text-xs text-gray-500">Aggregating computational linguistics, Amazon Listing Integrity, and cognitive reachability indices.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => handleTrigger("full")}
              disabled={!!triggering}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 text-white text-xs font-bold hover:shadow-lg hover:shadow-cyan-500/25 transition-all disabled:opacity-30 flex items-center gap-2 border border-cyan-400/25"
            >
              {triggering === "full" && <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
              Full Prospecting Run
            </button>
          </div>
        </div>

        {/* Radial Index Gauges */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* ALII Card */}
          <div className="rounded-2xl border border-white/5 bg-[#0A1220]/50 p-6 space-y-4 hover:border-cyan-500/20 transition-all relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-500/5 rounded-full blur-2xl group-hover:bg-cyan-500/10 transition-all" />
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-cyan-400 font-mono tracking-wider uppercase">Listing Need</span>
              <span className="px-2 py-0.5 rounded-full text-[9px] font-mono bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 uppercase font-bold">ALII</span>
            </div>
            <div className="flex items-end justify-between">
              <div className="space-y-1">
                <span className="text-4xl font-black text-white">{data.avg_lqs.toFixed(1)}<span className="text-xs text-gray-500 font-normal">/100</span></span>
                <p className="text-[10px] text-gray-400">Amazon Listing Integrity Index (max: {data.max_lqs})</p>
              </div>
              <div className="w-12 h-12 rounded-full border-4 border-cyan-500/20 border-t-cyan-400 flex items-center justify-center text-[10px] font-mono text-cyan-400 animate-spin-slow">
                {Math.round(data.avg_lqs)}%
              </div>
            </div>
          </div>

          {/* CQS Card */}
          <div className="rounded-2xl border border-white/5 bg-[#0A1220]/50 p-6 space-y-4 hover:border-emerald-500/20 transition-all relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-2xl group-hover:bg-emerald-500/10 transition-all" />
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-emerald-400 font-mono tracking-wider uppercase">Brand Fit</span>
              <span className="px-2 py-0.5 rounded-full text-[9px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase font-bold">CQS</span>
            </div>
            <div className="flex items-end justify-between">
              <div className="space-y-1">
                <span className="text-4xl font-black text-white">{data.avg_cqs.toFixed(1)}<span className="text-xs text-gray-500 font-normal">/100</span></span>
                <p className="text-[10px] text-gray-400">Client Quality Score (Urgency & Budget)</p>
              </div>
              <div className="w-12 h-12 rounded-full border-4 border-emerald-500/20 border-t-emerald-400 flex items-center justify-center text-[10px] font-mono text-emerald-400">
                {Math.round(data.avg_cqs)}%
              </div>
            </div>
          </div>

          {/* RI Card */}
          <div className="rounded-2xl border border-white/5 bg-[#0A1220]/50 p-6 space-y-4 hover:border-violet-500/20 transition-all relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-32 h-32 bg-violet-500/5 rounded-full blur-2xl group-hover:bg-violet-500/10 transition-all" />
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-violet-400 font-mono tracking-wider uppercase">Prioritization</span>
              <span className="px-2 py-0.5 rounded-full text-[9px] font-mono bg-violet-500/10 text-violet-400 border border-violet-500/20 uppercase font-bold">Reachability</span>
            </div>
            <div className="flex items-end justify-between">
              <div className="space-y-1">
                <span className="text-4xl font-black text-white">{data.avg_ri.toFixed(1)}<span className="text-xs text-gray-500 font-normal">/100</span></span>
                <p className="text-[10px] text-gray-400">Geometric Reachability Index (max: {data.max_ri})</p>
              </div>
              <div className="w-12 h-12 rounded-full border-4 border-violet-500/20 border-t-violet-400 flex items-center justify-center text-[10px] font-mono text-violet-400">
                {Math.round(data.avg_ri)}%
              </div>
            </div>
          </div>
        </div>

        {/* Dual Layout Panel */}
        <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
          {/* Linguistics Panel */}
          <div className="rounded-2xl border border-white/10 bg-[#0A1220]/30 p-8 space-y-6">
            <div className="flex justify-between items-center pb-4 border-b border-white/5">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
                Computational Linguistics Diagnostics
              </h3>
              <span className="text-[10px] text-gray-500 font-mono">Sample pool: {data.total_scored_listings} ASINs</span>
            </div>

            <div className="space-y-5">
              {/* Flesch */}
              <div className="p-4 rounded-xl border border-white/5 bg-[#060C16] space-y-3">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-gray-300 font-semibold">Flesch-Kincaid Readability Ease</span>
                  <span className="font-mono text-cyan-400 font-bold">{data.avg_flesch.toFixed(1)}</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/5 overflow-hidden relative">
                  <div className="h-full rounded-full bg-cyan-400 transition-all duration-1000" style={{ width: `${Math.min(data.avg_flesch, 100)}%` }} />
                </div>
                <p className="text-[10px] text-gray-500">Target is &gt;60. Lower values indicate complex, unreadable sentence structure which actively harms conversational search models (RAG) extraction.</p>
              </div>

              {/* TTR Lexical */}
              <div className="p-4 rounded-xl border border-white/5 bg-[#060C16] space-y-3">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-gray-300 font-semibold">Lexical Density (Type-Token Ratio)</span>
                  <span className="font-mono text-cyan-400 font-bold">{(data.avg_ttr * 100).toFixed(1)}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/5 overflow-hidden relative">
                  <div className="h-full rounded-full bg-cyan-400 transition-all duration-1000" style={{ width: `${Math.min(data.avg_ttr * 100, 100)}%` }} />
                </div>
                <p className="text-[10px] text-gray-500">Target is &gt;50%. Lower values indicate ad-stuffed, repetitive keyword copywriting that search engines flag as keyword spamming.</p>
              </div>

              {/* COSMO Preposition */}
              <div className="p-4 rounded-xl border border-white/5 bg-[#060C16] space-y-3">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-gray-300 font-semibold">COSMO Prepositional Relation Density</span>
                  <span className="font-mono text-cyan-400 font-bold">{data.avg_cosmo.toFixed(2)}/100w</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/5 overflow-hidden relative">
                  <div className="h-full rounded-full bg-cyan-400 transition-all duration-1000" style={{ width: `${Math.min(data.avg_cosmo * 20, 100)}%` }} />
                </div>
                <p className="text-[10px] text-gray-500">Target is &gt;3.5/100w. Calculates functional relation keywords (*for, with, in, on, during*) mapping to user intention node queries.</p>
              </div>
            </div>
          </div>

          {/* Controls and Pipelines Counts */}
          <div className="space-y-6">
            {/* Pipeline Stage Counts */}
            <div className="rounded-2xl border border-white/10 bg-[#0A1220]/30 p-6 space-y-4">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-2">Stage Breakdown</h3>
              <div className="space-y-2.5 max-h-[280px] overflow-y-auto pr-2">
                {[
                  { stage: "LISTING_FOUND", label: "Found Listings" },
                  { stage: "WEAK_LISTING", label: "Weak Listings" },
                  { stage: "WEAK_BRAND", label: "Weak Brands" },
                  { stage: "CONTACT_ENRICHED", label: "Enriched Contacts" },
                  { stage: "EMAIL_DRAFTED", label: "Drafted Send Queue" },
                  { stage: "SEQUENCED", label: "Active Sequences" },
                ].map((item) => {
                  const count = data.stage_counts[item.stage] || 0;
                  return (
                    <div key={item.stage} className="flex justify-between items-center text-xs pb-1.5 border-b border-white/[0.02]">
                      <span className="text-gray-400">{item.label}</span>
                      <span className="font-mono text-white font-bold">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Quick Trigger Control Board */}
            <div className="rounded-2xl border border-white/10 bg-[#0A1220]/30 p-6 space-y-4">
              <div>
                <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-1">Queue Control Panel</h3>
                <p className="text-[10px] text-gray-500 font-mono">Execute background prospecting routines.</p>
              </div>
              <div className="space-y-2">
                {[
                  { stage: "enrich", label: "Run Lead Enrichment Sync" },
                  { stage: "score", label: "Compute Listing Quality Metrics" },
                  { stage: "draft", label: "Draft Cold Outreach Templates" },
                  { stage: "sequence", label: "Activate Outbound Enrollment" },
                ].map((act) => (
                  <button
                    key={act.stage}
                    onClick={() => handleTrigger(act.stage)}
                    disabled={!!triggering}
                    className="w-full text-left px-3.5 py-2.5 rounded-xl border border-white/5 hover:border-cyan-500/20 bg-white/[0.01] hover:bg-cyan-500/[0.02] text-xs font-semibold text-gray-400 hover:text-white flex items-center justify-between transition-all"
                  >
                    {act.label}
                    {triggering === act.stage ? (
                      <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      <span className="text-[9px] text-cyan-500 font-bold uppercase tracking-wider font-mono">Queue</span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
