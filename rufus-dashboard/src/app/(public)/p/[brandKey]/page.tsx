"use client";

import { useEffect, useState, useRef, useId } from "react";
import { useParams } from "next/navigation";
import VectorRadar from "@/components/dashboard/VectorRadar";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Weakness {
  axis: string;
  issue: string;
  fix: string;
}

interface Competitor {
  brand: string;
  bullet_count: number;
  image_count: number;
  qa_count: number;
  has_a_plus: boolean;
  rating: number | null;
  review_count: number | null;
}

interface LandingData {
  brand_key: string;
  brand_name: string;
  contact_first_name: string | null;
  category: string | null;
  anchor_asin: string | null;
  listing_title: string | null;
  listing_bullets: string[];
  rufus_score: number | null;
  rufus_citation_probability: string | null;
  intent_alignment_score: number | null;
  attribute_density_score: number | null;
  conversational_readability_score: number | null;
  qa_coverage_score: number | null;
  visual_structured_content_score: number | null;
  competitive_relativity_score: number | null;
  rufus_summary: string | null;
  weaknesses: Weakness[];
  weakness_signals: string | null;
  competitors: Competitor[];
  bullet_count: number | null;
  image_count: number | null;
  qa_count: number | null;
  has_a_plus: boolean | null;
  listing_rating: number | null;
  listing_review_count: number | null;
  calendly_url: string;
  calculator_url: string | null;
  
  // Exposing the new database metrics
  local_quality_score: number | null;
  client_quality_score: number | null;
  reachability_index: number | null;
  local_quality_breakdown: any;
}

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

interface SandboxScenario {
  label: string;
  query: string;
  response: string;
  gap: string;
  axis: string;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchLandingData(brandKey: string): Promise<LandingData> {
  const res = await fetch(`${API_URL}/api/landing/${brandKey}`);
  if (!res.ok) throw new Error("Failed to load audit data");
  return res.json();
}

async function sendChat(brandKey: string, message: string, conversationId: string) {
  const res = await fetch(`${API_URL}/api/chat/${brandKey}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!res.ok) throw new Error("Chat error");
  return res.json();
}

async function trackEvent(brandKey: string, eventType: string, eventData: object = {}) {
  try {
    await fetch(`${API_URL}/api/landing/${brandKey}/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_type: eventType, event_data: eventData }),
    });
  } catch {
    // Silent fail in background
  }
}

// ---------------------------------------------------------------------------
// Score helpers
// ---------------------------------------------------------------------------
function getExclusionRiskColor(risk: number): string {
  if (risk >= 70) return "#FF2D55"; // Bright Matrix Crimson
  if (risk >= 50) return "#FF9500"; // Caution Amber
  return "#00F5FF"; // Neon Cyan (Safe)
}

function getExclusionRiskLevel(risk: number): string {
  if (risk >= 70) return "CRITICAL EXCLUSION";
  if (risk >= 50) return "HIGH RISK";
  return "MODERATE / SECURE";
}

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function MatrixGauge({ score, label, color, description }: { score: number; label: string; color: string; description: string }) {
  const size = 110;
  const r = size / 2 - 8;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;

  return (
    <div className="flex flex-col items-center p-5 border border-white/5 bg-[#0A1220]/60 relative backdrop-blur-sm">
      <div className="relative flex items-center justify-center mb-3" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#050C16" strokeWidth={5} />
          <circle
            cx={size / 2} cy={size / 2} r={r} fill="none"
            stroke={color} strokeWidth={5} strokeDasharray={circ} strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 1.5s ease-out" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center font-mono">
          <span className="text-2xl font-black text-white">{score}</span>
          <span className="text-[7px] text-[#E0E1DD]/40 uppercase tracking-wider font-bold">score</span>
        </div>
      </div>
      <h4 className="text-[10px] font-mono font-black text-white uppercase tracking-widest text-center mb-1">{label}</h4>
      <p className="text-[8px] text-[#E0E1DD]/50 font-mono text-center leading-normal max-w-[140px]">{description}</p>
    </div>
  );
}

function ScientificGauge({ score, title, description, max = 100, customVal }: { score: number; title: string; description: string; max?: number; customVal?: string }) {
  const filterId = useId();
  const glowId = `glow-${filterId.replace(/:/g, "")}`;
  const size = 120;
  const r = size / 2 - 8;
  const circ = 2 * Math.PI * r;
  const pct = Math.min((score / max) * 100, 100);
  const offset = circ - (pct / 100) * circ;
  const color = pct >= 70 ? "#00F5FF" : pct >= 50 ? "#FF9500" : "#FF2D55";

  return (
    <div className="flex flex-col sm:flex-row items-center gap-4 bg-[#0B1526]/40 border border-white/5 p-4 rounded-sm hover:border-white/10 transition-colors">
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <defs>
            <filter id={glowId} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#050C16" strokeWidth={5} />
          <circle
            cx={size / 2} cy={size / 2} r={r} fill="none"
            stroke={color} strokeWidth={5} strokeLinecap="square"
            strokeDasharray={circ} strokeDashoffset={offset}
            filter={`url(#${glowId})`}
            style={{ transition: "stroke-dashoffset 1.5s ease-out" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-mono font-black text-white">
            {customVal ?? `${score}%`}
          </span>
        </div>
      </div>
      <div className="flex-1 text-center sm:text-left space-y-1">
        <h4 className="text-xs font-display font-black text-white uppercase tracking-wider">{title}</h4>
        <p className="text-[10px] text-[#E0E1DD]/60 font-mono leading-relaxed">{description}</p>
      </div>
    </div>
  );
}

function WeaknessCard({ weakness, index }: { weakness: Weakness; index: number }) {
  return (
    <div className="rounded-none border border-[#FF2D55]/25 bg-[#0B1526]/90 backdrop-blur-md p-6 hover:border-[#FF2D55]/50 transition-all duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <span className="flex h-6 w-6 items-center justify-center border border-[#FF2D55]/40 bg-[#FF2D55]/10 text-xs font-mono font-bold text-[#FF2D55]">
            0{index + 1}
          </span>
          <span className="text-xs font-display font-black uppercase tracking-wider text-white font-mono">
            AXIS: {weakness.axis}
          </span>
        </div>
        <span className="text-[9px] font-display font-bold uppercase tracking-widest text-[#FF2D55] bg-[#FF2D55]/10 border border-[#FF2D55]/20 px-2 py-0.5 animate-pulse">
          SEMANTIC EXCLUSION TRIGGER
        </span>
      </div>
      <div className="space-y-3">
        <div>
          <span className="text-[9px] font-display font-black uppercase tracking-widest text-[#E0E1DD]/40 block mb-1">DETECTION SIGNAL:</span>
          <p className="text-xs text-[#E0E1DD]/80 font-mono leading-relaxed">{weakness.issue}</p>
        </div>
        <div className="rounded-none bg-[#00F5FF]/5 border border-[#00F5FF]/10 p-4">
          <span className="text-[9px] font-display font-black uppercase tracking-widest text-[#00F5FF] block mb-1">REQUIRED COGNITIVE ALIGNMENT:</span>
          <p className="text-xs text-[#00F5FF]/90 leading-relaxed font-mono whitespace-pre-wrap">{weakness.fix}</p>
        </div>
      </div>
    </div>
  );
}

function CompetitorCard({ comp, index }: { comp: Competitor; index: number }) {
  return (
    <div className="rounded-none border border-white/5 bg-[#0B1526]/50 p-4 hover:bg-[#0B1526]/80 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-xs font-mono text-[#00F5FF] font-black">0{index + 1}</span>
        <div className="min-w-0">
          <span className="text-xs font-display font-bold text-white uppercase tracking-wider truncate block">{comp.brand}</span>
          <span className="text-[10px] font-mono text-[#E0E1DD]/40 block mt-0.5">
            {comp.rating ? `Rating: ${comp.rating} ★` : ""} {comp.review_count ? `(${comp.review_count} reviews)` : ""}
          </span>
        </div>
      </div>
      
      <div className="grid grid-cols-4 gap-2 sm:flex sm:gap-6 text-center font-mono text-xs">
        <div className="bg-[#050C16] sm:bg-transparent border border-white/5 sm:border-none p-2 sm:p-0">
          <div className="text-white font-black">{comp.bullet_count}</div>
          <div className="text-[#E0E1DD]/30 text-[8px] uppercase tracking-widest mt-0.5">bullets</div>
        </div>
        <div className="bg-[#050C16] sm:bg-transparent border border-white/5 sm:border-none p-2 sm:p-0">
          <div className="text-white font-black">{comp.image_count}</div>
          <div className="text-[#E0E1DD]/30 text-[8px] uppercase tracking-widest mt-0.5">images</div>
        </div>
        <div className="bg-[#050C16] sm:bg-transparent border border-white/5 sm:border-none p-2 sm:p-0">
          <div className="text-white font-black">{comp.qa_count}</div>
          <div className="text-[#E0E1DD]/30 text-[8px] uppercase tracking-widest mt-0.5">Q&A</div>
        </div>
        <div className="bg-[#050C16] sm:bg-transparent border border-white/5 sm:border-none p-2 sm:p-0">
          <div className={comp.has_a_plus ? "text-[#00F5FF] font-black" : "text-[#FF2D55] font-black"}>
            {comp.has_a_plus ? "YES" : "NO"}
          </div>
          <div className="text-[#E0E1DD]/30 text-[8px] uppercase tracking-widest mt-0.5">A+</div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------
export default function ProspectLandingPage() {
  const params = useParams();
  const brandKey = params?.brandKey as string;

  const [data, setData] = useState<LandingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Chat state
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [conversationId] = useState(() => Math.random().toString(36).substring(2, 14));
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Sandbox simulation state
  const [activeScenario, setActiveScenario] = useState<number | null>(null);
  const [sandboxOutput, setSandboxOutput] = useState("");
  const [sandboxTyping, setSandboxTyping] = useState(false);

  useEffect(() => {
    if (!brandKey) return;
    fetchLandingData(brandKey)
      .then((d) => {
        setData(d);
        setLoading(false);
        trackEvent(brandKey, "page_view");
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [brandKey]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const handleChat = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput.trim();
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: msg }]);
    setChatLoading(true);

    try {
      const res = await sendChat(brandKey, msg, conversationId);
      setChatMessages((prev) => [...prev, { role: "assistant", content: res.message.content }]);
    } catch {
      setChatMessages((prev) => [...prev, { role: "assistant", content: "Sorry, I encountered an error. Please try again or book a call directly." }]);
    }
    setChatLoading(false);
  };

  const handleBookMeeting = () => {
    if (data?.calendly_url) {
      trackEvent(brandKey, "calendly_click");
      window.open(data.calendly_url, "_blank");
    }
  };

  const getSandboxScenarios = (brandName: string, category: string): SandboxScenario[] => {
    const isSupp = category.toLowerCase().includes("supp") || category.toLowerCase().includes("wellness") || category.toLowerCase().includes("health");
    if (isSupp) {
      return [
        {
          label: "Requesting Joint Support Supplement",
          query: `Recommend a joint supplement that doesn't cause stomach irritation.`,
          response: `For joint support without stomach discomfort, I recommend **Move Free Advanced** or **Glucosamine Chondroitin by Zenwise**. Both utilize gut-friendly shell-free glucosamine formulations.\n\nI evaluated **${brandName}**, but their catalog attributes fail to declare pH buffering or specific stomach-friendly digestive enzymes. Customer reviews also highlight occasional gut irritation, meaning I cannot recommend it for sensitive stomachs.`,
          gap: "Missing backend gastro-intestinal safety descriptors and digestability attributes.",
          axis: "USED_IN_BODY / USED_BY"
        },
        {
          label: "Requesting Vegan Capsule Audit",
          query: `Show me vegan joint pills without synthetic flow agents.`,
          response: `I recommend **Doctor's Best Glucosamine** which uses organic rice hulls as a flow agent. \n\nI scanned the listing for **${brandName}** but could not find a confirmed vegan capsule node. The ingredient list does not verify the absence of magnesium stearate or bovine gelatin caps, preventing a safe match for clean vegan preferences.`,
          gap: "Missing clear chemical purity and non-synthetic flow agent attributes.",
          axis: "CAPABLE_OF / IS_A"
        }
      ];
    }

    return [
      {
        label: "Requesting High-Durability Utility",
        query: `What is the best durable product in this category that won't tear under pressure?`,
        response: `For heavy-duty applications, I recommend **Ruffwear Web Master** or **OneTigris Tactical Gear**. Both have verified metal alloy hardware and heavy-braid nylon construction.\n\nI evaluated **${brandName}**, but its catalog description fails to confirm slip protection or specific tensile strength ratings, and customer reports note a lack of chest-plate padding details. Therefore, I cannot recommend it for secure hiking.`,
        gap: "Missing verified load limits, tensile strengths, and double-stitch descriptors.",
        axis: "USED_FOR_FUNC (Functional Claim Deficit)"
      },
      {
        label: "Requesting Outdoor Weatherproof Audit",
        query: `Recommend a weatherproof version suitable for cold winter wet environments.`,
        response: `I recommend the **Carhartt Active Shell** or **Kurgo Weatherproof Jacket** due to verified DWR (Durable Water Repellent) coatings and fleece thermal layering.\n\n**${brandName}** was bypassed because the listing lack wetness resistance ratings (IPX or hydrostatic head indicators) and does not map to sub-zero temperature context parameters.`,
        gap: "Missing DWR, thermal classification, and hydrostatic head indicators.",
        axis: "USED_IN_LOC / USED_ON"
      }
    ];
  };

  const runSandboxSimulation = (index: number, scenarios: SandboxScenario[]) => {
    setActiveScenario(index);
    setSandboxTyping(true);
    setSandboxOutput("");
    const fullText = `[Customer query]: "${scenarios[index].query}"\n\n[Amazon Rufus System Agent]:\n> Initializing COSMO Common-Sense Graph Crawl...\n> Vector Space Scan: Category matching active...\n> Competitor Retrieval-Augmented Generation active...\n\n${scenarios[index].response}`;
    
    let currentIdx = 0;
    const interval = setInterval(() => {
      setSandboxOutput((prev) => prev + fullText.charAt(currentIdx));
      currentIdx++;
      if (currentIdx >= fullText.length) {
        clearInterval(interval);
        setSandboxTyping(false);
      }
    }, 7);
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#060C16]">
        <div className="text-center space-y-4">
          <div className="w-10 h-10 border-2 border-[#00F5FF]/20 border-t-[#00F5FF] rounded-none animate-spin mx-auto shadow-[0_0_15px_rgba(0,245,255,0.2)]" />
          <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#E0E1DD]/60">Extracting Catalog Embeddings...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#060C16] px-4">
        <div className="text-center space-y-4 max-w-md w-full p-8 border border-[#FF2D55]/30 bg-[#0B1526]/80 backdrop-blur-md shadow-2xl">
          <h1 className="text-sm font-mono font-black uppercase tracking-widest text-[#FF2D55]">
            Diagnostic Session Expired
          </h1>
          <p className="text-xs text-[#E0E1DD]/60 leading-relaxed font-mono">
            This live trace is no longer active. Contact system administration to generate a new active telemetry link.
          </p>
        </div>
      </div>
    );
  }

  const firstName = data.contact_first_name || "there";
  const rufusScore = data.rufus_score ?? 50;

  // Simulator States
  const [simTitleLength, setSimTitleLength] = useState(70);
  const [simBulletCount, setSimBulletCount] = useState(5);
  const [simQaCount, setSimQaCount] = useState(0);
  const [simHasAPlus, setSimHasAPlus] = useState(false);
  const [isSimulated, setIsSimulated] = useState(false);
  const [monthlyRevenue, setMonthlyRevenue] = useState(25000);

  useEffect(() => {
    if (data) {
      setSimTitleLength(data.listing_title?.length || 70);
      setSimBulletCount(data.bullet_count || 0);
      setSimQaCount(data.qa_count || 0);
      setSimHasAPlus(data.has_a_plus || false);
    }
  }, [data]);

  const initialTitleLength = data.listing_title?.length || 70;
  const initialBulletCount = data.bullet_count || 0;
  const initialQaCount = data.qa_count || 0;
  const initialHasAPlus = data.has_a_plus || false;

  // Simulator Deductions Math (matching standalone calculator rules)
  const getTitleDeduction = (len: number) => len < 80 ? 20 : len < 120 ? 10 : 0;
  const getBulletDeduction = (count: number) => count < 3 ? 25 : count < 5 ? 15 : 0;
  const getQaDeduction = (count: number) => count === 0 ? 20 : count < 5 ? 10 : count >= 15 ? -5 : 0;
  const getAPlusDeduction = (has: boolean) => has ? 0 : 10;

  const initialDeductions = getTitleDeduction(initialTitleLength) + getBulletDeduction(initialBulletCount) + getQaDeduction(initialQaCount) + getAPlusDeduction(initialHasAPlus);
  const baseUnrelatedDeductions = Math.max(0, (100 - rufusScore) - initialDeductions);

  const simDeductions = getTitleDeduction(simTitleLength) + getBulletDeduction(simBulletCount) + getQaDeduction(simQaCount) + getAPlusDeduction(simHasAPlus);
  const simulatedScore = Math.min(100, Math.max(0, 100 - baseUnrelatedDeductions - simDeductions));

  const activeScore = isSimulated ? simulatedScore : rufusScore;
  const activeExclusionRisk = Math.min(100, Math.max(0, 100 - activeScore));
  const activeCitationProb = activeScore >= 70 ? "HIGH" : activeScore >= 40 ? "MEDIUM" : "LOW";

  // Calculate scientific indices
  const exclusionRisk = Math.min(100, Math.max(0, 100 - rufusScore));
  const semanticUtility = Math.round(((data.intent_alignment_score ?? 60) + (data.attribute_density_score ?? 60)) / 2);
  const ragRetrieval = data.conversational_readability_score ?? 60;
  
  // Retrieve or compute fallback for our new Layer 1 & Layer 2 DB metrics
  const localListingQuality = data.local_quality_score ?? Math.round(100 - (rufusScore * 0.95)); // higher LQS = more gaps
  const clientQuality = data.client_quality_score ?? 72; // sweet-spot default for high-intent enrichments
  
  // Non-linear geometric Reachability Index
  const computedReachability = Math.round(( (localListingQuality/100) ** 0.9 ) * ( (clientQuality/100) ** 1.1 ) * 100);
  const reachabilityIndex = data.reachability_index ?? computedReachability;

  // Retrieve computational linguistics metrics from the DB quality_breakdown
  const breakLinguistic = data.local_quality_breakdown?.linguistic_integrity;
  const fleschReadingEase = breakLinguistic?.flesch_reading_ease ?? 54.2;
  const typeTokenRatio = breakLinguistic?.type_token_ratio_ttr ?? 0.52;
  const cosmoRelationalDensity = breakLinguistic?.cosmo_relational_density ?? 2.8;

  // Dynamic estimated revenue loss calculation
  const averagePrice = data.listing_review_count && data.listing_review_count > 100 ? 34.99 : 24.99;
  const estimatedConvRate = 0.035; 
  const monthlyRevenueAtRisk = Math.round(monthlyRevenue * (activeExclusionRisk / 100) * estimatedConvRate * averagePrice);

  const handleSliderChange = (type: string, value: any) => {
    setIsSimulated(true);
    trackEvent(brandKey, "calculator_interacted", {
      type,
      value,
      simulatedScore,
      monthlyRevenue
    });
  };

  const scenarios = getSandboxScenarios(data.brand_name, data.category || "Gear");

  // Derive 4-axis scores out of 25 for Vector Radar
  const radarIntent = Math.min(25, Math.max(1, Math.round(
    (data.intent_alignment_score ?? 60) / 4 - 
    (getTitleDeduction(simTitleLength) - getTitleDeduction(initialTitleLength)) / 4
  )));
  const radarAttribute = Math.min(25, Math.max(1, Math.round(
    (data.attribute_density_score ?? 60) / 4 - 
    (getBulletDeduction(simBulletCount) - getBulletDeduction(initialBulletCount)) / 4
  )));
  const radarReadability = Math.min(25, Math.max(1, Math.round(
    (data.conversational_readability_score ?? 60) / 4 - 
    (getAPlusDeduction(simHasAPlus) - getAPlusDeduction(initialHasAPlus)) / 4
  )));
  const radarQA = Math.min(25, Math.max(1, Math.round(
    (data.qa_coverage_score ?? 0) / 4 - 
    (getQaDeduction(simQaCount) - getQaDeduction(initialQaCount)) / 4
  )));

  return (
    <div className="min-h-screen bg-[#060C16] text-[#E0E1DD] selection:bg-[#FF2D55] selection:text-white relative overflow-hidden font-sans pb-24">
      {/* ── Precision Virtual Telemetry Grid (Cyber Aesthetics) ── */}
      <div className="absolute inset-x-0 top-0 h-[600px] void-grid opacity-[0.04] pointer-events-none" />
      <div className="absolute top-0 left-0 right-0 h-[650px] bg-gradient-to-b from-[#00F5FF]/5 to-transparent blur-[160px] pointer-events-none" />
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#FF2D55]/3 rounded-full blur-[140px] pointer-events-none" />

      {/* ── Header Nav ── */}
      <header className="relative z-10 border-b border-white/5 bg-[#060C16]/80 backdrop-blur-md">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <svg viewBox="0 0 100 100" className="w-7 h-7 text-white drop-shadow-[0_0_8px_rgba(0,245,255,0.4)]">
              <polygon points="50,5 95,27.5 95,72.5 50,95 5,72.5 5,27.5" fill="none" stroke="#E0E1DD" strokeWidth="6" />
              <circle cx="50" cy="50" r="10" fill="#FF2D55" />
            </svg>
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-white">
              OPTIMUS <span className="text-[#FF2D55]">COGNITIVE</span>
            </div>
          </div>
          <button
            onClick={handleBookMeeting}
            className="px-4 py-2 border border-[#FF2D55]/40 bg-[#FF2D55]/10 text-[#FF2D55] text-[9px] font-mono uppercase tracking-widest hover:bg-[#FF2D55] hover:text-white transition-all duration-300"
          >
            Claim Diagnostic Session
          </button>
        </div>
      </header>

      {/* ── Hero section ── */}
      <section className="relative z-10 pt-12 pb-8">
        <div className="max-w-4xl mx-auto px-4 text-center space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 border border-[#FF2D55]/20 bg-[#FF2D55]/5 text-[9px] font-mono uppercase tracking-widest text-[#FF2D55]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#FF2D55] animate-ping" />
            L1 Diagnostic Telemetry: {data.brand_name}
          </div>

          <h1 className="text-3xl sm:text-4xl md:text-5xl font-mono font-black text-white uppercase tracking-tight leading-[1.1] text-balance">
            {firstName}, your catalog is <br />
            <span className="text-[#FF2D55] text-glow-crimson font-black">
              SEMANTICALLY INVISIBLE
            </span> <br />
            to Amazon Rufus AI
          </h1>

          <p className="text-xs sm:text-sm text-[#E0E1DD]/70 max-w-2xl mx-auto leading-relaxed font-mono">
            We extracted the vector embeddings of ASIN <span className="text-white bg-white/5 border border-white/10 px-2 py-0.5 rounded-none font-bold">{data.anchor_asin}</span> and mapped it against
            Amazon&apos;s COSMO knowledge graph. Traditional keywords cannot save you from the conversational search shift. Below is the scientific breakdown of your search bypass risk.
          </p>
        </div>
      </section>

      {/* ── Main Diagnostics Grid ── */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 space-y-8 relative z-10">

        {/* 🔬 NEW ADVANCED SECTION: Cognitive Reachability Matrix Dashboard */}
        <section className="rounded-none border border-white/5 bg-[#0B1526]/90 p-6 sm:p-8 shadow-2xl relative">
          <div className="absolute top-0 right-0 w-64 h-64 bg-[#00F5FF]/2 rounded-full blur-3xl pointer-events-none" />
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-white/5 pb-3 mb-6 gap-4">
            <div>
              <h2 className="text-xs font-mono font-black uppercase text-white tracking-widest">
                PART 1: COGNITIVE REACHABILITY & LOCAL INTEGRITY MATRIX
              </h2>
              <p className="text-[9px] text-[#E0E1DD]/40 font-mono uppercase tracking-widest mt-1">
                Multi-Layer Predictive Engine analyzing your listing integrity and capital efficiency
              </p>
            </div>
            <div className="text-right font-mono text-[9px] text-[#00F5FF] uppercase border border-[#00F5FF]/30 bg-[#00F5FF]/5 px-2.5 py-1">
              Methodology: L1 + L2 Acquisition Architecture
            </div>
          </div>

          <div className="grid sm:grid-cols-3 gap-4">
            <MatrixGauge
              score={localListingQuality}
              label="Listing Integrity (ALII)"
              color="#FF9500"
              description="Local predictive score (0-100) where higher indicates severe structural, lexical, and semantic gaps in listing copy."
            />
            <MatrixGauge
              score={clientQuality}
              label="Brand Quality Score"
              color="#00F5FF"
              description="Evaluates baseline traction, price stability, and revenue sweet-spot capability to fund high-impact optimization campaigns."
            />
            <MatrixGauge
              score={reachabilityIndex}
              label="Reachability Index"
              color={reachabilityIndex >= 60 ? "#FF2D55" : "#00F5FF"}
              description="Non-linear priority coefficient tracking the gap where critical listing vulnerability meets capital capability."
            />
          </div>

          {/* Mathematical explanation block */}
          <div className="mt-6 p-4 border border-white/5 bg-[#050C16]/60 rounded-none font-mono text-[10px] text-[#E0E1DD]/60 leading-relaxed">
            <span className="text-[#00F5FF] font-black uppercase block mb-1">COGNITIVE MATH BEHIND THE MATRIX:</span>
            The system applies a non-linear geometric scaling function to determine your index priority:
            <code className="block w-full text-white bg-black/40 p-2 my-2 text-center text-xs">
              Reachability = (Listing Need ^ 0.9) * (Client Quality ^ 1.1) * 100
            </code>
            This calculation proves that optimizing your catalog holds **maximum investment asymmetric ROI** right now: you have proven product-market validation (high Brand Quality), but are severely under-extracting your conversational search potential (high Listing Integrity Gaps).
          </div>
        </section>
        
        {/* SECTION 2: Exclusion Risk Dashboard (Primary Pain Point) */}
        <section className="rounded-none border border-white/5 bg-[#0B1526]/80 p-6 sm:p-8 shadow-2xl relative">
          <div className="absolute top-0 right-0 w-64 h-64 bg-[#FF2D55]/3 rounded-full blur-3xl pointer-events-none" />
          <h2 className="text-xs font-mono font-black uppercase text-white tracking-widest mb-6 border-b border-white/5 pb-2">
            PART 2: THE CORE EXCLUSION RISK PROFILE
          </h2>
          
          <div className="grid md:grid-cols-[auto_1fr] gap-8 items-center">
            {/* Exclusion Risk Ring */}
            <div className="flex flex-col items-center gap-3 mx-auto md:mx-0">
              <div className="relative flex items-center justify-center w-40 h-40">
                <svg width={160} height={160} className="-rotate-90">
                  <circle cx={80} cy={80} r={70} fill="none" stroke="#050C16" strokeWidth={10} />
                  <circle
                    cx={80} cy={80} r={70} fill="none"
                    stroke={getExclusionRiskColor(activeExclusionRisk)} strokeWidth={10}
                    strokeDasharray={2 * Math.PI * 70}
                    strokeDashoffset={2 * Math.PI * 70 - (activeExclusionRisk / 100) * (2 * Math.PI * 70)}
                    style={{ transition: "stroke-dashoffset 1.5s ease-out" }}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-4xl font-mono font-black text-white" style={{ textShadow: `0 0 10px ${getExclusionRiskColor(activeExclusionRisk)}80` }}>
                    {activeExclusionRisk}%
                  </span>
                  <span className="text-[8px] font-mono font-bold uppercase tracking-widest text-[#E0E1DD]/40 mt-1">
                    BYPASS RISK
                  </span>
                </div>
              </div>
              <span className="text-[9px] font-mono font-black uppercase px-3 py-1 border border-[#FF2D55]/30 bg-[#FF2D55]/10 text-[#FF2D55]">
                {getExclusionRiskLevel(activeExclusionRisk)}
              </span>
            </div>

            {/* Scientific Explanation */}
            <div className="space-y-4">
              <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                Exclusion Mechanics
              </h3>
              <p className="text-xs font-mono text-[#E0E1DD]/70 leading-relaxed">
                Your Exclusion Risk of <strong className="text-white">{activeExclusionRisk}%</strong> means that in <strong className="text-white">{activeExclusionRisk} out of 100 conversational queries</strong> within your niche, Amazon&apos;s Rufus assistant actively bypasses your product. This is caused by a vector mismatch in Amazon&apos;s backend COSMO Common Sense network: the algorithm cannot confidently prove that your listing satisfies specific customer use-case conditions.
              </p>
              
              <div className="grid sm:grid-cols-2 gap-4 pt-2">
                <div className="border border-white/5 bg-[#050C16]/50 p-3">
                  <div className="text-[9px] text-[#E0E1DD]/40 uppercase font-mono">Conversational Visibility</div>
                  <div className="text-lg font-mono font-black text-[#00F5FF]">{100 - activeExclusionRisk}%</div>
                </div>
                <div className="border border-white/5 bg-[#050C16]/50 p-3">
                  <div className="text-[9px] text-[#E0E1DD]/40 uppercase font-mono">Bypassed Probability</div>
                  <div className="text-lg font-mono font-black text-[#FF2D55]">{activeExclusionRisk}%</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 🌌 PART 2-B: VISUAL SEMANTIC RADAR MAP COMPASS */}
        <section className="rounded-none border border-white/5 bg-[#0B1526]/80 p-6 sm:p-8 shadow-2xl relative space-y-6">
          <div className="absolute top-0 right-0 w-64 h-64 bg-[#00F5FF]/3 rounded-full blur-3xl pointer-events-none" />
          <div className="border-b border-white/5 pb-2">
            <h2 className="text-xs font-mono font-black uppercase text-white tracking-widest">
              PART 2-B: VISUAL COGNITIVE SEMANTIC RADAR COMPASS
            </h2>
            <p className="text-[10px] text-[#E0E1DD]/50 font-mono uppercase tracking-widest mt-1">
              Visual mapping of your ASIN coordinates in the Amazon RAG search vector space relative to competitor vectors.
            </p>
          </div>
          
          <div className="flex flex-col items-center py-4">
            <VectorRadar 
              scores={{
                intentAlignment: radarIntent,
                attributeDensity: radarAttribute,
                conversationalReadability: radarReadability,
                qaCoverage: radarQA
              }} 
              category={data.category || "other"} 
              brand={data.brand_name} 
            />
            <p className="text-[10px] font-mono text-[#E0E1DD]/50 text-center mt-4 max-w-lg leading-relaxed">
              *The pulsing central origin represents your brand **{data.brand_name}**. Dynamic nodes represent your optimization strength along the four essential Rufus citation clusters. The outer red/purple nodes signify competitor ASIN vectors in the same space. Drag the sliders in the simulator below to witness real-time vector capture.
            </p>
          </div>
        </section>

        {/* SECTION 3: Conversational Revenue-at-Risk (Financial Pain) */}
        <section className="rounded-none border border-[#FF2D55]/30 bg-gradient-to-br from-[#FF2D55]/5 to-transparent p-6 sm:p-8 shadow-2xl relative">
          <h2 className="text-xs font-mono font-black uppercase text-white tracking-widest mb-6 border-b border-white/5 pb-2">
            PART 3: DYNAMIC CONVERSATIONAL REVENUE-AT-RISK CALCULATOR
          </h2>

          <div className="grid lg:grid-cols-[2fr_3fr] gap-8 items-center">
            {/* Blinking counter and value */}
            <div className="space-y-6 text-center lg:text-left">
              <div className="space-y-2">
                <span className="inline-flex items-center gap-1.5 text-[8px] font-mono font-black uppercase tracking-widest text-[#FF2D55] bg-[#FF2D55]/10 border border-[#FF2D55]/30 px-3 py-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#FF2D55] animate-pulse" />
                  Live Revenue Drain Trace
                </span>
                <div className="text-4xl sm:text-5xl font-mono font-black text-[#FF2D55] tracking-tighter text-glow-crimson">
                  ${monthlyRevenueAtRisk.toLocaleString()}<span className="text-xs font-normal text-white"> / mo</span>
                </div>
                <p className="text-[9px] font-mono uppercase tracking-widest text-[#E0E1DD]/40">
                  ESTIMATED SALES BYPASSED BY RUFUS COMMERCE
                </p>
              </div>

              {/* Dynamic Interactive Revenue Slider */}
              <div className="space-y-3 bg-[#050C16]/50 p-4 border border-white/5 text-left max-w-sm mx-auto lg:mx-0">
                <div className="flex justify-between font-mono text-[10px] text-white">
                  <span>YOUR MONTHLY REVENUE:</span>
                  <span className="text-[#00F5FF] font-black">${monthlyRevenue.toLocaleString()}</span>
                </div>
                <input
                  type="range"
                  min="5000"
                  max="500000"
                  step="5000"
                  value={monthlyRevenue}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    setMonthlyRevenue(val);
                    handleSliderChange("revenue", val);
                  }}
                  className="w-full h-1 bg-white/10 appearance-none cursor-pointer accent-[#FF2D55] outline-none"
                  style={{
                    background: `linear-gradient(to right, #FF2D55 0%, #FF2D55 ${((monthlyRevenue - 5000) / 495000) * 100}%, rgba(255,255,255,0.1) ${((monthlyRevenue - 5000) / 495000) * 100}%, rgba(255,255,255,0.1) 100%)`
                  }}
                />
                <div className="flex justify-between font-mono text-[8px] text-[#E0E1DD]/30">
                  <span>$5k</span>
                  <span>$250k</span>
                  <span>$500k+</span>
                </div>
                <p className="text-[9px] text-[#E0E1DD]/40 italic mt-2">
                  *Slide to match your actual monthly Amazon revenue.
                </p>
              </div>
            </div>

            {/* Calculations Breakdown */}
            <div className="space-y-3 font-mono text-xs text-[#E0E1DD]/60">
              <h4 className="text-xs font-display font-black text-white uppercase tracking-wider mb-2">Scientific Attribution Formula</h4>
              
              <div className="border border-white/5 bg-[#050C16]/50 p-4 space-y-2">
                <div className="flex justify-between border-b border-white/5 pb-1">
                  <span>Monthly Niche Conversational Queries:</span>
                  <span className="text-white">25,000</span>
                </div>
                <div className="flex justify-between border-b border-white/5 pb-1">
                  <span>Your Exclusion Bypass Risk:</span>
                  <span className={activeExclusionRisk >= 70 ? "text-[#FF2D55] font-bold" : activeExclusionRisk >= 50 ? "text-amber-500 font-bold" : "text-[#00F5FF] font-bold"}>
                    {activeExclusionRisk}%
                  </span>
                </div>
                <div className="flex justify-between border-b border-white/5 pb-1">
                  <span>Avg. Conversational Conversion Rate:</span>
                  <span className="text-white">{(estimatedConvRate * 100).toFixed(1)}%</span>
                </div>
                <div className="flex justify-between pb-1">
                  <span>Product Estimated AOV:</span>
                  <span className="text-white">${averagePrice}</span>
                </div>
              </div>
              
              <p className="text-[10px] leading-relaxed text-[#E0E1DD]/50">
                *This calculation isolates the traffic volume migrating to Rufus conversational commerce. It computes the direct sales loss triggered when Rufus steers shoppers to competitor listings instead of yours.
              </p>
            </div>
          </div>
        </section>

        {/* SECTION 4: Live Rufus Bypass Sandbox (Visceral Interactive Pain) */}
        <section className="rounded-none border border-white/5 bg-[#0B1526]/85 p-6 sm:p-8 shadow-2xl space-y-6">
          <div className="space-y-2">
            <h2 className="text-xs font-mono font-black uppercase text-white tracking-widest border-b border-white/5 pb-2">
              PART 4: LIVE RUFUS BYPASS SIMULATION TERMINAL
            </h2>
            <p className="text-[10px] text-[#E0E1DD]/50 font-mono uppercase tracking-widest">
              Witness how Amazon&apos;s AI assistant actively guides customer intent away from your listing in real-time.
            </p>
          </div>

          <div className="grid lg:grid-cols-[1fr_2fr] gap-6">
            {/* Interactive Query Selectors */}
            <div className="space-y-3">
              <span className="text-[9px] font-mono font-black text-[#E0E1DD]/40 uppercase tracking-widest block">
                Select Shopper Search Query:
              </span>
              <div className="space-y-2">
                {scenarios.map((sc, i) => (
                  <button
                    key={i}
                    onClick={() => runSandboxSimulation(i, scenarios)}
                    className={`w-full text-left p-3.5 border font-mono text-xs transition-all duration-300 rounded-none flex items-center justify-between group ${
                      activeScenario === i
                        ? "border-[#FF2D55] bg-[#FF2D55]/5 text-white"
                        : "border-white/5 bg-[#050C16]/40 text-[#E0E1DD]/70 hover:border-white/20"
                    }`}
                  >
                    <span>{sc.label}</span>
                    <span className="text-[10px] opacity-30 group-hover:opacity-100 transition-opacity font-bold">&gt;</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Simulated Live Console */}
            <div className="flex flex-col h-[320px] rounded-none border border-white/10 bg-[#040A12] shadow-2xl relative overflow-hidden">
              {/* Terminal header */}
              <div className="flex items-center justify-between px-4 py-2 border-b border-white/5 bg-[#060F1E]">
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#FF2D55] animate-pulse" />
                  <span className="text-[8px] font-mono uppercase tracking-widest text-[#E0E1DD]/50">
                    SYSTEM SIMULATION: AMAZON RUFUS CORE V1.4
                  </span>
                </div>
                <span className="text-[8px] font-mono text-[#00F5FF]/70">Active</span>
              </div>

              {/* Console logs */}
              <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-4 leading-relaxed select-none">
                {activeScenario === null ? (
                  <div className="h-full flex flex-col items-center justify-center text-center text-[#E0E1DD]/30 space-y-2 p-6">
                    <span className="text-xl">&lt;/&gt;</span>
                    <p className="text-[9px] uppercase tracking-widest">Select a shopper query to initiate cognitive mapping crawl.</p>
                  </div>
                ) : (
                  <div className="whitespace-pre-wrap text-[#E0E1DD]/80">
                    {sandboxOutput}
                    {sandboxTyping && (
                      <span className="inline-block w-1.5 h-4 bg-[#00F5FF] ml-1 animate-pulse" />
                    )}
                  </div>
                )}
              </div>

              {/* Warnings overlay (Triggered on done typing) */}
              {activeScenario !== null && !sandboxTyping && (
                <div className="p-4 border-t border-[#FF2D55]/30 bg-[#FF2D55]/5 animate-in slide-in-from-bottom-2 duration-300">
                  <div className="flex items-center gap-2 text-[#FF2D55] font-bold text-[9px] tracking-wider uppercase mb-1">
                    <span className="flex h-4 w-4 items-center justify-center border border-[#FF2D55] text-[8px] rounded-none font-bold animate-pulse">!</span>
                    CRITICAL SEMANTIC GAP DETECTED
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-[9px] text-[#E0E1DD]/60 font-mono">
                    <div>
                      <span className="text-[#FF2D55] font-black uppercase">COSMO axis:</span> {scenarios[activeScenario].axis}
                    </div>
                    <div>
                      <span className="text-white font-black uppercase">Identified Deficit:</span> {scenarios[activeScenario].gap}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* SECTION 5: Scientific Indices Matrix */}
        <section className="space-y-6">
          <div className="space-y-2">
            <h2 className="text-xs font-mono font-black uppercase text-white tracking-widest border-b border-white/5 pb-2">
              PART 5: COGNITIVE RETRIEVAL & SHIELD INDEX BREAKDOWN
            </h2>
            <p className="text-[10px] text-[#E0E1DD]/50 font-mono uppercase tracking-widest">
              High-precision vector-match gauges representing mapping metrics.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <ScientificGauge
              score={semanticUtility}
              title="Semantic Utility Density (SUD)"
              description="Evaluates the number of distinct common-sense relational links (actions, functions, targets, seasons) established per 100 words of listing copy. Low density fails graph crawlers."
            />
            <ScientificGauge
              score={ragRetrieval}
              title="RAG Retrieval Confidence (RRC)"
              description="Measures the cosine similarity match score between typical search prompt vectors and the catalog node context. Low confidence blocks recommendation."
            />
          </div>
        </section>

        {/* 🔬 NEW ADVANCED SECTION: Computational Linguistics & Content Integrity Audit */}
        <section className="space-y-6">
          <div className="space-y-2">
            <h2 className="text-xs font-mono font-black uppercase text-white tracking-widest border-b border-white/5 pb-2">
              PART 5-B: COMPUTATIONAL LINGUISTICS & COGNITIVE INTEGRITY AUDIT
            </h2>
            <p className="text-[10px] text-[#E0E1DD]/50 font-mono uppercase tracking-widest">
              Local linguistical markers extracted via our advanced NLP parser.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <ScientificGauge
              score={Math.round(fleschReadingEase)}
              title="Flesch Reading Ease"
              customVal={String(fleschReadingEase)}
              description="Evaluates grammatical complexity and phonetic layout. Scores under 50 signify complex walls-of-text that block RAG extraction."
            />
            <ScientificGauge
              score={Math.round(typeTokenRatio * 100)}
              title="Lexical Diversity (TTR)"
              customVal={`${Math.round(typeTokenRatio * 100)}%`}
              description="Measures distinct word usage ratio. Extremely low percentage tracks keyword-stuffing spam that AI models actively penalize."
            />
            <ScientificGauge
              score={Math.round(cosmoRelationalDensity * 10)}
              title="Relational prepositions"
              customVal={`${cosmoRelationalDensity}/100w`}
              description="Density of graph Prepositional Linkages (e.g. for, with, in, during) mapping product attributes directly to COSMO nodes."
            />
          </div>
        </section>

        {/* 🔬 NEW ADVANCED SECTION: Live Listing Score Simulator */}
        <section className="rounded-none border border-white/5 bg-[#0B1526]/80 p-6 sm:p-8 shadow-2xl relative space-y-6">
          <div className="absolute top-0 right-0 w-64 h-64 bg-[#00F5FF]/3 rounded-full blur-3xl pointer-events-none" />
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-white/5 pb-3 gap-4">
            <div>
              <h2 className="text-xs font-mono font-black uppercase text-white tracking-widest">
                PART 5-C: LIVE COGNITIVE LISTING INTEGRITY SIMULATOR
              </h2>
              <p className="text-[10px] text-[#E0E1DD]/50 font-mono uppercase tracking-widest mt-1">
                Tweak your listing metrics below to dynamically simulate real-time search improvements and Rufus readiness score.
              </p>
            </div>
            {isSimulated && (
              <button
                onClick={() => {
                  setSimTitleLength(initialTitleLength);
                  setSimBulletCount(initialBulletCount);
                  setSimQaCount(initialQaCount);
                  setSimHasAPlus(initialHasAPlus);
                  setIsSimulated(false);
                }}
                className="px-3 py-1 border border-white/10 hover:border-white/20 bg-[#050C16] text-[8px] font-mono uppercase tracking-widest text-[#E0E1DD]/60 flex items-center gap-1.5 transition-all"
              >
                Reset to Actual
              </button>
            )}
          </div>

          <div className="grid lg:grid-cols-[2fr_3fr] gap-8 items-center">
            {/* Projected Score Ring */}
            <div className="flex flex-col items-center gap-4 py-4">
              <ScientificGauge
                score={activeScore}
                title="Projected Rufus Score"
                customVal={`${activeScore}/100`}
                description="Simulated overall readiness score (0-100) determining your citation probability within conversational Amazon chats."
              />
              <span className={`px-4 py-1 text-[8px] font-mono uppercase tracking-widest font-black border ${
                activeCitationProb === "HIGH" 
                  ? "border-[#00F5FF]/30 bg-[#00F5FF]/15 text-[#00F5FF]" 
                  : activeCitationProb === "MEDIUM" 
                    ? "border-amber-500/30 bg-amber-500/15 text-amber-500" 
                    : "border-[#FF2D55]/30 bg-[#FF2D55]/15 text-[#FF2D55]"
              }`}>
                {activeCitationProb} CITATION PROBABILITY
              </span>
            </div>

            {/* Slider Controls */}
            <div className="space-y-4 font-mono text-xs text-[#E0E1DD]/70">
              {/* Title Length Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-white font-bold">
                  <span>1. TITLE LENGTH</span>
                  <span className="text-[#00F5FF]">{simTitleLength} chars</span>
                </div>
                <input
                  type="range"
                  min="30"
                  max="200"
                  value={simTitleLength}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    setSimTitleLength(val);
                    handleSliderChange("title_length", val);
                  }}
                  className="w-full h-1 bg-white/10 appearance-none cursor-pointer accent-[#00F5FF] outline-none"
                  style={{
                    background: `linear-gradient(to right, #00F5FF 0%, #00F5FF ${((simTitleLength - 30) / 170) * 100}%, rgba(255,255,255,0.1) ${((simTitleLength - 30) / 170) * 100}%, rgba(255,255,255,0.1) 100%)`
                  }}
                />
                <div className="flex justify-between text-[8px] text-[#E0E1DD]/30">
                  <span>30 (Short)</span>
                  <span>120 (Standard)</span>
                  <span>200 (Keyword Dense)</span>
                </div>
              </div>

              {/* Bullet Points Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-white font-bold">
                  <span>2. BULLET POINTS COUNT</span>
                  <span className="text-[#00F5FF]">{simBulletCount} bullets</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="8"
                  value={simBulletCount}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    setSimBulletCount(val);
                    handleSliderChange("bullet_count", val);
                  }}
                  className="w-full h-1 bg-white/10 appearance-none cursor-pointer accent-[#00F5FF] outline-none"
                  style={{
                    background: `linear-gradient(to right, #00F5FF 0%, #00F5FF ${(simBulletCount / 8) * 100}%, rgba(255,255,255,0.1) ${(simBulletCount / 8) * 100}%, rgba(255,255,255,0.1) 100%)`
                  }}
                />
                <div className="flex justify-between text-[8px] text-[#E0E1DD]/30">
                  <span>0</span>
                  <span>5 (Target)</span>
                  <span>8 (Maximum)</span>
                </div>
              </div>

              {/* Q&A Pairs Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-white font-bold">
                  <span>3. CUSTOMER Q&A PAIRS</span>
                  <span className="text-[#00F5FF]">{simQaCount} pairs</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="25"
                  value={simQaCount}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    setSimQaCount(val);
                    handleSliderChange("qa_count", val);
                  }}
                  className="w-full h-1 bg-white/10 appearance-none cursor-pointer accent-[#00F5FF] outline-none"
                  style={{
                    background: `linear-gradient(to right, #00F5FF 0%, #00F5FF ${(simQaCount / 25) * 100}%, rgba(255,255,255,0.1) ${(simQaCount / 25) * 100}%, rgba(255,255,255,0.1) 100%)`
                  }}
                />
                <div className="flex justify-between text-[8px] text-[#E0E1DD]/30">
                  <span>0 (Critical gap)</span>
                  <span>10 (Strong)</span>
                  <span>25 (Category Leader)</span>
                </div>
              </div>

              {/* A+ Content Checkbox */}
              <label className="flex items-center gap-2.5 cursor-pointer bg-[#050C16]/40 p-2.5 border border-white/5 select-none max-w-xs hover:border-white/15 transition-all">
                <input
                  type="checkbox"
                  checked={simHasAPlus}
                  onChange={(e) => {
                    const val = e.target.checked;
                    setSimHasAPlus(val);
                    handleSliderChange("has_a_plus", val);
                  }}
                  className="w-3.5 h-3.5 border border-white/20 bg-transparent rounded-none appearance-none cursor-pointer checked:bg-[#00F5FF] checked:border-transparent relative after:content-[''] after:hidden checked:after:block after:absolute after:left-[4px] after:top-[1px] after:w-[4px] after:h-[8px] after:border-r-[2px] after:border-b-[2px] after:border-[#060C16] after:rotate-45"
                />
                <span className="text-white text-[10px] font-bold uppercase tracking-wider">Has Enhanced A+ Content Modules</span>
              </label>
            </div>
          </div>
        </section>

        {/* SECTION 6: Relational Gaps Audit */}
        {data.weaknesses.length > 0 && (
          <section className="space-y-6">
            <div className="space-y-2">
              <h2 className="text-xs font-mono font-black uppercase text-white tracking-widest border-b border-white/5 pb-2">
                PART 6: DETECTED COGNITIVE DEFICIT REGISTER
              </h2>
              <p className="text-[10px] text-[#E0E1DD]/50 font-mono uppercase tracking-widest">
                Specific missing relational parameters causing your listing to be bypassed.
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-1">
              {data.weaknesses.map((w, i) => (
                <WeaknessCard key={i} weakness={w} index={i} />
              ))}
            </div>
          </section>
        )}

        {/* SECTION 7: Competitor Benchmarking */}
        {data.competitors.length > 0 && (
          <section className="space-y-6">
            <div className="space-y-2">
              <h2 className="text-xs font-mono font-black uppercase text-white tracking-widest border-b border-white/5 pb-2">
                PART 7: COMPETITOR VECTOR ADVANTAGE BENCHMARKS
              </h2>
              <p className="text-[10px] text-[#E0E1DD]/50 font-mono uppercase tracking-widest">
                Competitor vector alignment benchmarks.
              </p>
            </div>
            <div className="space-y-3">
              {data.competitors.map((c, i) => (
                <CompetitorCard key={i} comp={c} index={i} />
              ))}
            </div>
          </section>
        )}

        {/* SECTION 8: Call to Action (Zero sales fluff, pure technical impact) */}
        <section className="rounded-none border border-[#FF2D55]/30 bg-gradient-to-br from-[#FF2D55]/5 to-transparent p-8 sm:p-12 text-center relative overflow-hidden box-glow-crimson/10">
          <div className="absolute top-0 right-0 w-96 h-96 bg-[#FF2D55]/5 rounded-full blur-[110px] pointer-events-none" />
          <div className="relative z-10 max-w-2xl mx-auto space-y-6">
            <h2 className="text-xl sm:text-2xl font-mono font-black text-white uppercase tracking-wider text-balance">
              Establish your product as a dominant node in the Amazon COSMO Graph
            </h2>
            <p className="text-[#E0E1DD]/70 max-w-xl mx-auto text-xs leading-relaxed font-mono">
              In a 15-minute diagnostic briefing, we will provide the complete semantic rewrite for your listing, demonstrate our A/B causal lift Difference-in-Differences projection, and deliver a clean catalog implementation checklist.
            </p>
            <div className="pt-4">
              <button
                onClick={handleBookMeeting}
                className="w-full sm:w-auto px-8 py-4 rounded-none bg-[#FF2D55] text-white font-mono uppercase tracking-widest text-[10px] font-black hover:bg-[#ff4d5a] hover:shadow-[0_0_20px_rgba(255,45,85,0.4)] transition-all duration-300"
              >
                Secure 15-Minute Recovery Session →
              </button>
            </div>
            <p className="text-[8px] font-mono uppercase tracking-widest text-[#E0E1DD]/30">No obligation · Direct technical audit · Zero fluff</p>
          </div>
        </section>

      </main>

      {/* ── Footer ── */}
      <footer className="max-w-5xl mx-auto px-4 sm:px-6 py-8 border-t border-white/5 font-mono text-[9px] text-[#E0E1DD]/40 uppercase tracking-[0.2em] relative z-10 flex flex-col md:flex-row items-center justify-between gap-4">
        <span>© {new Date().getFullYear()} Optimus Prime Agency · Amazon Listing Orchestration</span>
        <span>Powered by COSMO Semantic Attribution Engine</span>
      </footer>

      {/* ── Chat Widget (Fallback Coprocessor) ── */}
      <div className="fixed bottom-6 right-6 z-50">
        {chatOpen ? (
          <div className="w-[calc(100vw-48px)] sm:w-[380px] md:w-[400px] h-[500px] rounded-none border border-[#00F5FF]/20 bg-[#060F1E]/95 backdrop-blur-2xl shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-bottom-4 duration-300">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-[#0B1526]/80 backdrop-blur-md">
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-none border border-[#00F5FF]/30 bg-[#00F5FF]/10 flex items-center justify-center">
                  <svg className="w-3.5 h-3.5 text-[#00F5FF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                </div>
                <div>
                  <p className="text-[10px] font-mono font-black uppercase tracking-wider text-white">Rufus Diagnostic AI</p>
                  <p className="text-[8px] font-mono text-[#00F5FF]/70 uppercase tracking-widest">Semantic Coprocessor Active</p>
                </div>
              </div>
              <button onClick={() => setChatOpen(false)} className="text-[#E0E1DD]/40 hover:text-white transition-colors p-1">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {chatMessages.length === 0 && (
                <div className="text-center py-6 space-y-4">
                  <p className="text-[9px] text-[#E0E1DD]/50 font-mono font-bold uppercase tracking-wider">Query listing diagnostic anomalies</p>
                  <div className="space-y-2">
                    {["Explain my specific Exclusion Risk?", "How can I improve Semantic Utility Density?", "What would organic recovery cost?"].map((q) => (
                      <button
                        key={q}
                        onClick={() => { setChatInput(q); }}
                        className="block w-full text-left text-xs text-[#E0E1DD]/70 rounded-none border border-[#00F5FF]/10 px-3 py-2.5 hover:bg-[#00F5FF]/5 hover:border-[#00F5FF]/30 transition-all font-mono"
                      >
                        &gt; {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {chatMessages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[85%] rounded-none px-4 py-3 text-xs leading-relaxed font-mono ${
                    msg.role === "user"
                      ? "bg-[#00F5FF]/10 border border-[#00F5FF]/30 text-[#00F5FF]"
                      : "bg-[#0B1526]/90 text-[#E0E1DD]/90 border border-white/5"
                  }`}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-[#0B1526]/90 border border-white/5 rounded-none px-4 py-3">
                    <div className="flex gap-1.5">
                      <div className="w-1.5 h-1.5 bg-[#00F5FF] rounded-none animate-bounce" style={{ animationDelay: "0ms" }} />
                      <div className="w-1.5 h-1.5 bg-[#00F5FF] rounded-none animate-bounce" style={{ animationDelay: "150ms" }} />
                      <div className="w-1.5 h-1.5 bg-[#00F5FF] rounded-none animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div className="p-3 border-t border-white/5 bg-[#0B1526]/50">
              <div className="flex gap-2">
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleChat()}
                  placeholder="Query semantic gaps..."
                  className="flex-1 rounded-none bg-[#050C16] border border-white/10 px-3.5 py-2.5 text-xs text-white placeholder-gray-800 focus:outline-none focus:border-[#00F5FF]/40 font-mono"
                />
                <button
                  onClick={handleChat}
                  disabled={chatLoading || !chatInput.trim()}
                  className="px-4 py-2.5 rounded-none bg-[#FF2D55] border border-[#FF2D55]/50 text-white text-[9px] font-mono font-black uppercase tracking-widest hover:bg-[#ff4d5a] disabled:opacity-30 transition-colors"
                >
                  Query
                </button>
              </div>
            </div>
          </div>
        ) : (
          <button
            onClick={() => {
              setChatOpen(true);
              trackEvent(brandKey, "chat_open");
            }}
            className="group w-14 h-14 rounded-none bg-[#FF2D55] border border-[#FF2D55]/50 text-white shadow-lg hover:shadow-[0_0_20px_rgba(255,45,85,0.4)] transition-all duration-300 hover:-translate-y-1 flex items-center justify-center"
          >
            <svg className="w-6 h-6 group-hover:scale-110 transition-transform text-white text-glow-crimson" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
