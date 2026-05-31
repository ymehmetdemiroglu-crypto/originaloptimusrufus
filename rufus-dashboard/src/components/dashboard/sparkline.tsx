"use client";

import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { cn } from "@/lib/utils";

interface SparklineProps {
  data: { value: number }[];
  className?: string;
  color?: string;
  trend?: "up" | "down" | "neutral";
}

export function Sparkline({
  data,
  className,
  color,
  trend = "neutral",
}: SparklineProps) {
  const defaultColor =
    trend === "up"
      ? "hsl(160 84% 39%)"
      : trend === "down"
      ? "hsl(0 84% 60%)"
      : "hsl(215 16% 47%)";

  const strokeColor = color ?? defaultColor;
  const fillColor = strokeColor.replace(")", " / 0.15)")
    .replace("hsl(", "hsla(");

  return (
    <div className={cn("h-8 w-full", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <Area
            type="monotone"
            dataKey="value"
            stroke={strokeColor}
            fill={fillColor}
            strokeWidth={1.5}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
