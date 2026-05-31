import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { lookupASIN } from './supabase';
import { calculateRufusScore, fetchBackendAnalysis } from './calculator';
import './App.css';

// ---- ASIN Zod Schema ----
const calculatorSchema = z.object({
  asin: z.string()
    .min(1, 'Amazon ASIN is required')
    .regex(/^B[0-9A-Z]{9}$/, 'Invalid Amazon ASIN format (should be 10 characters starting with B)')
});

export default function Calculator() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [apiError, setApiError] = useState('');

  // 1. Initialize React Hook Form with Zod
  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm({
    resolver: zodResolver(calculatorSchema),
    defaultValues: { asin: '' },
    mode: 'onChange'
  });

  const asinValue = watch('asin');

  // 2. Debounced database existence lookup (500ms delay)
  useEffect(() => {
    if (!asinValue || asinValue.length < 10) {
      setStatusMessage('');
      return;
    }

    const normalized = asinValue.trim().toUpperCase();
    if (!/^B[0-9A-Z]{9}$/.test(normalized)) {
      setStatusMessage('');
      return;
    }

    const delay = setTimeout(async () => {
      setStatusMessage('Checking database…');
      try {
        const data = await lookupASIN(normalized);
        if (data) {
          setStatusMessage('✓ Product found (Telemetric Audit available)');
        } else {
          setStatusMessage('⚠ Product not in database (Projected Baseline Scrape will run)');
        }
      } catch (e) {
        setStatusMessage('');
      }
    }, 500);

    return () => clearTimeout(delay);
  }, [asinValue]);

  // 3. Auto-fill ASIN from URL query param
  useEffect(() => {
    const urlAsin = searchParams.get('asin');
    if (urlAsin && urlAsin.trim().length >= 10) {
      const normalized = urlAsin.trim().toUpperCase();
      setValue('asin', normalized);
      handleAnalyze({ asin: normalized });
    }
  }, [searchParams, setValue]);

  const handleAnalyze = useCallback(async (formData) => {
    const trimmed = formData.asin.trim().toUpperCase();
    
    setLoading(true);
    setApiError('');
    setStatusMessage('Initiating vector crawl…');

    try {
      const data = await lookupASIN(trimmed);

      // Enrich with backend COSMO semantic analysis (non-blocking)
      let backendAnalysis = null;
      try {
        backendAnalysis = await fetchBackendAnalysis(trimmed);
      } catch (e) {
        // Silently ignore backend fetch errors
      }

      if (data && data.rufus_score != null) {
        // ASIN found in DB — go straight to results
        const results = calculateRufusScore({ category: data.category || 'other' }, data, backendAnalysis);
        navigate('/results', { state: { asin: trimmed, prospect: data, results, backendAnalysis } });
      } else if (data) {
        // ASIN in DB but not scored yet — calculate score instantly on the client!
        const results = calculateRufusScore({ category: data.category || 'other' }, data, backendAnalysis);
        navigate('/results', { state: { asin: trimmed, prospect: data, results, isProjected: true, backendAnalysis } });
      } else {
        // ASIN not in DB — compute a baseline score instantly and show results!
        const fallbackProspect = {
          asin: trimmed,
          brand: 'Brand Preview',
          category: 'other',
          post_title: 'Preview Product Listing Title',
          bullet_count: 3,
          image_count: 3,
          has_a_plus: false,
          qa_count: 0,
          listing_rating: 4.2,
          listing_review_count: 120,
        };
        const results = calculateRufusScore({ category: 'other' }, fallbackProspect, backendAnalysis);
        navigate('/results', { state: { asin: trimmed, prospect: fallbackProspect, results, isProjected: true, backendAnalysis } });
      }
    } catch (e) {
      console.error('ASIN lookup failed:', e);
      setApiError('Lookup failed. Please verify your connection and try again.');
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  return (
    <div className="app-bg">
      <div className="container">
        <header className="calc-header">
          <div className="brand-mark">
            <span className="brand-icon">◈</span>
            <span className="brand-name">OPTIMUS RUFUS</span>
          </div>
          <h1 className="calc-title">
            <span className="text-gradient">Rufus Visibility</span> Audit
          </h1>
          <p className="calc-subtitle">
            Enter your Amazon ASIN. We'll show you exactly what Rufus AI sees — and the 3 specific gaps costing you visibility.
          </p>
        </header>

        <form onSubmit={handleSubmit(handleAnalyze)} className="step-form animate-fade-in">
          <div className="glass-card step-card" style={{ maxWidth: 560, margin: '0 auto' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="asin-input">
                Amazon ASIN
              </label>
              <div className="asin-input-wrapper" style={{ display: 'flex', gap: 12 }}>
                <input
                  id="asin-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g. B07X4B7QFM"
                  {...register('asin')}
                  maxLength={10}
                  required
                  style={{ fontSize: '1.1rem', letterSpacing: '0.05em', flex: 1, textTransform: 'uppercase' }}
                  disabled={loading}
                />
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading || asinValue.trim().length < 10}
                  style={{ whiteSpace: 'nowrap', minWidth: 140 }}
                >
                  {loading ? 'Analyzing…' : 'Audit My Listing →'}
                </button>
              </div>

              {/* Real-time Validation Errors */}
              {errors.asin && (
                <span className="asin-status" style={{ color: 'var(--score-low)', marginTop: 8, fontSize: '0.8rem' }}>
                  {errors.asin.message}
                </span>
              )}

              {/* Status Telemetry Messages */}
              {!errors.asin && statusMessage && (
                <span className="asin-status text-mono" style={{ color: 'var(--amber-400)', marginTop: 8, fontSize: '0.8rem' }}>
                  {statusMessage}
                </span>
              )}

              {/* API Connection Errors */}
              {apiError && (
                <span className="asin-status" style={{ color: 'var(--score-low)', marginTop: 8, fontSize: '0.8rem' }}>
                  {apiError}
                </span>
              )}
            </div>

            <p className="text-xs text-muted" style={{ marginTop: 16, textAlign: 'center' }}>
              Free instant analysis. No email required to see your score and gaps.
            </p>
          </div>
        </form>

        {/* Trust signals */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 32, marginTop: 48, flexWrap: 'wrap' }}>
          <div className="trust-pill">
            <span style={{ fontSize: '1.2rem' }}>⚡</span>
            <span>Instant results</span>
          </div>
          <div className="trust-pill">
            <span style={{ fontSize: '1.2rem' }}>🔍</span>
            <span>Real Rufus data</span>
          </div>
          <div className="trust-pill">
            <span style={{ fontSize: '1.2rem' }}>🎯</span>
            <span>3 specific gaps</span>
          </div>
          <div className="trust-pill">
            <span style={{ fontSize: '1.2rem' }}>🏆</span>
            <span>Competitor comparison</span>
          </div>
        </div>
      </div>
    </div>
  );
}
