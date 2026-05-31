"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface Settings {
  openrouter_model: string;
  openrouter_draft_model: string;
  max_llm_concurrency: string;
  max_apollo_concurrency: string;
  email_mini_batch_size: string;
  calendly_url: string;
  landing_page_base_url: string;
  auto_send_enabled: string;
  auto_reply_enabled: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const router = useRouter();

  const fetchSettings = async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/settings`, {
        credentials: "include",
      });
      if (res.status === 401) {
        router.push("/admin/login");
        return;
      }
      if (!res.ok) throw new Error("Failed to load settings");
      const data = await res.json();
      setSettings(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleSaveSetting = async (key: string, value: string) => {
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, value }),
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to update setting");
      
      // Update local state
      if (settings) {
        setSettings({ ...settings, [key]: value });
      }
      alert(`Setting '${key}' updated successfully!`);
    } catch (err: any) {
      alert(err.message || "Failed to save setting");
    } finally {
      setSaving(false);
    }
  };

  if (loading || !settings) {
    return (
      <div className="min-h-screen bg-[#06060c] flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-10 h-10 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin mx-auto" />
          <p className="text-xs text-gray-500">Loading settings...</p>
        </div>
      </div>
    );
  }

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
            <a href="/admin/emails" className="hover:text-white transition-colors">Emails Queue</a>
            <a href="/admin/settings" className="text-violet-400 font-bold">Settings</a>
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
      <main className="max-w-3xl mx-auto w-full px-6 py-12 space-y-8 relative z-10">
        {/* Title */}
        <div>
          <h1 className="text-2xl font-black text-white">System Configuration</h1>
          <p className="text-xs text-gray-500 mt-1">Configure models, integration booking hooks, landing domains, and sequence triggers.</p>
        </div>

        {/* Form container */}
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 space-y-8">
          {/* Section: LLM Model Configurations */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-widest text-violet-400">Large Language Models (LLM)</h3>
            
            <div className="space-y-3">
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between">
                  <label className="text-xs font-semibold text-white">Primary Pipeline Model</label>
                  <span className="text-[10px] text-gray-500 font-mono">OPENROUTER_MODEL</span>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    defaultValue={settings.openrouter_model}
                    onBlur={(e) => handleSaveSetting("openrouter_model", e.target.value)}
                    className="flex-1 rounded-xl bg-white/5 border border-white/10 px-4 py-2.5 text-xs focus:outline-none focus:border-violet-500/50 font-mono text-gray-300"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between">
                  <label className="text-xs font-semibold text-white">Email Reply Draft Model</label>
                  <span className="text-[10px] text-gray-500 font-mono">OPENROUTER_DRAFT_MODEL</span>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    defaultValue={settings.openrouter_draft_model}
                    onBlur={(e) => handleSaveSetting("openrouter_draft_model", e.target.value)}
                    className="flex-1 rounded-xl bg-white/5 border border-white/10 px-4 py-2.5 text-xs focus:outline-none focus:border-violet-500/50 font-mono text-gray-300"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Section: Integration Settings */}
          <div className="space-y-4 pt-6 border-t border-white/5">
            <h3 className="text-xs font-bold uppercase tracking-widest text-violet-400">Integrations & Hooks</h3>
            
            <div className="space-y-3">
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between">
                  <label className="text-xs font-semibold text-white">Calendly Meeting Booking Link</label>
                  <span className="text-[10px] text-gray-500 font-mono">CALENDLY_URL</span>
                </div>
                <input
                  type="text"
                  defaultValue={settings.calendly_url}
                  onBlur={(e) => handleSaveSetting("calendly_url", e.target.value)}
                  placeholder="https://calendly.com/username/meeting-slug"
                  className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-2.5 text-xs focus:outline-none focus:border-violet-500/50 text-gray-300"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between">
                  <label className="text-xs font-semibold text-white">Landing Page Base URL</label>
                  <span className="text-[10px] text-gray-500 font-mono">LANDING_PAGE_BASE_URL</span>
                </div>
                <input
                  type="text"
                  defaultValue={settings.landing_page_base_url}
                  onBlur={(e) => handleSaveSetting("landing_page_base_url", e.target.value)}
                  placeholder="https://audit.optimusrufus.com"
                  className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-2.5 text-xs focus:outline-none focus:border-violet-500/50 text-gray-300"
                />
              </div>
            </div>
          </div>

          {/* Section: Automation Controls */}
          <div className="space-y-4 pt-6 border-t border-white/5">
            <h3 className="text-xs font-bold uppercase tracking-widest text-violet-400">Outbound Automations</h3>
            
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <div>
                  <h4 className="text-xs font-bold text-white">Autonomous Reply Dispatching</h4>
                  <p className="text-[10px] text-gray-500 mt-0.5">Let AI objection handling send reply drafts directly back to the inbox thread without manual confirmation.</p>
                </div>
                <input
                  type="checkbox"
                  defaultChecked={settings.auto_reply_enabled === "true"}
                  onChange={(e) => handleSaveSetting("auto_reply_enabled", e.target.checked ? "true" : "false")}
                  className="w-4 h-4 text-violet-600 bg-white/5 border-white/10 rounded focus:ring-violet-500"
                />
              </div>

              <div className="flex justify-between items-center">
                <div>
                  <h4 className="text-xs font-bold text-white">Autonomous Cold-Outreach Sequences</h4>
                  <p className="text-[10px] text-gray-500 mt-0.5">Directly upload completed AI cold sequence drafts straight to active Apollo outbound pipelines upon daily cron completion.</p>
                </div>
                <input
                  type="checkbox"
                  defaultChecked={settings.auto_send_enabled === "true"}
                  onChange={(e) => handleSaveSetting("auto_send_enabled", e.target.checked ? "true" : "false")}
                  className="w-4 h-4 text-violet-600 bg-[#06060c] border border-white/10 rounded"
                />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
