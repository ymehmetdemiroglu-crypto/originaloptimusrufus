"use client";

import { useState, useRef, useEffect } from "react";

interface CSVJob {
  job_id: string;
  status: string; // 'processing', 'completed', 'failed'
  row_count: number;
  processed: number;
  scores_before: Array<{ asin: string; score: number; grade: string }>;
  scores_after: Array<{ asin: string; score: number; grade: string }>;
  error?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CSVOptimizePage() {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<CSVJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Poll job status if processing
  useEffect(() => {
    if (!job || job.status !== "processing") return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/api/csv/job/${job.job_id}`);
        if (!res.ok) throw new Error("Failed to poll status");
        const data = await res.json();
        setJob(data);

        if (data.status !== "processing") {
          clearInterval(interval);
        }
      } catch (err: any) {
        setError("Error tracking optimization progress.");
        clearInterval(interval);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [job]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.name.endsWith(".csv")) {
        setFile(droppedFile);
        setError(null);
      } else {
        setError("Please drop a valid .csv file.");
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.name.endsWith(".csv")) {
        setFile(selectedFile);
        setError(null);
      } else {
        setError("Please select a valid .csv file.");
      }
    }
  };

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  const handleSubmit = async () => {
    if (!file) return;

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_URL}/api/csv/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to upload file");
      }

      const data = await res.json();
      setJob({
        job_id: data.job_id,
        status: data.status,
        row_count: data.row_count,
        processed: 0,
        scores_before: [],
        scores_after: [],
      });
    } catch (err: any) {
      setError(err.message || "Failed to start optimization.");
    } finally {
      setLoading(false);
    }
  };

  const averageScore = (scores: Array<{ score: number }>) => {
    if (!scores.length) return 0;
    return Math.round(scores.reduce((acc, curr) => acc + curr.score, 0) / scores.length);
  };

  const averageBefore = job ? averageScore(job.scores_before) : 0;
  const averageAfter = job ? averageScore(job.scores_after) : 0;
  const lift = averageAfter - averageBefore;

  return (
    <div className="min-h-screen bg-[#0A192F] text-[#E0E1DD] selection:bg-[#E63946] selection:text-white relative overflow-hidden font-sans flex flex-col justify-between">
      {/* Geometric Ghost Background */}
      <div className="absolute inset-0 void-grid opacity-30 pointer-events-none" />
      <div className="absolute top-0 left-0 right-0 h-[500px] bg-gradient-to-b from-[#00F5FF]/5 to-transparent blur-[120px] pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-[#00F5FF]/3 rounded-full blur-[120px] pointer-events-none" />

      {/* Nav */}
      <nav className="max-w-6xl mx-auto w-full px-6 py-6 flex items-center justify-between border-b border-white/5 relative z-10">
        <div className="flex items-center gap-3">
          <div className="relative w-8 h-8 flex items-center justify-center">
            <svg viewBox="0 0 100 100" className="w-full h-full text-white drop-shadow-[0_0_6px_rgba(230,57,70,0.4)]">
              <polygon points="50,5 95,25 95,75 50,95 5,75 5,25" fill="none" stroke="currentColor" strokeWidth="8" />
              <circle cx="50" cy="50" r="14" fill="#E63946" className="animate-pulse" />
            </svg>
          </div>
          <div className="flex items-center gap-1.5 font-display tracking-[0.2em] text-[10px] uppercase leading-none">
            <span className="font-semibold text-white">OPTIMUS</span>
            <span className="text-[#E0E1DD]/30">|</span>
            <span className="font-light text-[#E0E1DD]">PRIME</span>
          </div>
        </div>
        <a
          href={`${API_URL}/api/csv/template`}
          className="text-[10px] font-display uppercase tracking-widest text-[#E0E1DD]/60 hover:text-white transition-all bg-white/5 border border-white/10 rounded-sm px-4 py-2 hover:border-[#00F5FF]/35"
        >
          Download Template
        </a>
      </nav>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-16 relative z-10 flex flex-col justify-center">
        <div className="text-center space-y-4 mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-none border border-[#00F5FF]/20 bg-[#00F5FF]/5 text-[10px] font-display uppercase tracking-widest text-[#00F5FF] text-glow-cyan">
            <span className="w-1.5 h-1.5 rounded-full bg-[#00F5FF] animate-pulse" />
            Self-Service Optimization Portal
          </div>
          <h1 className="text-3xl md:text-4xl font-display font-bold text-white uppercase tracking-wider">
            Batch COSMO Listing Optimizer
          </h1>
          <p className="text-[#E0E1DD]/70 max-w-xl mx-auto text-xs leading-relaxed font-mono">
            Upload your product listings in bulk via CSV. We will analyze each product against 12 semantic COSMO relationship categories and rewrite bullet copy dynamically to secure top-tier citation in Amazon Rufus.
          </p>
        </div>

        {/* Form or Processing view */}
        {!job ? (
          <div className="rounded-sm border border-white/10 bg-[#0F2442]/30 backdrop-blur-md p-8 max-w-xl mx-auto w-full space-y-6 shadow-xl">
            {/* Drag & Drop Area */}
            <div
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={triggerFileInput}
              className={`border border-dashed rounded-sm p-10 text-center cursor-pointer transition-all duration-300 ${
                dragActive
                  ? "border-[#00F5FF] bg-[#00F5FF]/5 box-glow-cyan/10"
                  : file
                  ? "border-emerald-500/50 bg-emerald-500/5"
                  : "border-white/10 hover:border-[#00F5FF]/30 hover:bg-white/[0.01]"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".csv"
                onChange={handleFileChange}
              />
              <div className="space-y-4">
                <div className="w-12 h-12 rounded-sm bg-white/5 mx-auto flex items-center justify-center border border-white/10">
                  {file ? (
                    <svg className="w-6 h-6 text-[#00F5FF] text-glow-cyan" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="w-6 h-6 text-[#E0E1DD]/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                  )}
                </div>
                <div>
                  <p className="text-sm font-display font-medium text-white uppercase tracking-wider">
                    {file ? file.name : "Choose CSV file to optimize"}
                  </p>
                  <p className="text-xs text-[#E0E1DD]/45 font-mono mt-1">
                    {file ? `${(file.size / 1024).toFixed(1)} KB` : "Drag and drop or click to select"}
                  </p>
                </div>
              </div>
            </div>

            {error && (
              <div className="rounded-sm border border-[#E63946]/20 bg-[#E63946]/5 px-4 py-3 text-xs text-[#E63946] text-glow-crimson font-mono">
                &gt; {error}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={!file || loading}
              className="w-full py-3.5 rounded-sm bg-[#E63946] border border-[#E63946]/50 text-white font-display uppercase tracking-widest text-xs font-semibold hover:bg-[#ff4d5a] hover:shadow-[0_0_20px_rgba(230,57,70,0.4)] transition-all duration-300 disabled:opacity-30 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-none animate-spin" />
                  INITIATING BATCH VECTOR RUN...
                </>
              ) : (
                "OPTIMIZE BATCH NOW"
              )}
            </button>
          </div>
        ) : (
          <div className="rounded-sm border border-white/10 bg-[#0F2442]/30 backdrop-blur-md p-8 max-w-2xl mx-auto w-full space-y-8 shadow-xl">
            {/* Status Header */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-display font-bold text-white uppercase tracking-wider">Batch Job: {job.job_id}</h3>
                <p className="text-xs font-mono text-[#E0E1DD]/40 mt-1">
                  Processing {job.row_count} catalog rows
                </p>
              </div>
              <div className={`px-4 py-1.5 rounded-none text-[10px] font-display font-bold uppercase tracking-widest ${
                job.status === "completed"
                  ? "bg-[#00F5FF]/10 text-[#00F5FF] border border-[#00F5FF]/30 text-glow-cyan"
                  : job.status === "failed"
                  ? "bg-[#E63946]/10 text-[#E63946] border border-[#E63946]/30 text-glow-crimson"
                  : "bg-white/5 text-[#E0E1DD]/60 border border-white/10 animate-pulse"
              }`}>
                {job.status}
              </div>
            </div>

            {/* Progress Meter */}
            {job.status === "processing" && (
              <div className="space-y-3">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-[#E0E1DD]/40">Rewriting catalog listings...</span>
                  <span className="text-[#00F5FF] font-bold">{job.processed} / {job.row_count}</span>
                </div>
                <div className="h-2 bg-[#060F1E] border border-white/5 p-[1px] rounded-none">
                  <div
                    className="h-full bg-[#00F5FF] box-glow-cyan transition-all duration-500 ease-out"
                    style={{ width: `${(job.processed / job.row_count) * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* Summary Statistics Card */}
            {job.status === "completed" && (
              <div className="grid grid-cols-3 gap-4">
                <div className="rounded-sm border border-white/5 bg-[#0A192F]/40 p-4 text-center">
                  <div className="text-[9px] text-[#E0E1DD]/40 uppercase tracking-widest font-display font-medium">Avg Score Before</div>
                  <div className="text-2xl font-display font-black text-white/70 mt-1">{averageBefore}</div>
                </div>
                <div className="rounded-sm border border-white/5 bg-[#0A192F]/40 p-4 text-center">
                  <div className="text-[9px] text-[#E0E1DD]/40 uppercase tracking-widest font-display font-medium">Avg Score After</div>
                  <div className="text-2xl font-display font-black text-[#00F5FF] text-glow-cyan mt-1">{averageAfter}</div>
                </div>
                <div className="rounded-sm border border-[#00F5FF]/20 bg-[#00F5FF]/5 p-4 text-center">
                  <div className="text-[9px] text-[#00F5FF] uppercase tracking-widest font-display font-bold">Total Lift</div>
                  <div className="text-2xl font-display font-black text-[#00F5FF] text-glow-cyan mt-1">+{lift} pts</div>
                </div>
              </div>
            )}

            {/* Error alerts */}
            {job.status === "failed" && (
              <div className="rounded-sm border border-[#E63946]/20 bg-[#E63946]/5 p-4 text-xs text-[#E63946] text-glow-crimson font-mono">
                &gt; OPTIMIZATION FAILURE: {job.error || "Critical runtime processing exception"}
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-4">
              <button
                onClick={() => {
                  setJob(null);
                  setFile(null);
                }}
                className="flex-1 py-3.5 rounded-sm border border-white/10 text-[#E0E1DD]/60 hover:text-white hover:bg-white/5 hover:border-white/20 transition-all duration-200 text-[10px] font-display uppercase tracking-widest"
              >
                Upload New Batch
              </button>
              {job.status === "completed" && (
                <a
                  href={`${API_URL}/api/csv/job/${job.job_id}/download`}
                  className="flex-1 py-3.5 rounded-sm bg-[#E63946] border border-[#E63946]/50 text-white font-display uppercase tracking-widest text-[10px] font-semibold text-center flex items-center justify-center gap-2 hover:bg-[#ff4d5a] hover:shadow-[0_0_20px_rgba(230,57,70,0.4)] transition-all duration-300"
                >
                  <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download Optimized CSV
                </a>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="max-w-6xl mx-auto w-full px-6 py-8 border-t border-white/5 relative z-10 flex items-center justify-between font-display text-[9px] text-[#E0E1DD]/35 uppercase tracking-widest">
        <span>© {new Date().getFullYear()} Optimus Prime Agency · Batch Analysis Pipeline</span>
        <span>Powered by COSMO Engine</span>
      </footer>
    </div>
  );
}
