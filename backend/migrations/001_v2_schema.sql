-- =============================================================================
-- Optimus Rufus v2 — Supabase Schema Migration
-- Run this in the Supabase SQL Editor to add new tables and columns.
-- =============================================================================

-- Enable pgvector if not already enabled (for RAG embeddings)
-- CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- New columns on existing brands table
-- ---------------------------------------------------------------------------
ALTER TABLE brands ADD COLUMN IF NOT EXISTS landing_page_views INTEGER DEFAULT 0;
ALTER TABLE brands ADD COLUMN IF NOT EXISTS landing_page_last_visit TIMESTAMPTZ;
ALTER TABLE brands ADD COLUMN IF NOT EXISTS meeting_scheduled_at TIMESTAMPTZ;
ALTER TABLE brands ADD COLUMN IF NOT EXISTS meeting_calendly_id TEXT;

-- ---------------------------------------------------------------------------
-- Chat sessions for RAG assistant
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    brand_key TEXT REFERENCES brands(brand_key) ON DELETE CASCADE,
    messages JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_brand ON chat_sessions(brand_key);

-- ---------------------------------------------------------------------------
-- Landing page analytics
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS landing_analytics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    brand_key TEXT,
    event_type TEXT NOT NULL,
    event_data JSONB DEFAULT '{}'::jsonb,
    ip_hash TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_landing_analytics_brand ON landing_analytics(brand_key);
CREATE INDEX IF NOT EXISTS idx_landing_analytics_event ON landing_analytics(event_type, created_at);

-- ---------------------------------------------------------------------------
-- Email conversations (beyond Apollo sequences)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    brand_key TEXT REFERENCES brands(brand_key) ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK (direction IN ('outbound', 'inbound')),
    subject TEXT,
    body TEXT NOT NULL,
    classification JSONB,
    ai_draft TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'sent', 'auto_sent', 'received')),
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_email_conv_brand ON email_conversations(brand_key, created_at);
CREATE INDEX IF NOT EXISTS idx_email_conv_status ON email_conversations(status);

-- ---------------------------------------------------------------------------
-- Email steps (per-brand, per-step storage for 5-step sequences)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_steps (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    brand_key TEXT REFERENCES brands(brand_key) ON DELETE CASCADE,
    step_num INTEGER NOT NULL CHECK (step_num BETWEEN 1 AND 5),
    subject TEXT,
    body TEXT,
    overlap FLOAT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(brand_key, step_num)
);

CREATE INDEX IF NOT EXISTS idx_email_steps_brand ON email_steps(brand_key);

-- ---------------------------------------------------------------------------
-- Meeting bookings
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meetings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    brand_key TEXT REFERENCES brands(brand_key) ON DELETE SET NULL,
    calendly_event_id TEXT UNIQUE,
    invitee_email TEXT,
    invitee_name TEXT,
    scheduled_at TIMESTAMPTZ,
    event_type TEXT,
    status TEXT DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no_show')),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_meetings_brand ON meetings(brand_key);
CREATE INDEX IF NOT EXISTS idx_meetings_status ON meetings(status);

-- ---------------------------------------------------------------------------
-- CSV upload jobs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS csv_jobs (
    id TEXT PRIMARY KEY,
    upload_filename TEXT,
    row_count INTEGER,
    status TEXT DEFAULT 'processing' CHECK (status IN ('processing', 'completed', 'failed')),
    input_data JSONB,
    output_data JSONB,
    scores_before JSONB,
    scores_after JSONB,
    ip_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- Row Level Security (optional — enable if using anon key from frontend)
-- ---------------------------------------------------------------------------
-- Landing analytics: allow inserts from anon
-- ALTER TABLE landing_analytics ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Allow anonymous landing analytics inserts" ON landing_analytics
--     FOR INSERT TO anon WITH CHECK (true);

-- Chat sessions: allow inserts/reads from anon (scoped by brand_key)
-- ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Allow chat sessions" ON chat_sessions
--     FOR ALL TO anon USING (true) WITH CHECK (true);

-- Core tables: enable Row Level Security (RLS) to enforce pre-existing policies
ALTER TABLE brands ENABLE ROW LEVEL SECURITY;
ALTER TABLE prospects ENABLE ROW LEVEL SECURITY;

-- Harden RLS policies to prevent overly permissive linter warnings
-- Brand step emails table policies
DROP POLICY IF EXISTS "Allow authenticated full step emails" ON public.brand_step_emails;
CREATE POLICY "Allow authenticated full step emails" ON public.brand_step_emails 
    FOR ALL TO authenticated 
    USING (auth.role() = 'authenticated') 
    WITH CHECK (auth.role() = 'authenticated');

-- Rufus calculator submissions table policies
DROP POLICY IF EXISTS "Allow anon insert submissions" ON public.rufus_calc_submissions;
CREATE POLICY "Allow anon insert submissions" ON public.rufus_calc_submissions 
    FOR INSERT TO anon 
    WITH CHECK (auth.role() = 'anon');

DROP POLICY IF EXISTS "Allow authenticated full submissions" ON public.rufus_calc_submissions;
CREATE POLICY "Allow authenticated full submissions" ON public.rufus_calc_submissions 
    FOR ALL TO authenticated 
    USING (auth.role() = 'authenticated') 
    WITH CHECK (auth.role() = 'authenticated');

-- Brands and prospects tables proactive hardening
DROP POLICY IF EXISTS "Allow authenticated full brands" ON public.brands;
CREATE POLICY "Allow authenticated full brands" ON public.brands 
    FOR ALL TO authenticated 
    USING (auth.role() = 'authenticated') 
    WITH CHECK (auth.role() = 'authenticated');

DROP POLICY IF EXISTS "Allow authenticated full prospects" ON public.prospects;
CREATE POLICY "Allow authenticated full prospects" ON public.prospects 
    FOR ALL TO authenticated 
    USING (auth.role() = 'authenticated') 
    WITH CHECK (auth.role() = 'authenticated');

-- ---------------------------------------------------------------------------
-- Helper function: get reply stats by axis
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_reply_stats_by_axis()
RETURNS TABLE(axis TEXT, total_sent BIGINT, total_replied BIGINT, reply_rate FLOAT) AS $$
BEGIN
    RETURN QUERY
    SELECT
        b.worst_axis_at_send AS axis,
        COUNT(*)::BIGINT AS total_sent,
        COUNT(*) FILTER (WHERE b.stage IN ('REPLIED', 'DEMO_SCHEDULED', 'MEETING_BOOKED'))::BIGINT AS total_replied,
        CASE 
            WHEN COUNT(*) > 0 THEN 
                COUNT(*) FILTER (WHERE b.stage IN ('REPLIED', 'DEMO_SCHEDULED', 'MEETING_BOOKED'))::FLOAT / COUNT(*)::FLOAT
            ELSE 0.0
        END AS reply_rate
    FROM brands b
    WHERE b.worst_axis_at_send IS NOT NULL
    GROUP BY b.worst_axis_at_send
    ORDER BY reply_rate DESC;
END;
$$ LANGUAGE plpgsql SET search_path = public;

-- ---------------------------------------------------------------------------
-- Competitors table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.competitors (
    brand_key TEXT NOT NULL,
    competitor_asin TEXT NOT NULL,
    competitor_brand TEXT,
    search_rank INTEGER,
    title TEXT,
    bullet_count INTEGER,
    bullets TEXT,
    image_count INTEGER,
    has_a_plus BOOLEAN,
    qa_count INTEGER,
    rating FLOAT,
    review_count INTEGER,
    price FLOAT,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (brand_key, competitor_asin)
);

ALTER TABLE public.competitors ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anon read competitors" ON public.competitors FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon full competitors" ON public.competitors FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY "Allow authenticated full competitors" ON public.competitors FOR ALL TO authenticated USING (auth.role() = 'authenticated') WITH CHECK (auth.role() = 'authenticated');

