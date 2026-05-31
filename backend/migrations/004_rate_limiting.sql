-- =============================================================================
-- Optimus Rufus — Rate Limiting Submissions Migration (004)
-- =============================================================================

-- Enable pgcrypto for secure IP hashing
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Add an IP hash column if not already present to prevent tracking raw IPs
ALTER TABLE public.rufus_calc_submissions ADD COLUMN IF NOT EXISTS ip_hash TEXT;

-- Create an index to keep checks lightning fast
CREATE INDEX IF NOT EXISTS idx_rufus_calc_subs_ip ON public.rufus_calc_submissions(ip_hash, created_at DESC);

-- Create a rate-limiting checker function
CREATE OR REPLACE FUNCTION public.check_rufus_calc_submission_rate()
RETURNS TRIGGER AS $$
DECLARE
    recent_count INTEGER;
    client_ip TEXT;
BEGIN
    -- Extract IP address from HTTP headers if available via Supabase/PostgREST
    BEGIN
        client_ip := current_setting('request.headers', true)::json->>'x-real-ip';
    EXCEPTION WHEN OTHERS THEN
        client_ip := 'unknown';
    END;

    IF client_ip IS NULL OR client_ip = '' THEN
        client_ip := 'unknown';
    END IF;

    -- Store hash of IP address to prevent PII leaks while allowing rate-limiting
    NEW.ip_hash := encode(digest(client_ip, 'sha256'), 'hex');

    -- Count submissions from the same IP in the past hour
    SELECT COUNT(*) INTO recent_count
    FROM public.rufus_calc_submissions
    WHERE ip_hash = NEW.ip_hash AND created_at > now() - INTERVAL '1 hour';

    -- Enforce max 10 submissions per hour
    IF recent_count >= 10 THEN
        RAISE EXCEPTION 'Rate limit exceeded: Maximum of 10 submissions per hour.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Bind the trigger to run before any anon inserts
DROP TRIGGER IF EXISTS trg_check_rufus_calc_rate ON public.rufus_calc_submissions;
CREATE TRIGGER trg_check_rufus_calc_rate
    BEFORE INSERT ON public.rufus_calc_submissions
    FOR EACH ROW
    EXECUTE FUNCTION public.check_rufus_calc_submission_rate();
