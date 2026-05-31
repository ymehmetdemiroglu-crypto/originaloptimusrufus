"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/dashboard/page-header";
import { MetricCard } from "@/components/dashboard/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Search, Shield, ShieldAlert, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

export default function ListingAnalyzerPage() {
  const [asin, setAsin] = useState("B08N5WRWNW");
  const [analyzing, setAnalyzing] = useState(false);
  const [data, setData] = useState<any>(null);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const res = await api.analyze(asin);
      setData(res);
    } catch (e) {
      console.error(e);
    } finally {
      setAnalyzing(false);
    }
  };

  const clusterGroups = data
    ? (Array.from(new Set(data.relations.map((r: any) => r.cluster))) as string[])
    : [];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Listing Analyzer"
        description="Analyze any ASIN for COSMO semantic coverage and embedding alignment."
      />

      <Card className="border border-border/60 bg-card">
        <CardContent className="flex flex-col gap-4 pt-6 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-2">
            <label className="text-sm font-medium text-foreground">ASIN</label>
            <Input
              value={asin}
              onChange={(e) => setAsin(e.target.value)}
              placeholder="Enter Amazon ASIN"
              className="font-mono"
            />
          </div>
          <Button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="bg-accent text-accent-foreground hover:bg-accent/90"
          >
            <Search className="mr-2 h-4 w-4" />
            {analyzing ? "Analyzing..." : "Analyze Listing"}
          </Button>
        </CardContent>
      </Card>

      {data && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <MetricCard
              title="Overall Readiness"
              value={data.overall_score}
              badge={{
                label: data.overall_score >= 65 ? "Good" : "Needs Work",
                variant: data.overall_score >= 65 ? "success" : "warning",
              }}
            >
              <Progress value={data.overall_score} className="mt-3 h-2" />
            </MetricCard>

            <MetricCard
              title="Keyword Safety"
              value={data.keyword_safety}
              subtitle="No ranking signals at risk"
              badge={{ label: "Verified", variant: "success" }}
            >
              <div className="mt-3 flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                <ShieldCheck className="h-5 w-5" />
                <span className="text-xs font-medium">All changes preserve A9 rank</span>
              </div>
            </MetricCard>

            <MetricCard
              title="Embedding Dimensions"
              value={data.embedding_dimensions.toLocaleString()}
              subtitle="Archival quality vectors"
            >
              <div className="mt-3 flex items-center gap-2 text-muted-foreground">
                <span className="text-xs font-medium">Model: gemini-embedding-001</span>
              </div>
            </MetricCard>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="border border-border/60 bg-card lg:col-span-2">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  COSMO 15 Relation Type Coverage
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {clusterGroups.map((cluster: string) => {
                  const items = data.relations.filter((r: any) => r.cluster === cluster);
                  const avg = Math.round(items.reduce((a: number, b: any) => a + b.confidence_score, 0) / items.length * 100);
                  return (
                    <div key={cluster} className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-foreground">{cluster}</span>
                        <span className="font-mono text-xs text-muted-foreground">Avg: {avg}</span>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {items.map((relation: any) => (
                          <div key={relation.relation} className="rounded-md border border-border/60 p-3 transition-colors hover:bg-muted/30">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-medium text-foreground">{relation.relation}</span>
                              <span className={cn(
                                "font-mono text-xs font-bold",
                                relation.confidence_score >= 0.7 ? "text-emerald-600 dark:text-emerald-400" :
                                relation.confidence_score >= 0.45 ? "text-amber-600 dark:text-amber-400" :
                                "text-rose-600 dark:text-rose-400"
                              )}>
                                {Math.round(relation.confidence_score * 100)}
                              </span>
                            </div>
                            <Progress value={relation.confidence_score * 100} className="mt-2 h-1" />
                            {relation.detected_signals.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1">
                                {relation.detected_signals.map((s: string) => (
                                  <span key={s} className="inline-block rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{s}</span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                      <Separator className="last:hidden" />
                    </div>
                  );
                })}
              </CardContent>
            </Card>

            <Card className="border border-border/60 bg-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Optimization Safety
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {data.safety_checks.map((check: any) => (
                  <div key={check.label} className="flex items-center justify-between rounded-md border border-border/40 p-2.5">
                    <div className="flex items-center gap-2">
                      {check.status === "safe" ? (
                        <ShieldCheck className="h-4 w-4 text-emerald-500" />
                      ) : check.status === "caution" ? (
                        <ShieldAlert className="h-4 w-4 text-amber-500" />
                      ) : (
                        <Shield className="h-4 w-4 text-rose-500" />
                      )}
                      <span className="text-sm text-foreground">{check.label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{check.detail}</span>
                      <Badge variant="secondary" className={cn(
                        "text-[10px] font-semibold uppercase",
                        check.status === "safe" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
                        check.status === "caution" && "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
                        check.status === "risky" && "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400"
                      )}>
                        {check.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
