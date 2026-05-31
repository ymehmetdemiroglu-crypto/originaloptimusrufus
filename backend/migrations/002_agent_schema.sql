-- =============================================================================
-- Optimus Rufus Autonomous Agent — Schema Migration (Phase 1)
-- Run this in the Supabase SQL Editor to add agent orchestration tables.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Agent run logging — every autonomous job execution is tracked here
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_runs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    run_type TEXT NOT NULL CHECK (run_type IN (
        'scrape', 'enrich', 'score', 'draft', 'sequence',
        'reply_poll', 'landing_sync', 'loom', 'nurture', 'learning', 'full_pipeline'
    )),
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'success', 'partial', 'failed', 'cancelled')),
    records_processed INTEGER DEFAULT 0,
    records_succeeded INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_log JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    triggered_by TEXT DEFAULT 'scheduler' CHECK (triggered_by IN ('scheduler', 'manual', 'webhook', 'system'))
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_type ON agent_runs(run_type, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status, started_at DESC);

-- ---------------------------------------------------------------------------
-- Agent configuration / feature flags (single-row config table)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_config (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    agent_enabled BOOLEAN DEFAULT false,
    auto_scrape BOOLEAN DEFAULT false,
    auto_enrich BOOLEAN DEFAULT false,
    auto_score BOOLEAN DEFAULT false,
    auto_draft BOOLEAN DEFAULT false,
    auto_sequence BOOLEAN DEFAULT false,
    auto_reply BOOLEAN DEFAULT false,
    max_daily_sequences INTEGER DEFAULT 50,
    reply_confidence_threshold FLOAT DEFAULT 0.85,
    updated_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO agent_config (id, agent_enabled, auto_scrape, auto_enrich, auto_score, auto_draft, auto_sequence, auto_reply)
VALUES (1, false, false, false, false, false, false, false)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Email conversations: extend status enum for auto-sent tracking
-- ---------------------------------------------------------------------------
ALTER TABLE email_conversations DROP CONSTRAINT IF EXISTS email_conversations_status_check;
ALTER TABLE email_conversations ADD CONSTRAINT email_conversations_status_check
    CHECK (status IN ('pending', 'approved', 'sent', 'auto_sent', 'received'));

ALTER TABLE email_conversations ADD COLUMN IF NOT EXISTS auto_sent BOOLEAN DEFAULT false;
ALTER TABLE email_conversations ADD COLUMN IF NOT EXISTS ai_draft_reviewed BOOLEAN DEFAULT false;

-- ---------------------------------------------------------------------------
-- Daily pipeline snapshot (for trend dashboards)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    stage TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    avg_reachability_index FLOAT,
    avg_client_quality_score FLOAT,
    metadata JSONB DEFAULT '{}'::jsonb,
    UNIQUE(snapshot_date, stage)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_snapshots_date ON pipeline_snapshots(snapshot_date DESC);
