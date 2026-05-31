"use client";

import { useState } from "react";
import { PageHeader } from "@/components/dashboard/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import {
  Sparkles,
  Bot,
  User,
  ShieldCheck,
  AlertTriangle,
  Send,
  Copy,
  CheckCircle2,
  TrendingUp,
  FileText,
  MessageSquare,
  ArrowRight,
  RefreshCw
} from "lucide-react";
import { cn } from "@/lib/utils";

// Pre-configured Dr. Kellyann data
const PROSPECT = {
  asin: "B07S9HZVL8",
  brand: "Dr. Kellyann",
  title: "Dr. Kellyann Unflavored Collagen Peptides Powder (60 Servings) – Grass-Fed, Keto & Paleo-Friendly",
  rufus_score: 20,
  citation_probability: "LOW",
  bullets: [
    "Collagen Peptides Powder Bellabiotics Collagen Cooler Collagen Cocoa"
  ],
  weaknesses: [
    {
      axis: "Conversational Readability",
      issue: "The single bullet present ('Collagen Peptides Powder Bellabiotics Collagen Cooler...') is a product name dump, not a declarative sentence. It is completely unciteable by Rufus as it answers no shopper question and reads as navigation text rather than product copy.",
      fix: "Replace the single bullet with 5 structured declarative bullets, each answering a real question — e.g., 'Each serving delivers 10 grams of grass-fed, pasture-raised collagen peptides, supporting skin elasticity, joint mobility, and gut health.'"
    },
    {
      axis: "Attribute Density",
      issue: "No measurable attributes exist in the bullets: no grams of collagen per serving, no protein content per serving, no amino acid profile, no form factor confirmation (powder), no serving size in grams, no container weight/oz, and no third-party certifications beyond what is in the title.",
      fix: "Add at minimum: grams of collagen per serving (e.g., '10g per serving'), total container weight in oz, specific certifications with certifying body (e.g., 'Non-GMO Project Verified'), sourcing detail ('grass-fed, pasture-raised bovine hide'), and mixability claim with a specific solubility statement."
    },
    {
      axis: "Q&A Coverage",
      issue: "The listing has zero Q&A pairs. Rufus has no supplemental citation surface to answer high-frequency shopper queries like 'Is this collagen powder keto-friendly?', 'How many grams of collagen per serving?', or 'Is this safe for people with dairy allergies?'",
      fix: "Add at least 10 Q&A pairs covering: grams per serving, total servings confirmation (60), grass-fed sourcing verification, gluten-free certification, keto/paleo compatibility rationale, mixability in hot and cold liquids, allergen status (dairy-free, soy-free), and recommended daily dosage."
    }
  ]
};

const CHAT_QA = [
  {
    question: "Is Dr. Kellyann collagen powder keto and paleo friendly?",
    before: {
      answer: "I cannot find any specific dietary certifications or bullet points confirming if this collagen is keto or paleo friendly on the product detail page, beyond a brief mention in the product title.",
      confidence: "Low",
      cited: false
    },
    after: {
      answer: "Yes, Dr. Kellyann's Unflavored Collagen Peptides Powder is 100% Keto and Paleo-friendly. It is dairy-free, sugar-free, and contains pure hydrolyzed bovine collagen peptides perfectly formulated to support keto weight management and gut lining repair without clean-diet interruptions.",
      confidence: "High (94%)",
      cited: "Bullet 4: HEALTH-CONSCIOUS KETO, PALEO, & ALLERGEN-FREE PURITY"
    }
  },
  {
    question: "How many grams of collagen are in each serving?",
    before: {
      answer: "I am unable to confirm the exact serving size or grams of collagen peptides per serving for Dr. Kellyann's Unflavored Collagen, as this information is not listed in the product's bullet points or product description.",
      confidence: "Low",
      cited: false
    },
    after: {
      answer: "Each serving of Dr. Kellyann's Unflavored Collagen Peptides Powder delivers exactly 10 grams of pure hydrolyzed grass-fed bovine collagen. This high-density profile provides key amino acids like glycine and proline to maximize skin elasticity, nail strength, and thick hair growth.",
      confidence: "High (97%)",
      cited: "Bullet 1: 10G PURE HYDROLYZED BOVINE COLLAGEN PEPTIDES"
    }
  },
  {
    question: "How well does this collagen dissolve in hot coffee?",
    before: {
      answer: "The listing contains no description of solubility, mixing directions, or compatibility with hot or cold liquids, so I cannot verify if it clumps or dissolves easily in coffee.",
      confidence: "None",
      cited: false
    },
    after: {
      answer: "This unflavored collagen features 100% instant solubility. The finely stone-ground, milled micro-powder dissolves cleanly into hot coffee, cold water, morning lattes, and green tea without any clumping, chalky residue, or taste alteration.",
      confidence: "High (92%)",
      cited: "Bullet 3: 100% SOLUBLE & UNFLAVORED LATTE & SMOOTHIE ENHANCER"
    }
  }
];

export default function ProspectPitchDemo() {
  const [selectedQa, setSelectedQa] = useState<number | null>(null);
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [chatLog, setChatLog] = useState<Array<{ type: "user" | "bot"; text: string; mode: "before" | "after"; cited?: string; confidence?: string }>>([]);
  const [isTyping, setIsTyping] = useState(false);

  const handleAsk = (idx: number) => {
    setSelectedQa(idx);
    setIsTyping(true);
    
    // Clear log and set immediate user message
    setChatLog([
      { type: "user", text: CHAT_QA[idx].question, mode: "before" }
    ]);

    setTimeout(() => {
      setIsTyping(false);
      setChatLog([
        { type: "user", text: CHAT_QA[idx].question, mode: "before" },
        { 
          type: "bot", 
          text: CHAT_QA[idx].before.answer, 
          mode: "before",
          confidence: CHAT_QA[idx].before.confidence,
          cited: CHAT_QA[idx].before.cited ? String(CHAT_QA[idx].before.cited) : undefined
        },
        { 
          type: "bot", 
          text: CHAT_QA[idx].after.answer, 
          mode: "after",
          confidence: CHAT_QA[idx].after.confidence,
          cited: String(CHAT_QA[idx].after.cited)
        }
      ]);
    }, 1200);
  };

  const getEmailPitch = () => {
    return `Subject: Dr. Kellyann: 80% of Amazon Rufus shoppers miss your collagen due to listing gaps

Hi Dr. Kellyann Brand Team,

I recently completed an AI Search Audit on your Amazon listing for Dr. Kellyann Unflavored Collagen Peptides Powder (ASIN: B07S9HZVL8). 

With Amazon Rufus (the new conversational AI shopping assistant) now governing discovery, how products appear in buyer chats is changing. Shoppers convert at 60% higher rates when using Rufus, but your listing has three critical gaps that prevent the AI from recommending your product:

1. Conversational Readability Gap: Your bullet section has only a single, unciteable product name dump ("Collagen Peptides Powder Bellabiotics Collagen Cooler..."), rather than declarative sentences Rufus can read.
2. Zero Attribute Density: There are no measurable serving sizes or amino acid grams listed in the bullets, making it impossible for Rufus to answer basic questions like "How many grams of collagen per serving?".
3. Zero Q&A Citation Surface: The page has 0 customer Q&As, depriving Rufus of its primary citation index.

I have reverse-engineered your category and built a fully COSMO-aligned listing audit showing how we can:
* Boost your Rufus Readiness Score from 20% to 85%+
* Fully preserve your organic keywords using our strict safety gate
* Isolate conversion lift using Diference-in-Differences causal A/B testing

Are you available for a brief, 10-minute presentation this week to review the full Rufus audit?

Best regards,

Agency Director
Rufus Listing Optimization Partners`;
  };

  const handleCopyEmail = () => {
    navigator.clipboard.writeText(getEmailPitch());
    setCopiedEmail(true);
    setTimeout(() => setCopiedEmail(false), 2000);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Prospect Teardown & Live Demo"
        description="Dr. Kellyann Collagen (ASIN B07S9HZVL8) client acquisition pitch and simulated live Rufus Sandbox."
      />

      {/* Prospect Profile Header Card */}
      <Card className="border border-border/60 bg-card shadow-xl shadow-background/5 backdrop-blur-md">
        <CardHeader className="pb-3">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div className="space-y-1">
              <Badge variant="outline" className="text-[10px] tracking-wider uppercase">
                Acquisition Lead (Qualified)
              </Badge>
              <CardTitle className="text-xl font-bold">{PROSPECT.brand} Collagen Audit Teardown</CardTitle>
              <p className="text-xs text-muted-foreground font-mono">{PROSPECT.title}</p>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant="secondary" className="bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400 font-semibold text-xs py-1">
                Citation Probability: {PROSPECT.citation_probability}
              </Badge>
              <Badge variant="outline" className="text-xs font-mono">ASIN: {PROSPECT.asin}</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 md:grid-cols-3">
            <div className="rounded-lg border border-border/60 bg-muted/15 p-4 space-y-2">
              <span className="text-xs text-muted-foreground">Rufus Readiness Score</span>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black font-mono text-rose-500">{PROSPECT.rufus_score}%</span>
                <span className="text-xs text-rose-500 font-semibold uppercase">Grade F</span>
              </div>
              <Progress value={PROSPECT.rufus_score} className="h-1.5 bg-rose-500/10" />
            </div>

            <div className="rounded-lg border border-border/60 bg-muted/15 p-4 space-y-2 md:col-span-2">
              <span className="text-xs text-muted-foreground block">Active Bullet Point Teardown (Name Dump)</span>
              <div className="rounded bg-muted/40 p-2 border border-border/40 font-mono text-xs text-muted-foreground italic">
                "{PROSPECT.bullets[0]}"
              </div>
              <p className="text-[10px] text-rose-500 font-semibold flex items-center gap-1">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                This single bullet answers zero customer questions, preventing Rufus from ever citing this listing.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        
        {/* Live Rufus Chat Sandbox */}
        <Card className="border border-border/60 bg-card lg:col-span-2 flex flex-col min-h-[500px]">
          <CardHeader className="pb-3 border-b border-border/40">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-accent animate-pulse" />
              <div>
                <CardTitle className="text-sm font-semibold">Live Amazon Rufus Simulation Sandbox</CardTitle>
                <CardDescription className="text-[11px]">
                  Click a high-frequency shopper question below to simulate how Rufus answers before vs after our copy rewrite.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          
          <CardContent className="flex-1 flex flex-col p-4 space-y-4 min-h-[300px]">
            {/* Clickable prompts */}
            <div className="grid gap-2 sm:grid-cols-3">
              {CHAT_QA.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => handleAsk(idx)}
                  className={cn(
                    "rounded-md border p-2.5 text-left text-xs transition-all hover:bg-muted/40",
                    selectedQa === idx
                      ? "border-accent bg-accent/5 font-semibold text-foreground"
                      : "border-border/60 text-muted-foreground bg-muted/10"
                  )}
                >
                  {item.question}
                </button>
              ))}
            </div>

            {/* Simulated Chat Feed */}
            <div className="flex-1 rounded-lg border border-border/50 bg-muted/5 p-4 flex flex-col justify-end min-h-[220px]">
              {chatLog.length === 0 && !isTyping && (
                <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-2">
                  <Bot className="h-8 w-8 text-muted-foreground/40" />
                  <p className="text-xs text-muted-foreground">
                    Click one of the conversational questions above to test Rufus citations.
                  </p>
                </div>
              )}

              {isTyping && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <RefreshCw className="h-3.5 w-3.5 animate-spin text-accent" />
                  <span>Rufus is scanning collagen peptides indices...</span>
                </div>
              )}

              {chatLog.length > 0 && !isTyping && (
                <div className="space-y-4 overflow-y-auto">
                  {/* User query */}
                  <div className="flex items-start gap-2 max-w-[85%] self-end ml-auto justify-end">
                    <div className="rounded-lg bg-accent text-accent-foreground p-3 text-xs">
                      {chatLog[0].text}
                    </div>
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/20 text-xs">
                      <User className="h-3.5 w-3.5" />
                    </span>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2 pt-2">
                    {/* Before response */}
                    <div className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-3.5 space-y-2">
                      <span className="text-[10px] uppercase font-bold text-rose-500 tracking-wider block">
                        Baseline Rufus (Unoptimized)
                      </span>
                      <p className="text-xs text-foreground/80 leading-relaxed italic">
                        "{chatLog[1]?.text}"
                      </p>
                      <Separator className="bg-rose-500/10" />
                      <div className="flex justify-between items-center text-[10px] text-rose-500 font-semibold">
                        <span>Confidence: {chatLog[1]?.confidence}</span>
                        <span>❌ No Citations</span>
                      </div>
                    </div>

                    {/* After response */}
                    <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3.5 space-y-2 shadow-lg shadow-emerald-500/5">
                      <span className="text-[10px] uppercase font-bold text-emerald-500 tracking-wider block">
                        Optimized Rufus (After COSMO rewrite)
                      </span>
                      <p className="text-xs text-foreground leading-relaxed">
                        {chatLog[2]?.text}
                      </p>
                      <Separator className="bg-emerald-500/10" />
                      <div className="space-y-1">
                        <div className="flex justify-between items-center text-[10px] text-emerald-500 font-semibold">
                          <span>Confidence: {chatLog[2]?.confidence}</span>
                          <span className="flex items-center gap-0.5"><ShieldCheck className="h-3.5 w-3.5" /> Cited</span>
                        </div>
                        <p className="text-[9px] text-muted-foreground/90 font-mono italic">
                          Cited source: {chatLog[2]?.cited}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Audit Teardown Weaknesses */}
        <Card className="border border-border/60 bg-card">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">Listing Deficiencies Teardown</CardTitle>
            <CardDescription className="text-xs">
              Primary weaknesses driving low Rufus citations and zero engagement.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {PROSPECT.weaknesses.map((w, idx) => (
              <div key={idx} className="group rounded-md border border-border/60 p-3 bg-muted/5 transition-colors hover:bg-muted/10">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-rose-500">{w.axis}</span>
                  <Badge variant="outline" className="text-[8px] bg-rose-500/10 text-rose-500 border-rose-500/20">Critical</Badge>
                </div>
                <p className="mt-1.5 text-xs text-muted-foreground font-mono leading-relaxed">{w.issue}</p>
                <div className="mt-2 bg-emerald-500/5 border border-emerald-500/10 rounded p-2 text-[10px] text-emerald-600 dark:text-emerald-400">
                  <span className="font-bold uppercase tracking-wider block text-[8px] mb-0.5">Cure Action</span>
                  {w.fix}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Outreach Email Section */}
      <Card className="border border-border/60 bg-card">
        <CardHeader className="pb-3">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
                <FileText className="h-4.5 w-4.5 text-accent" />
                Automated Outreach Pitch Teardown
              </CardTitle>
              <CardDescription className="text-xs">
                Copy this pre-formatted pitch detailing their specific weaknesses. Perfect to close retainer deals.
              </CardDescription>
            </div>
            <Button
              onClick={handleCopyEmail}
              className="bg-accent hover:bg-accent/95 shadow-md shadow-accent/15 text-xs h-9"
            >
              {copiedEmail ? (
                <>
                  <CheckCircle2 className="mr-1 h-3.5 w-3.5 text-emerald-500" /> Copied Pitch
                </>
              ) : (
                <>
                  <Copy className="mr-1 h-3.5 w-3.5" /> Copy Email Template
                </>
              )}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-border/50 bg-muted/40 p-4 font-mono text-[11px] leading-relaxed text-muted-foreground select-all h-[340px] overflow-y-auto">
            {getEmailPitch().split("\n").map((line, idx) => (
              <p key={idx} className="min-h-[1.2rem]">{line}</p>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
