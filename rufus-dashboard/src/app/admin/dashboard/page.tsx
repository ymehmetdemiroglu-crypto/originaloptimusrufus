"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface DashboardData {
  total_brands: number;
  total_prospects: number;
  stage_counts: Record<string, number>;
  funnel: {
    prospected: number;
    enriched: number;
    emailed: number;
    replied: number;
    booked: number;
  };
  landing_page_views_7d: number;
  meetings_booked: number;
  recent_activity: Array<{
    brand_key: string;
    brand_name: string;
    stage: string;
    contact_email: string | null;
    updated_at: string;
  }>;
  email_stats: {
    drafted: number;
    sequenced: number;
    replied: number;
  };
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AdminDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState<string | null>(null);
  const router = useRouter();

  const fetchDashboardData = async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/dashboard`, {
        credentials: "include",
      });
      if (res.status === 401) {
        router.push("/admin/login");
        return;
      }
      if (!res.ok) throw new Error("Failed to load dashboard data");
      const d = await res.json();
      setData(d);
    } catch (err: any) {
      setError(err.message || "Failed to load admin dashboard.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const handleTrigger = async (stage: string) => {
    setTriggering(stage);
    try {
      const res = await fetch(`${API_URL}/api/admin/trigger/${stage}`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to trigger pipeline");
      alert(`Pipeline stage '${stage}' successfully queued for execution!`);
    } catch (err: any) {
      alert(err.message || "Pipeline trigger failed");
    } finally {
      setTriggering(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#06060c] flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-10 h-10 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin mx-auto" />
          <p className="text-xs text-gray-500">Loading admin panel...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#06060c] flex items-center justify-center text-center">
        <div className="space-y-4">
          <p className="text-sm text-red-400">Error: {error}</p>
          <button onClick={() => window.location.reload()} className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-xs">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#06060c] text-gray-100 selection:bg-violet-500/30 selection:text-violet-200">
      {/* Background Orbs */}
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
            <a href="/admin/dashboard" className="text-violet-400 font-bold">Overview</a>
            <a href="/admin/assistant" className="hover:text-cyan-400 transition-colors">Assistant</a>
            <a href="/admin/prospecting" className="hover:text-cyan-400 transition-colors">Prospecting</a>
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
          className="text-xs text-gray-500 hover:text-white transition-colors"
        >
          Sign Out
        </button>
      </nav>

      {/* Content */}
      <main className="max-w-6xl mx-auto w-full px-6 py-12 space-y-10 relative z-10">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black text-white">Optimus Rufus Pipeline Control</h1>
            <p className="text-xs text-gray-500 mt-1">Real-time status monitoring, manual triggers, and outreach validation</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => handleTrigger("full")}
              disabled={!!triggering}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-blue-600 text-white text-xs font-bold hover:shadow-lg hover:shadow-violet-500/25 transition-all disabled:opacity-30 flex items-center gap-2"
            >
              {triggering === "full" && <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
              Trigger Full Pipeline Run
            </button>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Total Brands Scraped", value: data.total_brands },
            { label: "Total ASIN Prospects", value: data.total_prospects },
            { label: "Landing views (7d)", value: data.landing_page_views_7d },
            { label: "Meetings Booked", value: data.meetings_booked },
          ].map((stat) => (
            <div key={stat.label} className="rounded-2xl border border-white/5 bg-white/[0.01] p-6 space-y-1 hover:border-white/10 transition-colors">
              <span className="text-[10px] text-gray-500 uppercase tracking-widest font-bold block">{stat.label}</span>
              <span className="text-3xl font-black text-white block">{stat.value}</span>
            </div>
          ))}
        </div>

        {/* Funnel & Trigger Actions row */}
        <div className="grid gap-6 lg:grid-cols-[1fr_350px]">
          {/* Funnel Stage Card */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 space-y-6">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Outreach Conversion Funnel</h3>
            <div className="space-y-4">
              {[
                { stage: "Scraped Prospect Brands", count: data.funnel.prospected, pct: 100, color: "bg-gray-500" },
                { stage: "Enriched Contacts", count: data.funnel.enriched, pct: Math.min((data.funnel.enriched / (data.funnel.prospected || 1)) * 100, 100), color: "bg-blue-500" },
                { stage: "AI Sequence Drafted", count: data.funnel.emailed, pct: Math.min((data.funnel.emailed / (data.funnel.prospected || 1)) * 100, 100), color: "bg-indigo-500" },
                { stage: "Prospect Replied", count: data.funnel.replied, pct: Math.min((data.funnel.replied / (data.funnel.prospected || 1)) * 100, 100), color: "bg-yellow-500" },
                { stage: "Demo Meeting Booked", count: data.funnel.booked, pct: Math.min((data.funnel.booked / (data.funnel.prospected || 1)) * 100, 100), color: "bg-emerald-500" },
              ].map((item) => (
                <div key={item.stage} className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-300 font-medium">{item.stage}</span>
                    <span className="font-mono text-gray-500">{item.count} ({Math.round(item.pct)}%)</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                    <div className={`h-full rounded-full transition-all duration-1000 ${item.color}`} style={{ width: `${item.pct}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Trigger Stages Card */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 space-y-5 flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-2">Outreach Pipeline Controls</h3>
              <p className="text-xs text-gray-500">Force queue background stages manually without waiting for cron schedule.</p>
            </div>
            <div className="space-y-2">
              {[
                { stage: "enrich", label: "Trigger Enrichment Sync" },
                { stage: "score", label: "Analyze Rufus Listing Scores" },
                { stage: "draft", label: "Draft AI Sequences" },
                { stage: "sequence", label: "Push to Outbound campaigns" },
              ].map((act) => (
                <button
                  key={act.stage}
                  onClick={() => handleTrigger(act.stage)}
                  disabled={!!triggering}
                  className="w-full text-left px-4 py-3 rounded-xl border border-white/5 hover:border-white/15 bg-white/[0.01] hover:bg-white/[0.02] text-xs font-semibold text-gray-300 hover:text-white flex items-center justify-between transition-all"
                >
                  {act.label}
                  {triggering === act.stage ? (
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <span className="text-[10px] text-gray-600 font-bold uppercase tracking-wider">Queue</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Recent Activity Table */}
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-6">Recent pipeline events</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/5 text-[10px] text-gray-500 uppercase tracking-widest font-bold">
                  <th className="pb-3">Brand Name</th>
                  <th className="pb-3">Contact info</th>
                  <th className="pb-3">Current Pipeline stage</th>
                  <th className="pb-3 text-right">Last Update</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-xs text-gray-300">
                {data.recent_activity.map((brand) => (
                  <tr key={brand.brand_key} className="hover:bg-white/[0.01] transition-colors">
                    <td className="py-4 font-semibold text-white">{brand.brand_name}</td>
                    <td className="py-4 text-gray-400 font-mono">{brand.contact_email || "N/A"}</td>
                    <td className="py-4">
                      <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${
                        brand.stage === "MEETING_BOOKED" || brand.stage === "DEMO_SCHEDULED"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : brand.stage === "SKIP"
                          ? "bg-red-500/10 text-red-400 border border-red-500/20"
                          : brand.stage === "EMAIL_DRAFTED"
                          ? "bg-violet-500/10 text-violet-400 border border-violet-500/20"
                          : "bg-white/5 text-gray-400 border border-white/5"
                      }`}>
                        {brand.stage}
                      </span>
                    </td>
                    <td className="py-4 text-right text-gray-500 font-mono">
                      {new Date(brand.updated_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
