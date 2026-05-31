import { useState, useEffect } from 'react';
import { useParams, Navigate, Link } from 'react-router-dom';
import { getSubmission } from './supabase';
import { ScoreRing, AxisBar } from './components';
import { useCountUp, formatCurrency } from './utils';
import VectorRadar from './VectorRadar';
import './App.css';

export default function Profile() {
  const { id } = useParams();
  const [submission, setSubmission] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [revealStarted, setRevealStarted] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const data = await getSubmission(id);
        setSubmission(data);
        if (data) {
          setTimeout(() => setRevealStarted(true), 400);
        }
      } catch (err) {
        console.error(err);
        setError("Failed to load profile. Please try again.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const results = submission?.results || {};
  const animatedScore = useCountUp(results?.displayScore || 0, 1400, revealStarted);

  if (loading) {
    return (
      <div className="app-bg flex-center" style={{ minHeight: '100vh' }}>
        <div className="text-muted">Loading your Rufus Visibility profile…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-bg flex-center" style={{ minHeight: '100vh' }}>
        <div className="text-muted">{error}</div>
      </div>
    );
  }

  if (!submission || !results) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="app-bg">
      <div className="container">
        {/* Header */}
        <header className="calc-header">
          <Link to="/" style={{ textDecoration: 'none' }}>
            <div className="brand-mark">
              <span className="brand-icon">◈</span>
              <span className="brand-name">OPTIMUS RUFUS</span>
            </div>
          </Link>
          <h1 className="calc-title">
            <span className="text-gradient">Rufus Visibility</span> Profile
          </h1>
          <p className="calc-subtitle">
            ASIN: <strong className="text-mono">{submission.asin}</strong>
          </p>
        </header>

        <div className="results-view animate-fade-in">
          {/* Main Score */}
          <div className="glass-card results-hero">
            <div className="results-hero-inner">
              <ScoreRing
                score={animatedScore}
                size={200}
                animated={revealStarted}
              />
              <div className="results-hero-text">
                <h2 className="text-2xl">Your Rufus Visibility Score</h2>
                <div className="citation-badge-row">
                  <span className={`comparison-badge ${results.citationProbability}`}>
                    {results.citationProbability === 'low' ? '⚠ Low' : results.citationProbability === 'medium' ? '◐ Medium' : '✓ High'} Citation Probability
                  </span>
                </div>
                <p className="text-muted text-sm competitive-gap">
                  Your score: <strong className="text-mono">{results.displayScore}/100</strong>
                  {' · '}Category average: <strong className="text-mono">{results.categoryAvg}/100</strong>
                </p>
                {results?.hasActual === true && (
                  <div className="actual-vs-self">
                    <span className="text-xs text-muted">Self-reported: {results.selfTotal}/100</span>
                    <span className="text-xs" style={{ color: 'var(--amber-400)' }}>
                      Actual Rufus Score: {results.actualTotal}/100
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Visual Semantic Radar Map */}
          <div className="glass-card vector-radar-card animate-fade-in-up animate-delay-1" style={{ padding: '24px' }}>
            <h3 style={{ marginBottom: 8, fontSize: '1.1rem', color: 'var(--amber-400)' }}>🌌 Visual Semantic Radar Map</h3>
            <p className="text-muted text-xs" style={{ marginBottom: 16, lineHeight: 1.4 }}>
              This radar shows your product (pulsing center node) in the Amazon COSMO semantic vector space. The closer a cluster lies to the center, the stronger your listing's indexing is.
            </p>
            <VectorRadar scores={results.displayScores} category={submission.category} brand={submission.brand || 'Your Product'} />
          </div>

          {/* Per-Axis Breakdown */}
          <div className="glass-card axis-breakdown animate-fade-in-up animate-delay-2">
            <h3>Per-Axis Breakdown</h3>
            <div className="axis-bars">
              <AxisBar label="Intent Alignment" score={results.displayScores.intentAlignment} animated={revealStarted} delay={0.5} />
              <AxisBar label="Attribute Density" score={results.displayScores.attributeDensity} animated={revealStarted} delay={0.7} />
              <AxisBar label="Conversational Readability" score={results.displayScores.conversationalReadability} animated={revealStarted} delay={0.9} />
              <AxisBar label="Q&A Coverage" score={results.displayScores.qaCoverage} animated={revealStarted} delay={1.1} />
            </div>
          </div>

          {/* Revenue Impact */}
          {results?.revenueImpact !== undefined && (
            <div className="glass-card revenue-section animate-fade-in-up animate-delay-5">
              <h3>Estimated Revenue Impact</h3>
              <p className="text-muted text-sm">Based on real optimization outcomes for listings in your score range.</p>

              <div className="annual-gap">
                <span className="text-sm text-muted">Estimated annual revenue you're leaving on the table</span>
                <div className="annual-gap-amount text-gradient text-4xl text-mono">
                  ${results.revenueImpact.annualGap?.toLocaleString()}
                </div>
              </div>

              <div className="projection-grid grid-3">
                <div className="revenue-card">
                  <div className="revenue-period">30 Days</div>
                  <div className="revenue-amount">{formatCurrency(results.revenueImpact.projections.day30.realistic)}</div>
                  <div className="text-xs text-muted">{formatCurrency(results.revenueImpact.projections.day30.conservative)} – {formatCurrency(results.revenueImpact.projections.day30.aggressive)}</div>
                </div>
                <div className="revenue-card highlight">
                  <div className="revenue-period">60 Days</div>
                  <div className="revenue-amount">{formatCurrency(results.revenueImpact.projections.day60.realistic)}</div>
                  <div className="text-xs text-muted">{formatCurrency(results.revenueImpact.projections.day60.conservative)} – {formatCurrency(results.revenueImpact.projections.day60.aggressive)}</div>
                </div>
                <div className="revenue-card highlight">
                  <div className="revenue-period">90 Days</div>
                  <div className="revenue-amount">{formatCurrency(results.revenueImpact.projections.day90.realistic)}</div>
                  <div className="text-xs text-muted">{formatCurrency(results.revenueImpact.projections.day90.conservative)} – {formatCurrency(results.revenueImpact.projections.day90.aggressive)}</div>
                </div>
              </div>
            </div>
          )}

          {/* The 3 Gaps */}
          {results?.gaps !== undefined && results.gaps.length > 0 && (
            <div className="glass-card animate-fade-in-up animate-delay-4" style={{ padding: 'var(--space-xl)' }}>
              <h3 style={{ marginBottom: 'var(--space-lg)', fontSize: '1.1rem' }}>🎯 3 Specific Gaps Costing You Visibility</h3>
              <div className="gaps-list">
                {results.gaps.map((gap, i) => (
                  <div key={i} className="gap-card animate-fade-in-up" style={{ animationDelay: `${0.3 + i * 0.15}s` }}>
                    <div className="gap-number">{i + 1}</div>
                    <div className="gap-content">
                      <div className="gap-title">{gap.title}</div>
                      <div className="gap-detail">{gap.detail}</div>
                      <div className="gap-fix">→ <strong>Fix:</strong> {gap.fix}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actual Listing Data */}
          {results.listingMeta && (
            <div className="glass-card listing-meta animate-fade-in-up animate-delay-6">
              <h3>Your Listing Data</h3>
              <p className="text-muted text-sm">Pulled from our database — this is what Rufus actually sees.</p>
              <div className="listing-stats grid-2">
                <div className="listing-stat">
                  <span className="listing-stat-label">Bullets</span>
                  <span className="listing-stat-value text-mono">{results.listingMeta.bulletCount || 0}</span>
                </div>
                <div className="listing-stat">
                  <span className="listing-stat-label">Images</span>
                  <span className="listing-stat-value text-mono">{results.listingMeta.imageCount || 0}</span>
                </div>
                <div className="listing-stat">
                  <span className="listing-stat-label">Q&A Pairs</span>
                  <span className="listing-stat-value text-mono">{results.listingMeta.qaCount || 0}</span>
                </div>
                <div className="listing-stat">
                  <span className="listing-stat-label">Reviews</span>
                  <span className="listing-stat-value text-mono">{results.listingMeta.reviewCount?.toLocaleString() || 0}</span>
                </div>
                <div className="listing-stat">
                  <span className="listing-stat-label">Rating</span>
                  <span className="listing-stat-value text-mono">{results.listingMeta.rating || '—'} ⭐</span>
                </div>
                <div className="listing-stat">
                  <span className="listing-stat-label">A+ Content</span>
                  <span className="listing-stat-value text-mono">{results.listingMeta.hasAPlus ? '✓ Yes' : '✗ No'}</span>
                </div>
              </div>
              {results.listingMeta.summary && (
                <div className="listing-summary">
                  <strong>Rufus AI Assessment:</strong> {results.listingMeta.summary}
                </div>
              )}
            </div>
          )}

          {/* Minimalist Contact CTA */}
          <div className="glass-card cta-section animate-fade-in-up animate-delay-7" style={{ padding: 'var(--space-xl)', textAlign: 'center', marginBottom: 24 }}>
            <h3>Optimus Rufus Optimization</h3>
            <p className="text-sm" style={{ color: 'var(--dark-200)', maxWidth: 500, margin: '0 auto 20px', lineHeights: 1.5 }}>
              Need professional assistance implementing these COSMO-aligned enhancements? 
              Get in touch with our specialist team for listing rewrite and optimization support.
            </p>
            <a
              href="mailto:team@optimusrufus.com?subject=Amazon Rufus Optimization Support"
              className="btn btn-primary submit-btn"
              style={{ maxWidth: 280, margin: '0 auto' }}
            >
              Contact Our Team →
            </a>
          </div>

          {/* Footer */}
          <footer className="calc-footer">
            <p className="text-xs text-muted">
              Rufus Visibility Score is based on the same 4-axis model used by Optimus Rufus to audit Amazon listings for AI-driven shopping visibility. Projections are estimates based on observed optimization outcomes and are not guaranteed results.
            </p>
            <p className="text-xs text-muted" style={{ marginTop: '0.5rem' }}>
              © {new Date().getFullYear()} Optimus Rufus · <a href="https://optimusrufus.com" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--amber-600)' }}>optimusrufus.com</a>
            </p>
          </footer>
        </div>
      </div>
    </div>
  );
}
