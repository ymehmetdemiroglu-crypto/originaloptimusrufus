"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  Target,
  GitBranch,
  Users,
  Sparkles,
  Contact,
  Bot,
  Orbit,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme-toggle";

const navItems = [
  {
    label: "Overview",
    href: "/",
    icon: LayoutDashboard,
  },
  {
    label: "Omni-Dashboard",
    href: "/omni",
    icon: Orbit,
  },
  {
    label: "Listing Analyzer",
    href: "/listing-analyzer",
    icon: Search,
  },
  {
    label: "Competitor Intel",
    href: "/competitor-intel",
    icon: Target,
  },
  {
    label: "Pipeline",
    href: "/pipeline",
    icon: GitBranch,
  },
  {
    label: "Marketing Assistant",
    href: "/marketing-assistant",
    icon: Sparkles,
  },
  {
    label: "Prospect Teardown Demo",
    href: "/prospect-pitch",
    icon: Bot,
  },
  {
    label: "Prospects",
    href: "/prospects",
    icon: Contact,
  },
  {
    label: "Clients",
    href: "/clients",
    icon: Users,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-64 flex-col border-r border-[#E0E1DD]/10 bg-commandBlueDark">
      <div className="flex h-16 items-center gap-3 border-b border-[#E0E1DD]/10 px-6">
        <div className="relative w-7 h-7 flex items-center justify-center">
          <svg viewBox="0 0 100 100" className="w-full h-full text-white drop-shadow-[0_0_6px_rgba(230,57,70,0.4)]">
            <polygon points="50,5 95,25 95,75 50,95 5,75 5,25" fill="none" stroke="currentColor" strokeWidth="8" />
            <circle cx="50" cy="50" r="14" fill="#E63946" className="animate-pulse" />
          </svg>
        </div>
        <div className="flex flex-col font-display tracking-[0.1em] text-[11px] uppercase leading-none">
          <span className="font-semibold text-white">OPTIMUS</span>
          <span className="mt-0.5 font-light text-titaniumSilver/60">PRIME</span>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 px-0 py-4">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 px-6 py-3.5 text-xs uppercase tracking-wider font-display transition-colors",
                isActive
                  ? "bg-white/[0.03] text-white border-l-2 border-[#00F5FF]"
                  : "text-[#E0E1DD]/60 hover:bg-white/[0.01] hover:text-white border-l-2 border-transparent"
              )}
            >
              <item.icon
                className={cn(
                  "h-4 w-4 transition-colors",
                  isActive
                    ? "text-[#00F5FF] text-glow-cyan"
                    : "text-[#E0E1DD]/40 group-hover:text-white"
                )}
              />
              {item.label}
              {isActive && (
                <div className="ml-auto h-1.5 w-1.5 bg-[#00F5FF] box-glow-cyan" />
              )}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-sidebar-border px-3 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 px-3">
            <div className="h-6 w-6 rounded-full bg-muted" />
            <div className="flex flex-col">
              <span className="text-xs font-medium text-sidebar-foreground">
                Agency Admin
              </span>
              <span className="text-[10px] text-sidebar-foreground/50">
                admin@agency.co
              </span>
            </div>
          </div>
          <ThemeToggle />
        </div>
      </div>
    </aside>
  );
}
