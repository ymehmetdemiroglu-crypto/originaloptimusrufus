"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/dashboard/page-header";
import { MetricCard } from "@/components/dashboard/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
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
import { Plus, Users, Package, CreditCard } from "lucide-react";
import { cn } from "@/lib/utils";

export default function ClientsPage() {
  const [clients, setClients] = useState<any[]>([]);
  const [usage, setUsage] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.clients(), api.clientUsage()]).then(([c, u]) => {
      setClients(c);
      setUsage(u);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center text-sm text-muted-foreground">
        Loading clients...
      </div>
    );
  }

  const totalMrr = clients.reduce((a, c) => a + c.mrr, 0);
  const activeClients = clients.filter((c) => c.status === "active").length;
  const totalListings = clients.reduce((a, c) => a + c.listings, 0);

  const tierColors: Record<string, string> = {
    Starter: "bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-400",
    Growth: "bg-accent/10 text-accent dark:bg-accent/20 dark:text-accent-foreground",
    Enterprise: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  };

  return (
    <div className="space-y-8">
      <PageHeader title="Clients" description="Multi-tenant client management and usage overview.">
        <Button size="sm" className="bg-accent text-accent-foreground hover:bg-accent/90 gap-1.5">
          <Plus className="h-4 w-4" />
          Add Client
        </Button>
      </PageHeader>

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard title="Active Clients" value={activeClients} subtitle={`of ${clients.length} total`}>
          <div className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Users className="h-3 w-3" />
            <span>{clients.filter((c) => c.tier === "Enterprise").length} enterprise</span>
          </div>
        </MetricCard>
        <MetricCard title="Total Listings" value={totalListings.toLocaleString()} subtitle="Across all clients">
          <div className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Package className="h-3 w-3" />
            <span>Avg {Math.round(totalListings / clients.length)} per client</span>
          </div>
        </MetricCard>
        <MetricCard title="Monthly Revenue" value={`$${(totalMrr / 1000).toFixed(1)}k`} subtitle="Combined MRR" delta={{ value: "12%", positive: true }}>
          <div className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
            <CreditCard className="h-3 w-3" />
            <span>All paid up to date</span>
          </div>
        </MetricCard>
        <MetricCard title="API Usage" value="92%" subtitle="Gemini embedding quota" badge={{ label: "Healthy", variant: "success" }}>
          <Progress value={92} className="mt-3 h-2" />
        </MetricCard>
      </div>

      <Card className="border border-border/60 bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Embedding Usage by Client</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={usage}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis dataKey="client" axisLine={false} tickLine={false} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} />
                <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }} />
                <Bar dataKey="embeddings" fill="hsl(var(--accent))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card className="border border-border/60 bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Client Directory</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="text-xs font-medium">Client</TableHead>
                <TableHead className="text-xs font-medium">Tier</TableHead>
                <TableHead className="text-xs font-medium text-right">Listings</TableHead>
                <TableHead className="text-xs font-medium text-right">ASINs</TableHead>
                <TableHead className="text-xs font-medium">Usage</TableHead>
                <TableHead className="text-xs font-medium text-right">MRR</TableHead>
                <TableHead className="text-xs font-medium">Status</TableHead>
                <TableHead className="text-xs font-medium text-right">Last Active</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {clients.map((client) => (
                <TableRow key={client.id} className="group cursor-pointer transition-colors hover:bg-muted/30">
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar className="h-7 w-7">
                        <AvatarFallback className="bg-muted text-[10px] font-bold text-muted-foreground">
                          {client.name.split(" ").map((n: string) => n[0]).join("").slice(0, 2)}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="text-sm font-medium text-foreground">{client.name}</p>
                        <p className="font-mono text-[10px] text-muted-foreground">{client.id}</p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className={cn("text-[10px] font-semibold", tierColors[client.tier])}>
                      {client.tier}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm text-foreground">{client.listings}</TableCell>
                  <TableCell className="text-right font-mono text-sm text-muted-foreground">{client.asins}</TableCell>
                  <TableCell className="w-[120px]">
                    <Progress value={client.usage} className="h-1.5" />
                    <span className="mt-0.5 block text-right font-mono text-[10px] text-muted-foreground">{client.usage}%</span>
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm text-foreground">${client.mrr.toLocaleString()}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className={cn(
                      "text-[10px] font-semibold uppercase",
                      client.status === "active" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
                      client.status === "paused" && "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                    )}>
                      {client.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">{client.last_active}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
