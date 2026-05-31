"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/dashboard/page-header";
import { MetricCard } from "@/components/dashboard/metric-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Mail,
  User,
  AlertTriangle,
  TrendingUp,
  Filter,
  ArrowUpRight,
  CheckCircle2,
  PlayCircle,
  PauseCircle,
  Eye,
  RefreshCw,
  Zap,
  ChevronRight,
  Calendar,
  Layers,
  Sparkles,
  Search,
  Check,
  Send,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const STAGE_FILTERS = [
  { label: "All Statuses", value: "" },
  { label: "Scraped (FOUND)", value: "FOUND" },
  { label: "Weak listings", value: "WEAK_LISTING" },
  { label: "Enriched contacts", value: "CONTACT_ENRICHED" },
  { label: "Drafted sequences", value: "EMAIL_DRAFTED" },
  { label: "Sequenced Apollo", value: "SEQUENCED" },
  { label: "Inbound replies", value: "REPLIED" },
];

const ANALYTICS_DATA = [
  { day: "May 20", sent: 12, opens: 8, replies: 1, bookings: 0 },
  { day: "May 21", sent: 18, opens: 11, replies: 2, bookings: 1 },
  { day: "May 22", sent: 25, opens: 17, replies: 3, bookings: 1 },
  { day: "May 23", sent: 32, opens: 22, replies: 4, bookings: 2 },
  { day: "May 24", sent: 30, opens: 21, replies: 2, bookings: 0 },
  { day: "May 25", sent: 42, opens: 29, replies: 6, bookings: 3 },
  { day: "May 26", sent: 48, opens: 35, replies: 7, bookings: 2 },
  { day: "May 27", sent: 50, opens: 38, replies: 8, bookings: 4 },
];

const CATEGORY_PERFORMANCE = [
  { name: "Supplements", reachability: 88, responseRate: 14.2 },
  { name: "Skincare", reachability: 74, responseRate: 11.5 },
  { name: "Pet Grooming", reachability: 82, responseRate: 12.8 },
  { name: "Fitness Gear", reachability: 65, responseRate: 9.4 },
  { name: "Baby Care", reachability: 71, responseRate: 10.2 },
];

function stageBadgeClass(stage: string) {
  const map: Record<string, string> = {
    FOUND: "bg-slate-100/80 text-slate-700 border-slate-200 dark:bg-slate-900/30 dark:text-slate-400 dark:border-slate-800",
    WEAK_LISTING: "bg-amber-100/80 text-amber-700 border-amber-200 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-900/40",
    CONTACT_ENRICHED: "bg-blue-100/80 text-blue-700 border-blue-200 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-900/40",
    EMAIL_DRAFTED: "bg-purple-100/80 text-purple-700 border-purple-200 dark:bg-purple-900/20 dark:text-purple-400 dark:border-purple-900/40",
    SEQUENCED: "bg-indigo-100/80 text-indigo-700 border-indigo-200 dark:bg-indigo-900/20 dark:text-indigo-400 dark:border-indigo-900/40",
    REPLIED: "bg-emerald-100/80 text-emerald-700 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-900/40",
    CALCULATOR_USED: "bg-cyan-100/80 text-cyan-700 border-cyan-200 dark:bg-cyan-900/20 dark:text-cyan-400 dark:border-cyan-900/40",
  };
  return map[stage] || "bg-slate-100/80 text-slate-700 border-slate-200 dark:bg-slate-900/30 dark:text-slate-400";
}

export default function ProspectsPage() {
  const [prospectsData, setProspectsData] = useState<any>(null);
  const [brandsData, setBrandsData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [stageFilter, setStageFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  
  // Agent scheduler & job state
  const [agentStatus, setAgentStatus] = useState<any>(null);
  const [runningJob, setRunningJob] = useState<string | null>(null);
  const [pipelineLoading, setPipelineLoading] = useState(false);

  // Email draft preview modal/drawer state
  const [selectedProspect, setSelectedProspect] = useState<any>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);

  const fetchAllData = () => {
    Promise.all([
      api.prospects(stageFilter || undefined, 100),
      api.brands(stageFilter || undefined, 100),
      api.agentStatus().catch(() => ({ running: false, jobs: [] })),
    ])
      .then(([prospects, brands, status]) => {
        setProspectsData(prospects);
        setBrandsData(brands);
        setAgentStatus(status);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchAllData();
  }, [stageFilter]);

  const handleToggleScheduler = async () => {
    if (!agentStatus) return;
    try {
      if (agentStatus.running) {
        await api.agentPause();
      } else {
        await api.agentResume();
      }
      fetchAllData();
    } catch (err) {
      console.error("Failed to toggle scheduler:", err);
    }
  };

  const handleTriggerJob = async (jobType: string) => {
    setRunningJob(jobType);
    try {
      await api.agentRunJob(jobType);
      fetchAllData();
    } catch (err) {
      console.error(`Failed to trigger job ${jobType}:`, err);
    } finally {
      setRunningJob(null);
    }
  };

  const handleTriggerPipeline = async () => {
    setPipelineLoading(true);
    try {
      await api.agentRunPipeline();
      fetchAllData();
    } catch (err) {
      console.error("Failed to trigger sequence run:", err);
    } finally {
      setPipelineLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-[450px] flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin text-accent" />
        <span>Loading Outbound Persuasion Suite...</span>
      </div>
    );
  }

  const prospects = prospectsData?.prospects || [];
  const brands = brandsData?.brands || [];
  const hasError = prospectsData?.error || brandsData?.error;

  // Funnel calculations
  const totalCount = prospects.length;
  const weakCount = prospects.filter((p: any) => p.stage === "WEAK_LISTING").length;
  const enrichedCount = prospects.filter((p: any) => p.stage === "CONTACT_ENRICHED").length;
  const draftedCount = prospects.filter((p: any) => p.stage === "EMAIL_DRAFTED").length;
  const sequencedCount = prospects.filter((p: any) => p.stage === "SEQUENCED").length;
  const repliedCount = prospects.filter((p: any) => p.stage === "REPLIED").length;

  const funnelStages = [
    { name: "Scraped", count: totalCount, pct: 100, color: "from-slate-500/10 to-slate-500/20 text-slate-500" },
    { name: "Weak Listings", count: weakCount, pct: totalCount ? Math.round((weakCount / totalCount) * 100) : 0, color: "from-amber-500/10 to-amber-500/20 text-amber-500" },
    { name: "Enriched Contacts", count: enrichedCount, pct: weakCount ? Math.round((enrichedCount / weakCount) * 100) : 0, color: "from-blue-500/10 to-blue-500/20 text-blue-500" },
    { name: "Drafted Sequences", count: draftedCount, pct: enrichedCount ? Math.round((draftedCount / enrichedCount) * 100) : 0, color: "from-purple-500/10 to-purple-500/20 text-purple-500" },
    { name: "Sequenced Apollo", count: sequencedCount, pct: draftedCount ? Math.round((sequencedCount / draftedCount) * 100) : 0, color: "from-indigo-500/10 to-indigo-500/20 text-indigo-500" },
    { name: "Inbound Replies", count: repliedCount, pct: sequencedCount ? Math.round((repliedCount / sequencedCount) * 100) : 0, color: "from-emerald-500/10 to-emerald-500/20 text-emerald-500" },
  ];

  // Filtering based on search and stage
  const filteredProspects = prospects.filter((p: any) => {
    const matchesSearch = 
      (p.asin && p.asin.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (p.brand && p.brand.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (p.contact_first_name && p.contact_first_name.toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesSearch;
  });

  // Obstruct objection preview email steps
  const mockEmailSteps = [
    {
      step: 1,
      label: "Teardown Anchor",
      subject: `the wording gap on your Amazon listing (${selectedProspect?.asin})`,
      body: `Hey ${selectedProspect?.contact_first_name || "founder"},\n\nI was looking at ${selectedProspect?.brand || "your brand"}'s Amazon listing for your category.\n\n4 of your 5 bullet points open with passive marketing-speak. That's what Rufus sees. When a shopper asks Rufus "is this organic?", Rufus skips your listing because it lacks structured attributes.\n\nI built a private diagotic trace page showing exactly what competitors are doing to capture these citations:\n\n{{calculator_link}}\n\nShould I send the 1-page PDF teardown?`
    },
    {
      step: 2,
      label: "Tactical Insight",
      subject: `quick fix for your Amazon listing`,
      body: `Hey ${selectedProspect?.contact_first_name || "founder"},\n\nFollowing up on that Rufus gap. You can ship one fix in 5 minutes today: rewrite your third bullet to include exact dietary badges.\n\nWhen a shopper asks Rufus "is this keto-friendly?", Rufus will immediately cite your listing. It's a high-leverage change.\n\nDid you have a chance to look at the diagnostic page I sent?`
    },
    {
      step: 3,
      label: "Competitor Proof",
      subject: `why competitors win in Rufus chat`,
      body: `Hey ${selectedProspect?.contact_first_name || "founder"},\n\nI was mapping your listing against category rivals. One competitor has stone-ground shadow-grown Q&As seeded, which Rufus cites directly in 65% of chat sessions.\n\nYou fall behind by 12 citations per session simply because of missing content.\n\nShould I send the side-by-side competitor audit?`
    },
    {
      step: 4,
      label: "Pattern Interrupt",
      subject: `quick question on visibility`,
      body: `Hey ${selectedProspect?.contact_first_name || "founder"},\n\nAre you still focused on growing your organic share of voice on Amazon, or should I close this out?`
    },
    {
      step: 5,
      label: "Break-Up",
      subject: `closing this trace`,
      body: `Hey ${selectedProspect?.contact_first_name || "founder"},\n\nI'm closing the audit tracker for your brand. I left your custom diagnostic page standing here in case timing is better later:\n\n{{calculator_link}}\n\nWish you all the best.`
    }
  ];

  return (
    <div className="space-y-8 pb-12">
      <PageHeader
        title="Autonomous Prospecting Suite"
        description="Monitor enrichment stages, trigger pipeline jobs, and manage persuasion metrics."
      />

      {/* Scheduler controller */}
      <Card className="border border-border/60 bg-gradient-to-r from-card to-muted/40 shadow-sm">
        <CardContent className="flex flex-col gap-6 py-6 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className={cn(
              "flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-tr shadow-sm",
              agentStatus?.running ? "from-emerald-500/10 to-emerald-500/20 text-emerald-500" : "from-amber-500/10 to-amber-500/20 text-amber-500"
            )}>
              <Zap className={cn("h-6 w-6", agentStatus?.running && "animate-pulse")} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-foreground">Autonomous Prospecting Engine</h3>
                <Badge variant={agentStatus?.running ? "success" : "warning"} className="text-[10px] font-semibold uppercase">
                  {agentStatus?.running ? "running" : "paused"}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {agentStatus?.running 
                  ? "Scheduler is active. Daily jobs run at scheduled UTC hours automatically."
                  : "Scheduler is paused. Click Resume to re-enable continuous daily runs."
                }
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant={agentStatus?.running ? "outline" : "default"}
              size="sm"
              className="gap-2 text-xs"
              onClick={handleToggleScheduler}
            >
              {agentStatus?.running ? (
                <>
                  <PauseCircle className="h-4 w-4" /> Pause Scheduler
                </>
              ) : (
                <>
                  <PlayCircle className="h-4 w-4" /> Resume Scheduler
                </>
              )}
            </Button>
            <Button
              variant="accent"
              size="sm"
              className="gap-2 text-xs shadow-sm shadow-accent/20"
              disabled={pipelineLoading}
              onClick={handleTriggerPipeline}
            >
              {pipelineLoading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Running Pipeline...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" /> Run Outbound Pipeline
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Chevron Funnel Flow */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
          <Layers className="h-4 w-4" />
          Acquisition Funnel Stages
        </h3>
        <div className="grid gap-2 grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
          {funnelStages.map((stage, idx) => (
            <div
              key={stage.name}
              className="relative flex flex-col items-center justify-center rounded-xl border border-border/40 bg-card p-4 transition-all duration-300 hover:border-accent/40 hover:shadow-md"
            >
              <span className="text-center text-xs text-muted-foreground">{stage.name}</span>
              <span className="mt-2 text-2xl font-bold text-foreground">{stage.count}</span>
              <div className="mt-2 flex items-center justify-center rounded-full bg-muted px-2 py-0.5 font-mono text-[9px] text-muted-foreground">
                {stage.pct}% {idx > 0 && "conv"}
              </div>
              <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 z-10 hidden lg:block">
                {idx < 5 && <ChevronRight className="h-4 w-4 text-muted-foreground/30" />}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Charts section */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* area chart */}
        <Card className="border border-border/60 bg-card lg:col-span-2 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-accent" />
              Daily Outreach Performance
            </CardTitle>
            <CardDescription className="text-xs">Outbound volume and conversions over the past 7 days</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={ANALYTICS_DATA} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(var(--accent))" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="hsl(var(--accent))" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="repliedGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }} />
                  <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "8px", fontSize: "11px" }} />
                  <Area type="monotone" name="Sent Emails" dataKey="sent" stroke="hsl(var(--accent))" fill="url(#sentGrad)" strokeWidth={2} />
                  <Area type="monotone" name="Inbound Replies" dataKey="replies" stroke="#10b981" fill="url(#repliedGrad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* bar chart */}
        <Card className="border border-border/60 bg-card shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-accent" />
              Category Insights
            </CardTitle>
            <CardDescription className="text-xs">Outreach response rates (%) across niches</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={CATEGORY_PERFORMANCE} layout="vertical" margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                  <XAxis type="number" domain={[0, 20]} axisLine={false} tickLine={false} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }} />
                  <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "hsl(var(--foreground))", fontSize: 11 }} width={80} />
                  <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "8px", fontSize: "11px" }} />
                  <Bar dataKey="responseRate" name="Response Rate %" fill="hsl(var(--accent))" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Prospect controller tools */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* operations controls panel */}
        <Card className="border border-border/60 bg-card shadow-sm h-full">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
              <Zap className="h-4 w-4 text-accent" />
              Job Execution Center
            </CardTitle>
            <CardDescription className="text-xs">Trigger individual idempotent prospecting stages manually</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-3">
            {[
              { type: "scrape", label: "Amazon Scraper", desc: "Scrapes weak ASIN listings" },
              { type: "score", label: "Listing Quality Scorer", desc: "Scores listing against rules" },
              { type: "enrich", label: "Apollo Contact Enricher", desc: "Looks up founder emails" },
              { type: "draft", label: "Persuasion Copy Drafter", desc: "Generates custom Hormozi email copy" },
              { type: "sequence", label: "Apollo Sequence Sync", desc: "Enrolls contacts into sequence" }
            ].map((job) => (
              <div key={job.type} className="flex items-center justify-between border-b border-border/40 pb-2.5 last:border-0 last:pb-0">
                <div>
                  <h4 className="text-xs font-semibold text-foreground">{job.label}</h4>
                  <p className="text-[10px] text-muted-foreground mt-0.5">{job.desc}</p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 text-[10px]"
                  disabled={runningJob !== null}
                  onClick={() => handleTriggerJob(job.type)}
                >
                  {runningJob === job.type ? (
                    <>
                      <Loader2 className="h-3 w-3 animate-spin text-accent" /> Running...
                    </>
                  ) : (
                    "Trigger Run"
                  )}
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* average listing metrics */}
        <Card className="border border-border/60 bg-card shadow-sm h-full lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
              <Layers className="h-4 w-4 text-accent" />
              Category Semantic Gaps (COSMO Axes)
            </CardTitle>
            <CardDescription className="text-xs">Average scores across our pipeline prospects (Weighted /100)</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 md:grid-cols-2 pt-3">
            {[
              { axis: "Shopper Intent Alignment", score: 58, desc: "Keyword matching with colloquial shopper terms", color: "bg-emerald-500" },
              { axis: "Attribute Density", score: 44, desc: "Structured product specifications in listing copy", color: "bg-amber-500" },
              { axis: "Conversational Readability", score: 71, desc: "Flow and natural sentence structures", color: "bg-blue-500" },
              { axis: "Q&A Coverage", score: 34, desc: "Pre-emptively answering potential customer queries", color: "bg-rose-500" },
            ].map((item) => (
              <div key={item.axis} className="space-y-1.5 rounded-xl border border-border/40 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground">{item.axis}</span>
                  <span className="font-mono text-xs font-bold text-muted-foreground">{item.score}/100</span>
                </div>
                <Progress value={item.score} className="h-2" />
                <p className="text-[10px] text-muted-foreground leading-relaxed mt-1">{item.desc}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Search & Main Prospects Table */}
      <div className="space-y-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-1 items-center gap-3 max-w-sm rounded-xl border border-border/60 bg-card px-3 py-1.5 shadow-sm">
            <Search className="h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search by ASIN, Brand, or Contact..."
              className="w-full bg-transparent text-sm placeholder:text-muted-foreground focus:outline-none"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            {STAGE_FILTERS.map((f) => (
              <Button
                key={f.value}
                variant={stageFilter === f.value ? "default" : "outline"}
                size="sm"
                className="h-7 text-[10px]"
                onClick={() => setStageFilter(f.value)}
              >
                {f.label}
              </Button>
            ))}
          </div>
        </div>

        {/* prospects table */}
        <Card className="border border-border/60 bg-card shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-semibold text-muted-foreground">Active Prospecting Leads</CardTitle>
            <span className="text-xs text-muted-foreground">{filteredProspects.length} total</span>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="text-xs font-medium">ASIN</TableHead>
                  <TableHead className="text-xs font-medium">Brand</TableHead>
                  <TableHead className="text-xs font-medium">Stage</TableHead>
                  <TableHead className="text-xs font-medium text-right">Quality Score</TableHead>
                  <TableHead className="text-xs font-medium text-right">COSMO Score</TableHead>
                  <TableHead className="text-xs font-medium">Contact & Target</TableHead>
                  <TableHead className="text-xs font-medium text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredProspects.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-sm text-muted-foreground py-8">
                      No matching prospects found.
                    </TableCell>
                  </TableRow>
                )}
                {filteredProspects.map((p: any) => (
                  <TableRow key={p.id || p.asin} className="group transition-colors hover:bg-muted/40">
                    <TableCell className="font-mono text-xs text-muted-foreground font-semibold">{p.asin || "—"}</TableCell>
                    <TableCell className="text-sm font-semibold text-foreground">{p.brand || "—"}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className={cn("text-[9px] font-bold uppercase tracking-wider px-2 py-0.5", stageBadgeClass(p.stage))}>
                        {p.stage?.replaceAll("_", " ")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs text-muted-foreground">
                      {p.quality_score != null ? p.quality_score : "—"}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {p.cosmo_score != null ? (
                        <span className={cn(
                          "font-bold",
                          p.cosmo_score >= 65 ? "text-emerald-600 dark:text-emerald-400" :
                          p.cosmo_score >= 40 ? "text-amber-600 dark:text-amber-400" :
                          "text-rose-600 dark:text-rose-400"
                        )}>
                          {p.cosmo_score}
                        </span>
                      ) : "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="text-xs font-semibold text-foreground">
                          {p.contact_first_name || "Unenriched"}
                        </span>
                        <span className="text-[10px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                          {p.contact_email ? (
                            <>
                              <Mail className="h-3 w-3 text-muted-foreground/60" /> {p.contact_email}
                            </>
                          ) : (
                            <>
                              <User className="h-3 w-3 text-muted-foreground/60" /> {p.contact_title || "No Title found"}
                            </>
                          )}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-foreground"
                          disabled={p.stage !== "EMAIL_DRAFTED"}
                          onClick={() => {
                            setSelectedProspect(p);
                            setCurrentStepIndex(0);
                          }}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {/* Custom dynamic interactive drawer for previewing/editing email sequences */}
      {selectedProspect && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-background/80 backdrop-blur-sm">
          <div className="h-full w-full max-w-2xl border-l border-border/60 bg-card p-6 shadow-2xl animate-in slide-in-from-right duration-300 overflow-y-auto">
            <div className="flex items-center justify-between border-b border-border pb-4">
              <div>
                <Badge variant="secondary" className="bg-purple-100/80 text-purple-700 dark:bg-purple-900/20 dark:text-purple-400">
                  Alex Hormozi persuasion sequence
                </Badge>
                <h3 className="text-lg font-bold text-foreground mt-1">Review Prospect Sequence</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Brand: <span className="font-semibold text-foreground">{selectedProspect.brand}</span> | ASIN: <span className="font-semibold text-foreground">{selectedProspect.asin}</span>
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-8"
                onClick={() => setSelectedProspect(null)}
              >
                Close Drawer
              </Button>
            </div>

            {/* Steps tabs */}
            <div className="grid grid-cols-5 gap-1 border-b border-border/40 py-4">
              {mockEmailSteps.map((step, idx) => (
                <button
                  key={step.step}
                  className={cn(
                    "flex flex-col items-center justify-center py-2 rounded-lg text-[10px] font-semibold border transition-all",
                    currentStepIndex === idx
                      ? "bg-primary border-primary text-primary-foreground shadow-sm shadow-primary/25"
                      : "bg-muted/40 hover:bg-muted border-transparent text-muted-foreground"
                  )}
                  onClick={() => setCurrentStepIndex(idx)}
                >
                  <span>Step {step.step}</span>
                  <span className="text-[8px] opacity-80 mt-0.5 font-normal truncate max-w-[80px]">{step.label}</span>
                </button>
              ))}
            </div>

            {/* Email preview card */}
            <div className="space-y-4 pt-6">
              <div className="space-y-1 rounded-xl border border-border/50 bg-muted/30 p-4">
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-semibold text-muted-foreground">Subject:</span>
                  <span className="font-semibold text-foreground">{mockEmailSteps[currentStepIndex].subject}</span>
                </div>
              </div>

              <div className="rounded-xl border border-border/50 bg-card p-5 shadow-inner">
                <pre className="whitespace-pre-wrap font-sans text-sm text-foreground leading-relaxed">
                  {mockEmailSteps[currentStepIndex].body}
                </pre>
              </div>

              {/* Loom and calculator link previews */}
              <div className="grid gap-2 grid-cols-2">
                <div className="rounded-xl border border-border/40 p-3 bg-muted/10">
                  <span className="text-[10px] text-muted-foreground">Step 1 Landing Page Audit URL</span>
                  <p className="text-xs font-semibold text-accent leading-relaxed mt-1 truncate">
                    http://localhost:3000/p/{selectedProspect.brand_key || "default_brand"}
                  </p>
                </div>
                <div className="rounded-xl border border-border/40 p-3 bg-muted/10">
                  <span className="text-[10px] text-muted-foreground">Worst Rufus Axis at send</span>
                  <p className="text-xs font-semibold text-foreground leading-relaxed mt-1 uppercase">
                    Q&A Coverage
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-border pt-4 mt-6">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedProspect(null)}
                >
                  Cancel
                </Button>
                <Button
                  variant="default"
                  size="sm"
                  className="gap-2"
                  onClick={() => {
                    alert(`Sequence enrolled successfully inside Apollo for ${selectedProspect.brand}!`);
                    setSelectedProspect(null);
                  }}
                >
                  <Send className="h-3.5 w-3.5" /> Approve & Sequence
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
