"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  delta?: {
    value: string;
    positive: boolean;
  };
  badge?: {
    label: string;
    variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning";
  };
  className?: string;
  children?: React.ReactNode;
}

export function MetricCard({
  title,
  value,
  subtitle,
  delta,
  badge,
  className,
  children,
}: MetricCardProps) {
  return (
    <Card className={cn("border border-border/60 bg-card", className)}>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        {badge && (
          <Badge
            variant={badge.variant === "success" || badge.variant === "warning" ? "secondary" : badge.variant}
            className={cn(
              "text-[10px] font-semibold uppercase tracking-wider",
              badge.variant === "success" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
              badge.variant === "warning" && "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
              badge.variant === "destructive" && "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400"
            )}
          >
            {badge.label}
          </Badge>
        )}
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold tracking-tight text-foreground">
            {value}
          </span>
          {delta && (
            <span
              className={cn(
                "text-xs font-medium",
                delta.positive
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-rose-600 dark:text-rose-400"
              )}
            >
              {delta.positive ? "+" : ""}
              {delta.value}
            </span>
          )}
        </div>
        {subtitle && (
          <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
        )}
        {children && <div className="mt-4">{children}</div>}
      </CardContent>
    </Card>
  );
}
