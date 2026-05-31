"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { MetricCard } from "@/components/dashboard/metric-card";
import { Sparkline } from "@/components/dashboard/sparkline";
import { PageHeader } from "@/components/dashboard/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
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
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";
import { ArrowUpRight, ArrowDownRight, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

export default function OverviewPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [sparklineData, setSparklineData] = useState<{ value: number }[]>([]);

  useEffect(() => {
    setSparklineData(Array.from({ length: 20 }, (_, i) => ({
      value: 60 + Math.random() * 30 + i * 0.5,
    })));
  }, []);

  useEffect(() => {
    api.overview().then((res) => {
      setData(res);
      setLoading(false);
    });
  }, []);

  if (loading || !data) {
    return (
      <div className="flex h-96 items-center justify-center text-sm text-muted-foreground">
        Loading dashboard...
      </div>
    );
  }

  const overallScore = data.cosmo_readiness_score;
  const scoreGrade = data.grade;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Overview"
        description="COSMO readiness and optimization performance at a glance."
      />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="COSMO Readiness Score"
          value={overallScore}
          subtitle="Weighted across 15 relation types"
          badge={{
            label: `Grade ${scoreGrade}`,
            variant: overallScore >= 65 ? "success" : "warning",
          }}
          className="lg:col-span-1"
        >
          <div className="mt-3">
            <Progress value={overallScore} className="h-2" />
          </div>
        </MetricCard>

        <MetricCard
          title="Active Listings"
          value={data.active_listings?.toLocaleString() ?? "0"}
          subtitle="Across all clients"
          delta={{ value: "12%", positive: true }}
        >
          <Sparkline data={sparklineData} trend="up" className="mt-2" />
        </MetricCard>

        <MetricCard
          title="Avg. Competitor Similarity"
          value={`${data.avg_competitor_similarity}%`}
          subtitle="Semantic vector distance"
          delta={{ value: "3.2%", positive: true }}
        >
          <Sparkline data={sparklineData.slice().reverse()} trend="neutral" />
        </MetricCard>

        <MetricCard
          title="Optimization Jobs (7d)"
          value={data.optimization_jobs_7d}
          subtitle="Completed this week"
          delta={{ value: "8%", positive: true }}
        >
          <Sparkline data={sparklineData} trend="up" />
        </MetricCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="border border-border/60 bg-card lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Readiness Score Trend
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.readiness_trend}>
                  <defs>
                    <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(var(--accent))" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="hsl(var(--accent))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} domain={[50, 80]} />
                  <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }} />
                  <Area type="monotone" dataKey="score" stroke="hsl(var(--accent))" fill="url(#scoreGradient)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="border border-border/60 bg-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Cluster Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.cluster_breakdown.map((item: any) => (
              <div key={item.cluster} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-foreground">{item.cluster}</span>
                  <span className="font-mono text-xs text-muted-foreground">{item.score}/100</span>
                </div>
                <Progress value={item.score} className="h-1.5" />
                <p className="text-[10px] text-muted-foreground">Weight: {item.weight}%</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="border border-border/60 bg-card">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              Top Semantic Gaps
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.gap_alerts.map((alert: any) => (
              <div key={alert.id} className="group rounded-md border border-border/60 p-3 transition-colors hover:bg-muted/50">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground">{alert.relation}</span>
                  <Badge variant="secondary" className={cn(
                    "text-[10px] font-semibold",
                    alert.impact === "High" ? "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400" : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                  )}>
                    {alert.impact}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{alert.description}</p>
                <p className="mt-1 text-[10px] text-muted-foreground">{alert.competitors} competitors covering this</p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border border-border/60 bg-card lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Competitor Semantic Similarity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.competitor_similarity} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
                  <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} width={80} tick={{ fill: "hsl(var(--foreground))", fontSize: 12, fontFamily: "var(--font-jetbrains-mono)" }} />
                  <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }} />
                  <Bar dataKey="score" fill="hsl(var(--accent))" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border border-border/60 bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Recent Optimization Jobs
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="text-xs font-medium">ASIN</TableHead>
                <TableHead className="text-xs font-medium">Product</TableHead>
                <TableHead className="text-xs font-medium">Status</TableHead>
                <TableHead className="text-xs font-medium text-right">Before</TableHead>
                <TableHead className="text-xs font-medium text-right">After</TableHead>
                <TableHead className="text-xs font-medium text-right">Change</TableHead>
                <TableHead className="text-xs font-medium text-right">Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.recent_jobs.map((job: any) => (
                <TableRow key={job.id} className="group">
                  <TableCell className="font-mono text-xs text-muted-foreground">{job.asin}</TableCell>
                  <TableCell className="text-sm font-medium text-foreground">{job.title}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className={cn(
                      "text-[10px] font-semibold uppercase",
                      job.status === "completed" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
                      job.status === "processing" && "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
                      job.status === "failed" && "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400"
                    )}>
                      {job.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm text-muted-foreground">{job.readiness_before}</TableCell>
                  <TableCell className="text-right font-mono text-sm text-foreground">{job.readiness_after ?? "—"}</TableCell>
                  <TableCell className="text-right">
                    {job.readiness_after && (
                      <span className="inline-flex items-center gap-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                        <ArrowUpRight className="h-3 w-3" />
                        {job.readiness_after - job.readiness_before}
                      </span>
                    )}
                    {job.status === "failed" && (
                      <span className="inline-flex items-center gap-0.5 text-xs font-medium text-rose-600 dark:text-rose-400">
                        <ArrowDownRight className="h-3 w-3" />
                        Failed
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">{job.date}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
