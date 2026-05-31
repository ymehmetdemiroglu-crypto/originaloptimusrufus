"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./sidebar";

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // Determine if the current page is public
  const isPublic = pathname?.startsWith("/p/") || pathname === "/optimize";

  return (
    <div className="flex min-h-screen w-full bg-[#0A192F]">
      {/* Structurally identical on all routes to prevent tag mismatches */}
      <div className={isPublic ? "hidden" : "block"}>
        <Sidebar />
      </div>
      <main className={`flex-1 transition-all duration-300 ${isPublic ? "pl-0" : "pl-64"}`}>
        <div className={isPublic ? "w-full h-full" : "mx-auto max-w-7xl px-6 py-8"}>
          {children}
        </div>
      </main>
    </div>
  );
}
