"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface Brand {
  brand_key: string;
  brand_name: string;
  stage: string;
  category: string | null;
  anchor_asin: string | null;
  asin_count: number;
  contact_email: string | null;
  contact_first_name: string | null;
  contact_title: string | null;
  rufus_score?: number | null;
  citation_probability?: string | null;
  reachability_index: number;
  landing_page_views: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STAGES = [
  "LISTING_FOUND", "WEAK_LISTING", "WEAK_BRAND", "BRAND_RESOLVED",
  "CONTACT_ENRICHED", "EMAIL_DRAFTED", "SEQUENCED", "REPLIED",
  "DEMO_SCHEDULED", "MEETING_BOOKED", "SKIP",
];

export default function AdminProspectsPage() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState("");
  const [sortBy, setSortBy] = useState("updated_at");
  const [order, setOrder] = useState("desc");
  const [limit] = useState(25);
  const [offset, setOffset] = useState(0);
  
  const [selectedBrand, setSelectedBrand] = useState<Brand | null>(null);
  const [noteText, setNoteText] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const router = useRouter();

  const fetchProspects = async () => {
    setLoading(true);
    try {
      let url = `${API_URL}/api/admin/prospects?limit=${limit}&offset=${offset}&sort_by=${sortBy}&order=${order}`;
      if (search) url += `&search=${encodeURIComponent(search)}`;
      if (stage) url += `&stage=${encodeURIComponent(stage)}`;

      const res = await fetch(url, {
        credentials: "include",
      });
      if (res.status === 401) {
        router.push("/admin/login");
        return;
      }
      if (!res.ok) throw new Error("Failed to load prospects");
      const data = await res.json();
      setBrands(data.brands || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProspects();
  }, [stage, sortBy, order, offset]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setOffset(0);
    fetchProspects();
  };

  const handleAction = async (brandKey: string, action: string, value?: string) => {
    setActionLoading(brandKey);
    try {
      const res = await fetch(`${API_URL}/api/admin/prospects/${brandKey}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, value }),
        credentials: "include",
      });

      if (!res.ok) throw new Error("Action execution failed");
      const resData = await res.json();

      // Refresh list or update selected
      fetchProspects();
      
      if (selectedBrand && selectedBrand.brand_key === brandKey) {
        if (action === "add_note") {
          setSelectedBrand({ ...selectedBrand, notes: resData.notes });
          setNoteText("");
        } else if (action === "set_stage" || action === "advance" || action === "skip") {
          setSelectedBrand({ ...selectedBrand, stage: resData.new_stage });
        }
      }
    } catch (err: any) {
      alert(err.message || "Failed to perform action");
    } finally {
      setActionLoading(null);
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
            <a href="/admin/prospects" className="text-violet-400 font-bold">Prospects</a>
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
      <main className="max-w-6xl mx-auto w-full px-6 py-12 space-y-8 relative z-10">
        {/* Title */}
        <div>
          <h1 className="text-2xl font-black text-white">Prospect Pipeline Management</h1>
          <p className="text-xs text-gray-500 mt-1">Audit, edit notes, manually override status stages, or regenerate sequences for individual brands.</p>
        </div>

        {/* Filters */}
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
          <form onSubmit={handleSearchSubmit} className="grid md:grid-cols-4 gap-4 items-end">
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold uppercase tracking-widest text-gray-500">Search</label>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search brand, email..."
                className="w-full rounded-xl bg-white/5 border border-white/10 px-3.5 py-2.5 text-xs focus:outline-none focus:border-violet-500/50"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold uppercase tracking-widest text-gray-500">Pipeline Stage</label>
              <select
                value={stage}
                onChange={(e) => { setStage(e.target.value); setOffset(0); }}
                className="w-full rounded-xl bg-white/5 border border-white/10 px-3.5 py-2.5 text-xs text-gray-300 focus:outline-none focus:border-violet-500/50"
              >
                <option value="">All Stages</option>
                {STAGES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[9px] font-bold uppercase tracking-widest text-gray-500">Sort By</label>
              <select
                value={`${sortBy}:${order}`}
                onChange={(e) => {
                  const [field, dir] = e.target.value.split(":");
                  setSortBy(field);
                  setOrder(dir);
                  setOffset(0);
                }}
                className="w-full rounded-xl bg-white/5 border border-white/10 px-3.5 py-2.5 text-xs text-gray-300 focus:outline-none focus:border-violet-500/50"
              >
                <option value="updated_at:desc">Recently Updated (Newest)</option>
                <option value="reachability_index:desc">Highest Reachability</option>
                <option value="client_quality_score:desc">Highest Quality Score</option>
                <option value="landing_page_views:desc">Most Landing views</option>
              </select>
            </div>

            <button type="submit" className="py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-bold text-xs transition-colors">
              Filter List
            </button>
          </form>
        </div>

        {/* Layout Grid */}
        <div className="grid gap-6 lg:grid-cols-[1fr_380px] items-start">
          {/* List Card */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 space-y-4">
            {loading ? (
              <div className="py-12 text-center text-xs text-gray-500 animate-pulse">Loading prospects catalog...</div>
            ) : brands.length === 0 ? (
              <div className="py-12 text-center text-xs text-gray-500">No prospects match the filter parameters.</div>
            ) : (
              <div className="space-y-2">
                {brands.map((brand) => (
                  <div
                    key={brand.brand_key}
                    onClick={() => { setSelectedBrand(brand); setNoteText(""); }}
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
                        brand.stage === "MEETING_BOOKED" || brand.stage === "DEMO_SCHEDULED"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : brand.stage === "SKIP"
                          ? "bg-red-500/10 text-red-400 border border-red-500/20"
                          : "bg-white/5 text-gray-400"
                      }`}>
                        {brand.stage}
                      </span>
                    </div>
                    
                    <div className="flex gap-4 mt-3 text-[10px] font-mono text-gray-400">
                      <div>Score: <span className="text-white font-bold">{brand.rufus_score ?? "—"}</span></div>
                      <div>Reachability: <span className="text-white font-bold">{brand.reachability_index}</span></div>
                      <div>Views: <span className="text-white font-bold">{brand.landing_page_views}</span></div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Pagination */}
            {total > limit && (
              <div className="flex justify-between items-center text-xs text-gray-500 font-mono mt-4 pt-4 border-t border-white/5">
                <button
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  className="px-3 py-1.5 rounded-lg bg-white/5 disabled:opacity-30"
                >
                  Prev
                </button>
                <span>{offset + 1}-{Math.min(offset + limit, total)} of {total}</span>
                <button
                  disabled={offset + limit >= total}
                  onClick={() => setOffset(offset + limit)}
                  className="px-3 py-1.5 rounded-lg bg-white/5 disabled:opacity-30"
                >
                  Next
                </button>
              </div>
            )}
          </div>

          {/* Details Sidebar Panel */}
          <div className="space-y-4">
            {selectedBrand ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 space-y-6">
                <div>
                  <h3 className="text-base font-bold text-white">{selectedBrand.brand_name}</h3>
                  <p className="text-xs text-gray-500 mt-1">Anchor ASIN: {selectedBrand.anchor_asin}</p>
                </div>

                {/* Info block */}
                <div className="rounded-xl bg-white/[0.02] border border-white/5 p-4 space-y-3 text-xs">
                  <div>
                    <span className="text-gray-500 font-medium">Contact:</span>{" "}
                    <span className="text-white">
                      {selectedBrand.contact_first_name || "N/A"} ({selectedBrand.contact_title || "Founder"})
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 font-medium">Email:</span>{" "}
                    <span className="text-white font-mono">{selectedBrand.contact_email || "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 font-medium">Rufus Citation:</span>{" "}
                    <span className="text-white font-mono font-bold uppercase">{selectedBrand.citation_probability || "N/A"}</span>
                  </div>
                </div>

                {/* Overrides / Transitions */}
                <div className="space-y-2">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-gray-500 block">Actions</span>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => handleAction(selectedBrand.brand_key, "advance")}
                      disabled={actionLoading === selectedBrand.brand_key}
                      className="py-2.5 rounded-xl border border-white/5 hover:border-white/15 bg-white/[0.02] text-xs font-semibold text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Advance Stage
                    </button>
                    <button
                      onClick={() => handleAction(selectedBrand.brand_key, "skip")}
                      disabled={actionLoading === selectedBrand.brand_key}
                      className="py-2.5 rounded-xl border border-red-500/20 bg-red-500/5 hover:bg-red-500/10 text-xs font-semibold text-red-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Skip Brand
                    </button>
                  </div>
                  <button
                    onClick={() => handleAction(selectedBrand.brand_key, "regenerate_email")}
                    disabled={actionLoading === selectedBrand.brand_key}
                    className="w-full py-2.5 rounded-xl border border-violet-500/20 bg-violet-500/5 text-xs font-semibold text-violet-400 hover:bg-violet-500/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Regenerate Email Sequence
                  </button>
                </div>

                {/* Custom Transition override dropdown */}
                <div className="space-y-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-gray-500 block">Force State Override</span>
                  <select
                    value={selectedBrand.stage}
                    onChange={(e) => handleAction(selectedBrand.brand_key, "set_stage", e.target.value)}
                    className="w-full rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-xs focus:outline-none focus:border-violet-500/50 text-gray-300"
                  >
                    {STAGES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>

                {/* Notes Block */}
                <div className="space-y-3 pt-4 border-t border-white/5">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-gray-500 block">Notes & Activity Logs</span>
                  <div className="rounded-xl bg-white/[0.01] border border-white/5 p-3 h-36 overflow-y-auto font-mono text-[10px] text-gray-400 leading-relaxed whitespace-pre-wrap">
                    {selectedBrand.notes || "No logs recorded for this brand."}
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={noteText}
                      onChange={(e) => setNoteText(e.target.value)}
                      placeholder="Add manual log..."
                      className="flex-1 rounded-xl bg-white/5 border border-white/10 px-3.5 py-2 text-xs focus:outline-none focus:border-violet-500/50"
                      onKeyDown={(e) => e.key === "Enter" && noteText.trim() && handleAction(selectedBrand.brand_key, "add_note", noteText.trim())}
                    />
                    <button
                      onClick={() => noteText.trim() && handleAction(selectedBrand.brand_key, "add_note", noteText.trim())}
                      disabled={actionLoading === selectedBrand.brand_key}
                      className="px-4 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-bold text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Save
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.01] p-12 text-center text-xs text-gray-500">
                Select a prospect card from the list to manage transitions, view listing insights, and edit notes.
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
