import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ScoreRing } from './components';
import { useSubmission } from './supabase';
import { calculateRevenueImpact, getCitationProbability } from './calculator';
import VectorRadar from './VectorRadar';
import './App.css';

// Premium SVG Outline Icons (No Emojis)
function LockIcon({ size = 18 }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
    </svg>
  );
}

function MailIcon({ size = 18 }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
      <polyline points="22,6 12,13 2,6"></polyline>
    </svg>
  );
}

export default function Results() {
  const location = useLocation();
  const navigate = useNavigate();
  const { asin, prospect, results, isProjected } = location.state || {};

  // Custom hook for submissions
  const { submit } = useSubmission();

  // Redirect if no data
  useEffect(() => {
    if (!asin) {
      navigate('/', { replace: true });
    }
  }, [asin, navigate]);

  if (!asin) return null;

  const displayScore = results?.displayScore || 0;
  const displayScores = results?.displayScores || {
    intentAlignment: 5,
    attributeDensity: 5,
    conversationalReadability: 12,
    qaCoverage: 0
  };

  // 1. Baseline audited scores
  const originalIntent = displayScores.intentAlignment || 5;
  const originalAttribute = displayScores.attributeDensity || 5;
  const originalReadability = displayScores.conversationalReadability || 12;
  const originalQA = displayScores.qaCoverage || 0;

  // 2. Interactive simulator states (clamped to at least original audit baseline)
  const [simIntent, setSimIntent] = useState(originalIntent);
  const [simAttribute, setSimAttribute] = useState(originalAttribute);
  const [simReadability, setSimReadability] = useState(originalReadability);
  const [simQA, setSimQA] = useState(originalQA);

  // 3. ROI states
  const [monthlyRevenue, setMonthlyRevenue] = useState(25000);
  const [category, setCategory] = useState(prospect?.category || 'other');

  // 4. Progressive unlock states
  const [email, setEmail] = useState(prospect?.contact_email || '');
  const [isUnlocked, setIsUnlocked] = useState(!!prospect?.contact_email);
  const [submitting, setSubmitting] = useState(false);

  // Calculate live simulated score dynamically
  const simulatedScore = Math.min(100, Math.max(0, simIntent + simAttribute + simReadability + simQA));
  const citationProb = getCitationProbability(simulatedScore);

  // Calculate dynamic ROI lift compared to the audited baseline
  const diffIntent = Math.max(0, simIntent - originalIntent);
  const diffAttribute = Math.max(0, simAttribute - originalAttribute);
  const diffReadability = Math.max(0, simReadability - originalReadability);
  const diffQA = Math.max(0, simQA - originalQA);

  // Map slider metrics to S-Curve coefficients
  const imageLift = (diffIntent / 25) * 0.17;
  const copyLift = (diffAttribute / 25) * 0.12;
  const ppcLift = (diffReadability / 25) * 0.22;
  const qaLift = (diffQA / 25) * 0.08;

  // Apply overlap synergy-aware dampening
  let areasImproved = 0;
  if (diffIntent > 0) areasImproved++;
  if (diffAttribute > 0) areasImproved++;
  if (diffReadability > 0) areasImproved++;
  if (diffQA > 0) areasImproved++;

  let dampening = 1.0;
  if (areasImproved > 1) {
    dampening = 1.0 - 0.05 * (areasImproved - 1);
  }
  dampening = Math.max(0.70, dampening);
  const combinedLift = (imageLift + copyLift + ppcLift + qaLift) * dampening;

  // Category modifiers lookup
  const categoryModifiers = {
    supplements: 0.85,
    beauty: 0.90,
    skincare: 0.90,
    electronics: 1.10,
    pet: 1.00,
    sports: 1.00,
    fitness: 1.00,
    kitchen: 1.05,
    home: 1.05,
    'essential oils': 0.85,
    'golf apparel': 1.00,
    nutrition: 0.85,
    other: 1.00,
  };
  const modifier = categoryModifiers[category] || 1.0;
  const rating = prospect?.listing_rating || 4.2;
  const reviewCount = prospect?.listing_review_count || 120;

  let countMultiplier = 1.0;
  if (reviewCount < 10) countMultiplier = 0.70;
  else if (reviewCount < 50) countMultiplier = 0.85;

  const ratingMultiplier = Math.pow(Math.max(1.0, Math.min(5.0, rating)) / 5.0, 0.5);
  const finalLift = combinedLift * modifier * countMultiplier * ratingMultiplier;

  // Projections
  const monthlyGain = Math.round(monthlyRevenue * finalLift);
  const annualGain = monthlyGain * 12;

  const handleUnlockSubmit = async (e) => {
    e.preventDefault();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return;

    setSubmitting(true);
    await submit({
      email,
      asin,
      category,
      actualRufusScore: displayScore,
      monthlyRevenue,
      selfIntent: Math.max(1, Math.round((simIntent / 25) * 5)),
      selfAttribute: Math.max(1, Math.round((simAttribute / 25) * 5)),
      selfReadability: Math.max(1, Math.round((simReadability / 25) * 5)),
      selfReportedScore: totalScoreToSubmit(),
      results: {
        simulatedScore,
        citationProb,
        annualGain,
        finalLift
      }
    });
    setSubmitting(false);
    setIsUnlocked(true);
  };

  const totalScoreToSubmit = () => simulatedScore;

  return (
    <div className="app-bg" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', padding: '40px 20px' }}>
      <div className="container" style={{ maxWidth: '680px', margin: '0 auto', width: '100%', position: 'relative', zIndex: 1 }}>
        
        {/* Sleek Logo and Header */}
        <header className="calc-header" style={{ padding: '0 0 24px', textAlign: 'center' }}>
          <div className="brand-mark" style={{ display: 'inline-flex', padding: '4px 12px', borderRadius: '4px', background: 'rgba(0, 245, 255, 0.05)', border: '1px solid rgba(0, 245, 255, 0.15)', marginBottom: 12 }}>
            <span className="brand-name" style={{ fontFamily: 'var(--font-display)', fontSize: '0.65rem', letterSpacing: '0.25em', color: 'var(--amber-400)' }}>◈ DIAGNOSTICS CONSOLE</span>
          </div>
          <p className="calc-subtitle" style={{ fontSize: '0.9rem', color: 'var(--dark-200)', margin: 0 }}>
            ASIN: <strong className="text-mono" style={{ color: 'var(--amber-400)' }}>{asin}</strong>
            {prospect?.brand && <> · Brand: <strong>{prospect.brand}</strong></>}
          </p>
        </header>

        {/* Dynamic Diagnostics console */}
        <div className="glass-card animate-fade-in" style={{ padding: 'var(--space-xl)', display: 'flex', flexDirection: 'column', gap: 24 }}>
          
          {/* Top Score Diagnostic Hub */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
            <ScoreRing score={simulatedScore} size={160} animated={true} />
            <div style={{ textAlign: 'center' }}>
              <div 
                className="comparison-badge" 
                style={{ 
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  fontSize: '0.7rem',
                  padding: '4px 12px',
                  borderRadius: '999px',
                  fontWeight: 700,
                  backgroundColor: citationProb === 'high' ? 'var(--score-high-bg)' : citationProb === 'medium' ? 'var(--score-medium-bg)' : 'var(--score-low-bg)',
                  color: citationProb === 'high' ? 'var(--score-high)' : citationProb === 'medium' ? 'var(--score-medium)' : 'var(--score-low)',
                  boxShadow: `0 0 15px ${citationProb === 'high' ? 'rgba(16, 185, 129, 0.15)' : citationProb === 'medium' ? 'rgba(251, 191, 36, 0.15)' : 'rgba(244, 63, 94, 0.15)'}`
                }}
              >
                {citationProb} Citation Probability
              </div>
              <p className="text-muted text-xs" style={{ marginTop: 8 }}>
                Current simulated score. Drag the sliders below to optimize your visibility.
              </p>
            </div>
          </div>

          {/* Visual Semantic Radar Map */}
          <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.05)', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', padding: '16px 0' }}>
            <VectorRadar 
              scores={{
                intentAlignment: simIntent,
                attributeDensity: simAttribute,
                conversationalReadability: simReadability,
                qaCoverage: simQA
              }} 
              category={category} 
              brand={prospect?.brand || 'Your Product'} 
            />
          </div>

          {/* Interactive Core Diagnostic Sliders */}
          <div className="simulator-controls" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '0.8rem', letterSpacing: '0.05em', color: 'var(--dark-200)', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: 6 }}>
              1. ADJUST AUDIT DIAGNOSTICS (MIN CLAMPED TO BASELINE)
            </h4>
            
            {/* Axis 1 */}
            <div className="sim-control-group">
              <div className="sim-control-header">
                <span className="sim-label">Intent Alignment</span>
                <span className="sim-value">{simIntent} / 25</span>
              </div>
              <input 
                type="range" 
                min={originalIntent} 
                max={25} 
                value={simIntent} 
                onChange={(e) => setSimIntent(parseInt(e.target.value))}
                className="sim-slider"
              />
              <span className="sim-tip">Audited: {originalIntent}/25 (Align listing keywords to shoppers queries)</span>
            </div>

            {/* Axis 2 */}
            <div className="sim-control-group">
              <div className="sim-control-header">
                <span className="sim-label">Attribute Density</span>
                <span className="sim-value">{simAttribute} / 25</span>
              </div>
              <input 
                type="range" 
                min={originalAttribute} 
                max={25} 
                value={simAttribute} 
                onChange={(e) => setSimAttribute(parseInt(e.target.value))}
                className="sim-slider"
              />
              <span className="sim-tip">Audited: {originalAttribute}/25 (Structured measurable specifications inside bullets)</span>
            </div>

            {/* Axis 3 */}
            <div className="sim-control-group">
              <div className="sim-control-header">
                <span className="sim-label">Conversational Readability</span>
                <span className="sim-value">{simReadability} / 25</span>
              </div>
              <input 
                type="range" 
                min={originalReadability} 
                max={25} 
                value={simReadability} 
                onChange={(e) => setSimReadability(parseInt(e.target.value))}
                className="sim-slider"
              />
              <span className="sim-tip">Audited: {originalReadability}/25 (Dialogue-driven product descriptions & A+ copy)</span>
            </div>

            {/* Axis 4 */}
            <div className="sim-control-group">
              <div className="sim-control-header">
                <span className="sim-label">Q&A Coverage</span>
                <span className="sim-value">{simQA} / 25</span>
              </div>
              <input 
                type="range" 
                min={originalQA} 
                max={25} 
                value={simQA} 
                onChange={(e) => setSimQA(parseInt(e.target.value))}
                className="sim-slider"
              />
              <span className="sim-tip">Audited: {originalQA}/25 (Answering high-density shopper dialogues pre-purchase)</span>
            </div>
          </div>

          {/* S-Curve ROI growth Module */}
          <div className="simulator-controls" style={{ display: 'flex', flexDirection: 'column', gap: 16, position: 'relative' }}>
            <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '0.8rem', letterSpacing: '0.05em', color: 'var(--dark-200)', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', paddingBottom: 6 }}>
              2. ATTRIBUTED REVENUE UPLIFT PROJECTIONS
            </h4>

            {/* Unlocked Active Projections Console */}
            <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              
              {/* Parameters Panel */}
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label" style={{ fontSize: '0.75rem' }}>Monthly Revenue</label>
                  <div className="revenue-input-wrap">
                    <span className="revenue-prefix">$</span>
                    <input 
                      type="number" 
                      value={monthlyRevenue} 
                      onChange={(e) => setMonthlyRevenue(Math.max(0, parseInt(e.target.value) || 0))}
                      className="form-input revenue-input"
                      style={{ padding: '6px 12px 6px 24px', fontSize: '0.85rem' }}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontSize: '0.75rem' }}>Listing Category</label>
                  <select 
                    value={category} 
                    onChange={(e) => setCategory(e.target.value)}
                    className="form-select text-sm"
                    style={{ padding: '6px 36px 6px 12px', fontSize: '0.85rem' }}
                  >
                    <option value="supplements">Supplements (0.85x)</option>
                    <option value="beauty">Beauty (0.90x)</option>
                    <option value="skincare">Skincare (0.90x)</option>
                    <option value="electronics">Electronics (1.10x)</option>
                    <option value="pet">Pet Care (1.00x)</option>
                    <option value="sports">Sports (1.00x)</option>
                    <option value="fitness">Fitness (1.00x)</option>
                    <option value="kitchen">Kitchen & Home (1.05x)</option>
                    <option value="other">Other Categories (1.00x)</option>
                  </select>
                </div>
              </div>

              {/* Interactive Dynamic Metrics Readout */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 4 }}>
                <div className="revenue-card highlight" style={{ padding: '16px' }}>
                  <div className="revenue-period" style={{ fontSize: '0.65rem' }}>Attributed Monthly Gain</div>
                  <div className="revenue-amount" style={{ fontSize: '1.4rem' }}>+{monthlyGain ? `$${monthlyGain.toLocaleString()}` : '$0'}</div>
                </div>
                <div className="revenue-card" style={{ padding: '16px', background: 'rgba(0, 245, 255, 0.03)' }}>
                  <div className="revenue-period" style={{ fontSize: '0.65rem' }}>Attributed Annual Lift</div>
                  <div className="revenue-amount" style={{ fontSize: '1.4rem', color: '#10b981' }}>+{annualGain ? `$${annualGain.toLocaleString()}` : '$0'}</div>
                </div>
              </div>

              <p className="text-xs text-muted" style={{ fontStyle: 'italic', textAlign: 'center', marginTop: 4 }}>
                Attributed gain calculated dynamically using category modifiers and review double bottlenecks.
              </p>
            </div>
          </div>

          {/* Calendly Booking Strategy Card */}
          <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: 20, textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.1rem', color: 'var(--amber-400)', margin: '0 0 6px' }}>
                📅 Schedule Your Live Rufus Optimization Session
              </h3>
              <p className="text-muted text-xs" style={{ maxWidth: '480px', margin: '0 auto', lineHeight: 1.4 }}>
                Our RAG search architects will walk you through your live vector embedding map, analyze your competitor's conversational keyword gaps, and outline the exact roadmap to capture 10x more conversational search visibility.
              </p>
            </div>
            <div>
              <a
                className="btn btn-primary"
                href="https://calendly.com/optimus-rufus/strategy-session"
                target="_blank"
                rel="noopener noreferrer"
                style={{ padding: '10px 24px', display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', boxShadow: '0 0 20px rgba(0, 245, 255, 0.25)' }}
              >
                <span>Book Strategy Call →</span>
              </a>
            </div>
          </div>

        </div>

        {/* Minimal Footer */}
        <footer className="calc-footer" style={{ textAlign: 'center', marginTop: 24 }}>
          <p className="text-xs text-muted">
            © {new Date().getFullYear()} Optimus Rufus · <a href="https://optimusrufus.com" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--amber-400)', textDecoration: 'none' }}>optimusrufus.com</a>
          </p>
        </footer>

      </div>
    </div>
  );
}
