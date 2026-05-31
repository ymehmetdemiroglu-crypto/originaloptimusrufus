import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Rufus Visibility Audit — Optimus Rufus",
  description: "See how Amazon's Rufus AI sees your listing — and how to fix it.",
};

export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      {children}
    </div>
  );
}
