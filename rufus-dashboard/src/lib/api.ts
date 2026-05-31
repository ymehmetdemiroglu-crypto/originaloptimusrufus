const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi(path: string, options?: RequestInit) {
  const adminKey = typeof window !== 'undefined' ? (localStorage.getItem("X-Admin-Key") || "optimus_secret_key_2026") : "optimus_secret_key_2026";
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 
      "Content-Type": "application/json", 
      "X-Admin-Key": adminKey,
      ...options?.headers 
    },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  overview: () => fetchApi("/api/overview"),
  analyze: (asin: string) =>
    fetchApi("/api/analyze", {
      method: "POST",
      body: JSON.stringify({ asin }),
    }),
  competitors: (asin: string) =>
    fetchApi("/api/competitors", {
      method: "POST",
      body: JSON.stringify({ asin }),
    }),
  optimizeMarketing: (asin: string, keywords?: string, audience?: string, location?: string) =>
    fetchApi("/api/marketing/optimize", {
      method: "POST",
      body: JSON.stringify({ asin, keywords, audience, location }),
    }),
  pipeline: () => fetchApi("/api/pipeline"),
  clients: () => fetchApi("/api/clients"),
  clientUsage: () => fetchApi("/api/clients/usage"),
  prospects: (stage?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (stage) params.append("stage", stage);
    if (limit) params.append("limit", String(limit));
    const qs = params.toString();
    return fetchApi(`/api/prospects${qs ? "?" + qs : ""}`);
  },
  brands: (stage?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (stage) params.append("stage", stage);
    if (limit) params.append("limit", String(limit));
    const qs = params.toString();
    return fetchApi(`/api/brands${qs ? "?" + qs : ""}`);
  },
  agentStatus: () => fetchApi("/api/agent/status"),
  agentRunJob: (job_type: string) =>
    fetchApi("/api/agent/run", {
      method: "POST",
      body: JSON.stringify({ job_type }),
    }),
  agentRunPipeline: () =>
    fetchApi("/api/agent/run-pipeline", {
      method: "POST",
      body: JSON.stringify({ triggered_by: "manual" }),
    }),
  agentPause: () => fetchApi("/api/agent/pause", { method: "POST" }),
  agentResume: () => fetchApi("/api/agent/resume", { method: "POST" }),
  agentRuns: () => fetchApi("/api/agent/runs"),
};
