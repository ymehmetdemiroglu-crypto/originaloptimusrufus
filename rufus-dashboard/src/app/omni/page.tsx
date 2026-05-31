"use client";

import React, { useEffect, useState } from "react";
import { Orbit, Search, Zap, BarChart3, Target, Mail, Activity } from "lucide-react";
import { PageHeader } from "@/components/dashboard/page-header";
import { MetricCard } from "@/components/dashboard/metric-card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { OmniWorkspaceProvider, useOmniWorkspace } from "@/components/omni/workspace-context";
import { AgentChatPanel } from "@/components/omni/agent-chat";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const AGENT_ICONS: Record<string, React.ReactNode> = {
  listing: <Target className="h-4 w-4" />,
  competitor: <BarChart3 className="h-4 w-4" />,
  attribution: <Activity className="h-4 w-4" />,
  outreach: <Mail className="h-4 w-4" />,
  email: <Mail className="h-4 w-4" />,
  admin: <Zap className="h-4 w-4" />,
};

function OmniDashboardInner() {
  const { workspace, setAsin } = useOmniWorkspace();
  const [asinInput, setAsinInput] = useState(workspace.asin || "");
  const [overview, setOverview] = useState<any>(null);
  const [agentsStatus, setAgentsStatus] = useState<any[]>([]);

  useEffect(() => {
    api.overview().then(setOverview).catch(() => null);
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/omni/agents`)
      .then((r) => r.json())
      .then((d) => setAgentsStatus(d.agents || []))
      .catch(() => null);
  }, []);

  const handleSetAsin = () => {
    if (asinInput.trim()) {
      setAsin(asinInput.trim().toUpperCase());
    }
  };

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* Main Canvas */}
      <div className="flex-1 overflow-y-auto p-6">
        <PageHeader
          title="Omni-Dashboard"
          description="Unified command center for the Optimus Rufus Multi-Agent System."
        />

        {/* Workspace Bar */}
        <div className="mt-6 flex items-center gap-3 rounded-lg border border-[#E0E1DD]/10 bg-white/[0.02] p-4">
          <div className="flex items-center gap-2 text-[#00F5FF]">
            <Orbit className="h-5 w-5" />
            <span className="text-xs font-display uppercase tracking-wider">Workspace</span>
          </div>
          <div className="flex flex-1 items-center gap-2">
            <Input
              value={asinInput}
              onChange={(e) => setAsinInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSetAsin()}
              placeholder="Enter ASIN (e.g., B08N5WRWNW)"
              className="h-9 max-w-xs border-[#E0E1DD]/10 bg-white/[0.03] text-xs text-white placeholder:text-[#E0E1DD]/40 focus-visible:ring-[#00F5FF]/30"
            />
            <Button
              size="sm"
              onClick={handleSetAsin}
              className="h-9 bg-[#00F5FF]/10 text-[#00F5FF] hover:bg-[#00F5FF]/20"
            >
              <Search className="mr-1.5 h-3.5 w-3.5" />
              Set Target
            </Button>
          </div>
          {workspace.asin && (
            <Badge
              variant="outline"
              className="border-[#00F5FF]/30 bg-[#00F5FF]/5 text-[#00F5FF]"
            >
              {workspace.asin}
            </Badge>
          )}
          {workspace.isStreaming && (
            <Badge
              variant="outline"
              className="animate-pulse border-amber-500/30 bg-amber-500/5 text-amber-300"
            >
              Streaming...
            </Badge>
          )}
        </div>

        {/* Agent Status Grid */}
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agentsStatus.map((agent) => {
            const isActive = workspace.activeAgents.includes(agent.id);
            return (
              <div
                key={agent.id}
                className={cn(
                  "group relative rounded-lg border p-4 transition-colors",
                  isActive
                    ? "border-[#00F5FF]/30 bg-[#00F5FF]/5"
                    : "border-[#E0E1DD]/10 bg-white/[0.02] hover:bg-white/[0.03]"
                )}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-md",
                      isActive ? "bg-[#00F5FF]/10 text-[#00F5FF]" : "bg-white/5 text-[#E0E1DD]/60"
                    )}
                  >
                    {AGENT_ICONS[agent.id] || <Zap className="h-4 w-4" />}
                  </div>
                  <div>
                    <div className="text-xs font-medium text-white">{agent.name}</div>
                    <div className="text-[10px] text-[#E0E1DD]/50">{agent.description}</div>
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <div
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      agent.status === "healthy" ? "bg-green-400" : "bg-red-400"
                    )}
                  />
                  <span className="text-[10px] uppercase tracking-wider text-[#E0E1DD]/50">
                    {agent.status}
                  </span>
                  {isActive && (
                    <span className="ml-auto text-[10px] text-[#00F5FF]">Running</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Contextual Metrics */}
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="COSMO Readiness"
            value={overview?.cosmo_readiness_score ? `${overview.cosmo_readiness_score}` : "—"}
            subtitle="Weighted semantic coverage"
          />
          <MetricCard
            title="Active Listings"
            value={overview?.active_listings ?? "—"}
            subtitle="In-flight optimizations"
          />
          <MetricCard
            title="Competitor Similarity"
            value={
              overview?.competitor_similarity ? `${(overview.competitor_similarity * 100).toFixed(1)}%` : "—"
            }
            subtitle="Vector embedding distance"
          />
          <MetricCard
            title="Gap Alerts"
            value={overview?.gap_alerts ?? "—"}
            subtitle="Actionable opportunities"
          />
        </div>

        {/* Quick Actions */}
        <div className="mt-6">
          <h3 className="text-xs font-display uppercase tracking-wider text-[#E0E1DD]/60">
            Quick Intents
          </h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {[
              "Analyze ASIN",
              "Compare competitors",
              "Project revenue impact",
              "Draft outreach email",
              "Run full optimization",
              "Show pipeline status",
            ].map((intent) => (
              <button
                key={intent}
                className="rounded-full border border-[#E0E1DD]/10 bg-white/[0.02] px-3 py-1.5 text-[11px] text-[#E0E1DD]/70 transition-colors hover:border-[#00F5FF]/30 hover:text-[#00F5FF]"
              >
                {intent}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Agent Chat Sidebar */}
      <div className="w-[380px] shrink-0">
        <AgentChatPanel />
      </div>
    </div>
  );
}

export default function OmniDashboardPage() {
  return (
    <OmniWorkspaceProvider>
      <OmniDashboardInner />
    </OmniWorkspaceProvider>
  );
}
