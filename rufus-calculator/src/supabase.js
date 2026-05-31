import { useState, useEffect, useRef } from 'react';
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

// Lazy init — only create client if credentials are configured
let _client = null;
function getSupabase() {
  if (!_client && supabaseUrl && supabaseAnonKey) {
    _client = createClient(supabaseUrl, supabaseAnonKey);
  }
  return _client;
}

export const supabase = { get client() { return getSupabase(); } };

/**
 * Look up an ASIN in the prospects table.
 * Returns the existing Rufus score data if found, null otherwise.
 */
export async function lookupASIN(asin) {
  const sb = getSupabase();
  if (!asin || !sb) return null;

  const { data, error } = await sb
    .from('prospects')
    .select(`
      asin,
      brand_key,
      post_title,
      post_body,
      brand,
      category,
      listing_price,
      listing_rating,
      listing_review_count,
      bullet_count,
      image_count,
      has_a_plus,
      qa_count,
      rufus_score,
      intent_alignment_score,
      attribute_density_score,
      conversational_readability_score,
      qa_coverage_score,
      rufus_citation_probability,
      rufus_top_weaknesses,
      rufus_summary,
      weakness_signals
    `)
    .eq('asin', asin)
    .limit(1);

  if (error || !data || data.length === 0) return null;
  const prospect = data[0];

  if (prospect.brand_key) {
    const { data: brandData, error: brandError } = await sb
      .from('brands')
      .select('loom_url')
      .eq('brand_key', prospect.brand_key)
      .limit(1);
    if (!brandError && brandData && brandData.length > 0) {
      prospect.loom_url = brandData[0].loom_url;
    }
  }

  return prospect;
}

/**
 * Submit calculator results to the rufus_calc_submissions table.
 */
export async function submitCalculatorResults(submission) {
  const sb = getSupabase();
  if (!sb) {
    console.warn('Supabase not configured — submission stored locally only');
    return { id: crypto.randomUUID(), ...submission };
  }

  const { data, error } = await sb
    .from('rufus_calc_submissions')
    .insert({
      email: submission.email,
      asin: submission.asin,
      category: submission.category,
      self_intent: submission.selfIntent || null,
      self_attribute: submission.selfAttribute || null,
      self_readability: submission.selfReadability || null,
      self_qa: submission.selfQA || null,
      self_reported_score: submission.selfReportedScore || null,
      actual_rufus_score: submission.actualRufusScore || null,
      monthly_revenue: submission.monthlyRevenue || null,
      results: submission.results || null,
      referrer: document.referrer || null,
      utm_source: new URLSearchParams(window.location.search).get('utm_source') || submission.ref || null,
      utm_campaign: new URLSearchParams(window.location.search).get('utm_campaign') || null,
      user_agent: navigator.userAgent,
    })
    .select('id')
    .single();

  if (error) {
    console.error('Submission error:', error);
    return { id: crypto.randomUUID(), ...submission };
  }

  return { id: data.id, ...submission };
}

/**
 * Fetch a submission by ID
 */
export async function getSubmission(id) {
  const sb = getSupabase();
  if (!sb || !id) return null;

  const { data, error } = await sb
    .from('rufus_calc_submissions')
    .select('*')
    .eq('id', id)
    .single();

  if (error || !data) {
    console.error('Fetch submission error:', error);
    return null;
  }
  
  return data;
}

/**
 * Custom React hook for handling calculator form submission to Supabase.
 * Encapsulates loading, error, and success states in an unmount-safe manner.
 */
export function useSubmission() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  const submit = async (submission) => {
    setIsSubmitting(true);
    setError(null);
    setIsSuccess(false);

    try {
      const result = await submitCalculatorResults(submission);
      if (isMounted.current) {
        setIsSuccess(true);
        return result;
      }
    } catch (err) {
      if (isMounted.current) {
        setError(err.message || 'Submission failed. Please check your connection and try again.');
      }
    } finally {
      if (isMounted.current) {
        setIsSubmitting(false);
      }
    }
    return null;
  };

  return { submit, isSubmitting, error, isSuccess };
}
