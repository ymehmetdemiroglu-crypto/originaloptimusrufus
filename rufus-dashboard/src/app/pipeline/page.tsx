"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/dashboard/page-header";
import { MetricCard } from "@/components/dashboard/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Play, Pause, RotateCcw, CheckCircle2, XCircle, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

const throughputData = [
  { hour: "00:00", jobs: 4 },
  { hour: "04:00", jobs: 2 },
  { hour: "08:00", jobs: 12 },
  { hour: "12:00", jobs: 18 },
  { hour: "16:00", jobs: 15 },
  { hour: "20:00", jobs: 9 },
];

export default function PipelinePage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.pipeline().then((res) => {
      setData(res);
      setLoading(false);
    });
  }, []);

  if (loading || !data) {
    return (
      <div className="flex h-96 items-center justify-center text-sm text-muted-foreground">
        Loading pipeline...
      </div>
    );
  }

  const publishStatus = [
    { asin: "B08N5WRWNW", title: "Stainless Steel Water Bottle", status: "live", publishedAt: "09:12", revision: 3 },
    { asin: "B07ZPKBL6P", title: "Organic Matcha Green Tea", status: "live", publishedAt: "09:01", revision: 2 },
    { asin: "B09QXT8B7L", title: "Ergonomic Office Chair", status: "pending_review", publishedAt: "—", revision: 1 },
    { asin: "B0B2QGDR6R", title: "Portable Bluetooth Speaker", status: "rejected", publishedAt: "—", revision: 1 },
  ];

  return (
    <div className="space-y-8">
      <PageHeader title="Optimization Pipeline" description="Job queue, processing stages, and SP-API publish status." />

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard title="Running" value={data.running} subtitle="Active jobs" badge={{ label: "Processing", variant: "default" }}>
          <div className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            <span>Avg 8 min per job</span>
          </div>
        </MetricCard>
        <MetricCard title="Queued" value={data.queued} subtitle="Awaiting workers" />
        <MetricCard title="Completed (24h)" value={data.completed} subtitle="Successfully optimized" badge={{ label: "Today", variant: "success" }} />
        <MetricCard title="Failed" value={data.failed} subtitle="Require attention" badge={{ label: "Action Needed", variant: data.failed > 0 ? "destructive" : "success" }} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="border border-border/60 bg-card lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Job Throughput (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={throughputData}>
                  <defs>
                    <linearGradient id="throughputGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(var(--accent))" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="hsl(var(--accent))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="hour" axisLine={false} tickLine={false} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
                  <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }} />
                  <Area type="monotone" dataKey="jobs" stroke="hsl(var(--accent))" fill="url(#throughputGradient)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="border border-border/60 bg-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Pipeline Stages</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {[
              { stage: "Ingestion", desc: "SP-API / scrape", jobs: 2 },
              { stage: "Embedding", desc: "Gemini 3072D", jobs: 1 },
              { stage: "COSMO Mapping", desc: "15 relations", jobs: 1 },
              { stage: "Competitor Analysis", desc: "Vector gaps", jobs: 0 },
              { stage: "Optimization", desc: "Content gen", jobs: 0 },
              { stage: "Publish", desc: "SP-API PUT", jobs: 2 },
            ].map((s, i, arr) => (
              <div key={s.stage} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-foreground">{s.stage}</p>
                    <p className="text-[10px] text-muted-foreground">{s.desc}</p>
                  </div>
                  <span className="font-mono text-xs text-muted-foreground">{s.jobs} jobs</span>
                </div>
                {i < arr.length - 1 && <Separator className="bg-border/40" />}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card className="border border-border/60 bg-card">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Active Jobs</CardTitle>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs"><Pause className="h-3 w-3" /> Pause All</Button>
            <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs"><RotateCcw className="h-3 w-3" /> Retry Failed</Button>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="text-xs font-medium">Job ID</TableHead>
                <TableHead className="text-xs font-medium">ASIN</TableHead>
                <TableHead className="text-xs font-medium">Client</TableHead>
                <TableHead className="text-xs font-medium">Stage</TableHead>
                <TableHead className="text-xs font-medium">Status</TableHead>
                <TableHead className="text-xs font-medium">Progress</TableHead>
                <TableHead className="text-xs font-medium text-right">Started</TableHead>
                <TableHead className="text-xs font-medium text-right">ETA</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.jobs.map((job: any) => (
                <TableRow key={job.id} className="group">
                  <TableCell className="font-mono text-xs text-muted-foreground">{job.id}</TableCell>
                  <TableCell className="font-mono text-xs text-foreground">{job.asin}</TableCell>
                  <TableCell className="text-sm text-foreground">{job.client}</TableCell>
                  <TableCell className="text-xs text-muted-foreground capitalize">{job.stage.replaceAll("_", " ")}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className={cn(
                      "text-[10px] font-semibold uppercase",
                      job.status === "running" && "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
                      job.status === "queued" && "bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-400",
                      job.status === "completed" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
                      job.status === "failed" && "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400"
                    )}>
                      {job.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="w-[140px]">
                    <Progress value={job.progress} className="h-1.5" />
                    <span className="mt-0.5 block text-right font-mono text-[10px] text-muted-foreground">{job.progress}%</span>
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">{job.started}</TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">{job.eta ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="border border-border/60 bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">SP-API Publish Status</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="text-xs font-medium">ASIN</TableHead>
                <TableHead className="text-xs font-medium">Product</TableHead>
                <TableHead className="text-xs font-medium">Status</TableHead>
                <TableHead className="text-xs font-medium text-right">Published At</TableHead>
                <TableHead className="text-xs font-medium text-right">Revision</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {publishStatus.map((item) => (
                <TableRow key={item.asin} className="group">
                  <TableCell className="font-mono text-xs text-muted-foreground">{item.asin}</TableCell>
                  <TableCell className="text-sm text-foreground">{item.title}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      {item.status === "live" && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />}
                      {item.status === "rejected" && <XCircle className="h-3.5 w-3.5 text-rose-500" />}
                      {item.status === "pending_review" && <Clock className="h-3.5 w-3.5 text-amber-500" />}
                      <Badge variant="secondary" className={cn(
                        "text-[10px] font-semibold uppercase",
                        item.status === "live" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
                        item.status === "pending_review" && "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
                        item.status === "rejected" && "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400"
                      )}>
                        {item.status.replaceAll("_", " ")}
                      </Badge>
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">{item.publishedAt}</TableCell>
                  <TableCell className="text-right font-mono text-xs text-foreground">v{item.revision}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
