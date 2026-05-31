"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/dashboard/page-header";
import { MetricCard } from "@/components/dashboard/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
} from "recharts";
import { ArrowUpRight, Search } from "lucide-react";
import { cn } from "@/lib/utils";

export default function CompetitorIntelPage() {
  const [asin, setAsin] = useState("B08N5WRWNW");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);

  const handleAnalyze = async () => {
    setLoading(true);
    try {
      const res = await api.competitors(asin);
      setData(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Competitor Intelligence"
        description="Vector-based semantic gap analysis and opportunity scoring."
      />

      <Card className="border border-border/60 bg-card">
        <CardContent className="flex flex-col gap-4 pt-6 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-2">
            <label className="text-sm font-medium text-foreground">ASIN</label>
            <Input value={asin} onChange={(e) => setAsin(e.target.value)} placeholder="Enter ASIN" className="font-mono" />
          </div>
          <Button onClick={handleAnalyze} disabled={loading} className="bg-accent text-accent-foreground hover:bg-accent/90">
            <Search className="mr-2 h-4 w-4" />
            {loading ? "Analyzing..." : "Analyze Competitors"}
          </Button>
        </CardContent>
      </Card>

      {data && (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <MetricCard title="Competitors Analyzed" value={data.competitor_profiles.length} subtitle="Top category performers" />
            <MetricCard title="Semantic Gaps Found" value={data.gap_opportunities.length} subtitle="High-opportunity gaps" badge={{ label: "Action Needed", variant: "warning" }} />
            <MetricCard title="Avg. Gap Score" value={data.gap_opportunities.length > 0 ? Math.round(data.gap_opportunities.reduce((a: number, b: any) => a + b.opportunity_score, 0) / data.gap_opportunities.length) : 0} subtitle="Opportunity potential" />
            <MetricCard title="Safe Gaps" value={data.positioning_summary.safe_gaps} subtitle="Ready to implement" badge={{ label: "Verified", variant: "success" }} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="border border-border/60 bg-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Competitor Similarity</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.competitor_profiles} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                      <XAxis type="number" domain={[0, 1]} axisLine={false} tickLine={false} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
                      <YAxis type="category" dataKey="asin" axisLine={false} tickLine={false} width={80} tick={{ fill: "hsl(var(--foreground))", fontSize: 12, fontFamily: "var(--font-jetbrains-mono)" }} />
                      <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }} />
                      <Bar dataKey="similarity" fill="hsl(var(--accent))" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card className="border border-border/60 bg-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Positioning Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.entries(data.positioning_summary).map(([key, value]: [string, any]) => (
                  <div key={key} className="flex items-center justify-between rounded-md border border-border/40 p-3">
                    <span className="text-sm text-foreground capitalize">{key.replace(/_/g, " ")}</span>
                    <span className="font-mono text-sm text-muted-foreground">{typeof value === "number" ? value.toFixed ? value.toFixed(2) : value : String(value)}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          <Card className="border border-border/60 bg-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Gap Opportunities</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="text-xs font-medium">ID</TableHead>
                    <TableHead className="text-xs font-medium">Description</TableHead>
                    <TableHead className="text-xs font-medium text-right">Competitors</TableHead>
                    <TableHead className="text-xs font-medium text-right">Score</TableHead>
                    <TableHead className="text-xs font-medium">Safety</TableHead>
                    <TableHead className="text-xs font-medium">Traffic</TableHead>
                    <TableHead className="text-xs font-medium">Suggested Content</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.gap_opportunities.map((gap: any) => (
                    <TableRow key={gap.gap_id} className="group">
                      <TableCell className="font-mono text-xs text-muted-foreground">{gap.gap_id}</TableCell>
                      <TableCell className="text-sm text-foreground">{gap.description}</TableCell>
                      <TableCell className="text-right font-mono text-sm text-foreground">{gap.competitors_covering.length}</TableCell>
                      <TableCell className="text-right">
                        <span className="inline-flex items-center gap-0.5 font-mono text-sm font-bold text-accent">
                          <ArrowUpRight className="h-3 w-3" />
                          {gap.opportunity_score}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className={cn(
                          "text-[10px] font-semibold uppercase",
                          gap.keyword_safety_rating === "SAFE" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
                          gap.keyword_safety_rating === "CAUTION" && "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
                          gap.keyword_safety_rating === "RISKY" && "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400"
                        )}>
                          {gap.keyword_safety_rating}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className={cn(
                          "text-[10px] font-semibold uppercase",
                          gap.estimated_traffic_impact === "HIGH" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
                          gap.estimated_traffic_impact === "MEDIUM" && "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
                          gap.estimated_traffic_impact === "LOW" && "bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-400"
                        )}>
                          {gap.estimated_traffic_impact}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[240px] text-xs text-muted-foreground">{gap.suggested_content}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
