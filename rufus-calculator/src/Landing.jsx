import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

/* ── Tiny animated score ring teaser ── */
function TeaserRing({ score, label, delay = 0 }) {
  const [animated, setAnimated] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setAnimated(true), delay);
    return () => clearTimeout(t);
  }, [delay]);

  const size = 88;
  const radius = (size - 12) / 2;
  const circ = 2 * Math.PI * radius;
  const pct = score / 100;
  const offset = circ * (1 - (animated ? pct : 0));
  const hue = pct * 120;
  const color = `hsl(${hue}, 72%, 50%)`;

  return (
    <div className="lp-teaser-ring" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} style={{ position: 'absolute', inset: 0, transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={6} />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke={color} strokeWidth={6} strokeLinecap="round"
          strokeDasharray={circ} strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.25,0.46,0.45,0.94)' }}
        />
      </svg>
      <div className="lp-teaser-ring-inner">
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700, color }}>{score}</span>
        <span style={{ fontSize: '0.55rem', color: 'var(--dark-400)', textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 1 }}>{label}</span>
      </div>
    </div>
  );
}

/* ── Axis bar teaser ── */
function MiniBar({ label, score, max = 25, delay = 0, color }) {
  const [animated, setAnimated] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setAnimated(true), delay);
    return () => clearTimeout(t);
  }, [delay]);
  const pct = (score / max) * 100;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '0.7rem', color: 'var(--dark-300)', fontFamily: 'var(--font-mono)' }}>{label}</span>
        <span style={{ fontSize: '0.7rem', fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>{score}/{max}</span>
      </div>
      <div style={{ height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{
          height: '100%', borderRadius: 99,
          background: `linear-gradient(90deg, ${color}, ${color}88)`,
          width: animated ? `${pct}%` : '0%',
          transition: `width 1s cubic-bezier(0.25,0.46,0.45,0.94) ${delay}ms`,
        }} />
      </div>
    </div>
  );
}

/* ── Animated counter ── */
function Counter({ target, prefix = '', suffix = '', duration = 1600, delay = 0 }) {
  const [val, setVal] = useState(0);
  const started = useRef(false);
  const ref = useRef(null);

  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !started.current) {
        started.current = true;
        const t = setTimeout(() => {
          const start = performance.now();
          const tick = (now) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setVal(Math.round(eased * target));
            if (progress < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        }, delay);
        return () => clearTimeout(t);
      }
    }, { threshold: 0.3 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [target, duration, delay]);

  return <span ref={ref}>{prefix}{val.toLocaleString()}{suffix}</span>;
}

/* ── Fade-in on scroll ── */
function FadeIn({ children, delay = 0, className = '', style = {} }) {
  const ref = useRef(null);
  const [vis, setVis] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setVis(true); obs.disconnect(); }
    }, { threshold: 0.1 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  return (
    <div ref={ref} className={className} style={{
      opacity: vis ? 1 : 0,
      transform: vis ? 'translateY(0)' : 'translateY(28px)',
      transition: `opacity 0.65s ease ${delay}ms, transform 0.65s cubic-bezier(0.25,0.46,0.45,0.94) ${delay}ms`,
      ...style,
    }}>
      {children}
    </div>
  );
}

/* ── Step card ── */
function StepCard({ num, title, body, delay }) {
  return (
    <FadeIn delay={delay}>
      <div className="lp-step-card">
        <div className="lp-step-num">{num}</div>
        <h3 className="lp-step-title">{title}</h3>
        <p className="lp-step-body">{body}</p>
      </div>
    </FadeIn>
  );
}

/* ── Feature card ── */
function FeatureCard({ icon, title, body, delay, accent }) {
  return (
    <FadeIn delay={delay}>
      <div className="lp-feature-card glass-card" style={{ '--lp-accent': accent }}>
        <div className="lp-feature-icon">{icon}</div>
        <h3 className="lp-feature-title">{title}</h3>
        <p className="lp-feature-body">{body}</p>
      </div>
    </FadeIn>
  );
}

export default function Landing() {
  const [heroVisible, setHeroVisible] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setHeroVisible(true), 80);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="lp-root app-bg">
      {/* ── NAV ── */}
      <nav className="lp-nav">
        <div className="lp-nav-inner">
          <Link to="/" className="lp-logo" aria-label="Optimus Rufus home">
            <span className="lp-logo-icon">◈</span>
            <span className="lp-logo-text">OPTIMUS RUFUS</span>
          </Link>
          <div className="lp-nav-actions">
            <Link to="/calculator" className="btn btn-primary lp-nav-cta">
              Audit My Listing
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                <path d="M2.5 7h9M7.5 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </Link>
          </div>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section className="lp-hero">
        <div className="lp-hero-grid">
          {/* Left column — copy */}
          <div className="lp-hero-copy">
            <div
              className="lp-eyebrow"
              style={{ opacity: heroVisible ? 1 : 0, transform: heroVisible ? 'translateY(0)' : 'translateY(16px)', transition: 'all 0.5s ease 0.1s' }}
            >
              <span className="lp-eyebrow-dot" />
              Amazon Rufus AI Optimization
            </div>

            <h1
              className="lp-hero-headline"
              style={{ opacity: heroVisible ? 1 : 0, transform: heroVisible ? 'translateY(0)' : 'translateY(24px)', transition: 'all 0.6s ease 0.2s' }}
            >
              Is Rufus Recommending{' '}
              <span className="text-gradient">You</span>
              {' '}— Or Your Competitor?
            </h1>

            <p
              className="lp-hero-sub"
              style={{ opacity: heroVisible ? 1 : 0, transform: heroVisible ? 'translateY(0)' : 'translateY(20px)', transition: 'all 0.6s ease 0.35s' }}
            >
              Amazon's Rufus AI is now answering millions of shopping questions daily.
              Find out exactly where your listing ranks — and the 3 specific gaps costing you visibility.
            </p>

            <div
              className="lp-hero-cta-row"
              style={{ opacity: heroVisible ? 1 : 0, transform: heroVisible ? 'translateY(0)' : 'translateY(20px)', transition: 'all 0.6s ease 0.5s' }}
            >
              <Link to="/calculator" className="btn btn-primary btn-lg lp-cta-btn">
                Get Your Free Audit
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </Link>
              <span className="lp-cta-note">Free · No email required · 90-second results</span>
            </div>

            <div
              className="lp-trust-row"
              style={{ opacity: heroVisible ? 1 : 0, transition: 'opacity 0.6s ease 0.7s' }}
            >
              <div className="trust-pill"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l2.8 2.8L10 3" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg> Real Rufus signals</div>
              <div className="trust-pill"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l2.8 2.8L10 3" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg> 4-axis breakdown</div>
              <div className="trust-pill"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l2.8 2.8L10 3" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg> Revenue gap estimate</div>
            </div>
          </div>

          {/* Right column — score preview widget */}
          <div
            className="lp-hero-widget"
            style={{ opacity: heroVisible ? 1 : 0, transform: heroVisible ? 'translateY(0) scale(1)' : 'translateY(32px) scale(0.97)', transition: 'all 0.8s cubic-bezier(0.34,1.2,0.64,1) 0.55s' }}
          >
            <div className="lp-widget-card glass-card">
              <div className="lp-widget-header">
                <div className="lp-widget-badge">
                  <span className="lp-widget-pulse" />
                  LIVE AUDIT PREVIEW
                </div>
                <span className="lp-widget-asin text-mono">B09XJ8K4Z1</span>
              </div>

              {/* Main score */}
              <div className="lp-widget-score-row">
                <TeaserRing score={34} label="Your Score" delay={900} />
                <div className="lp-widget-vs">
                  <div className="lp-vs-label">vs category avg</div>
                  <TeaserRing score={71} label="Avg Score" delay={1100} />
                </div>
              </div>

              {/* Axis bars */}
              <div className="lp-widget-bars">
                <MiniBar label="Intent Alignment" score={8} max={25} delay={1100} color="#f43f5e" />
                <MiniBar label="Attribute Density" score={11} max={25} delay={1250} color="#fbbf24" />
                <MiniBar label="Conversational Readability" score={7} max={25} delay={1400} color="#f43f5e" />
                <MiniBar label="Q&A Coverage" score={8} max={25} delay={1550} color="#fbbf24" />
              </div>

              {/* Revenue gap */}
              <div className="lp-widget-gap">
                <span className="lp-gap-label">Estimated Annual Revenue Gap</span>
                <span className="lp-gap-amount text-mono">
                  −$<Counter target={84200} duration={1800} delay={600} />
                </span>
              </div>

              <div className="lp-widget-footer-note">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="5" stroke="#00f5ff" strokeWidth="1"/><path d="M6 5.5V8.5M6 3.5v.5" stroke="#00f5ff" strokeWidth="1.2" strokeLinecap="round"/></svg>
                This is a sample preview — your real score may differ
              </div>
            </div>
          </div>
        </div>

        {/* Decorative diagonal line */}
        <div className="lp-hero-deco" aria-hidden="true" />
      </section>

      {/* ── STAT STRIP ── */}
      <section className="lp-stats-strip">
        <div className="lp-stats-inner">
          <div className="lp-stat">
            <span className="lp-stat-num text-mono">
              <Counter target={47} suffix="%" duration={1400} delay={0} />
            </span>
            <span className="lp-stat-label">of shoppers now use Rufus before buying</span>
          </div>
          <div className="lp-stat-divider" />
          <div className="lp-stat">
            <span className="lp-stat-num text-mono">
              <Counter target={3} duration={800} delay={100} />
            </span>
            <span className="lp-stat-label">specific gaps found in avg listing</span>
          </div>
          <div className="lp-stat-divider" />
          <div className="lp-stat">
            <span className="lp-stat-num text-mono">
              90<span style={{ fontSize: '0.7em' }}>s</span>
            </span>
            <span className="lp-stat-label">to see your full Rufus audit</span>
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section className="lp-section">
        <FadeIn>
          <div className="lp-section-label">How It Works</div>
          <h2 className="lp-section-headline">Three steps to your Rufus score</h2>
        </FadeIn>

        <div className="lp-steps-grid">
          <StepCard
            num="01"
            title="Enter Your ASIN"
            body="Paste your 10-character Amazon product ID. We cross-reference our database and begin vector analysis instantly."
            delay={100}
          />
          <StepCard
            num="02"
            title="We Analyze 4 Rufus Axes"
            body="Intent Alignment, Attribute Density, Conversational Readability, and Q&A Coverage — the exact factors Rufus weighs."
            delay={220}
          />
          <StepCard
            num="03"
            title="See Your Gaps and Revenue Cost"
            body="Get a scored breakdown, competitor comparison, and the exact revenue you're leaving on the table right now."
            delay={340}
          />
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section className="lp-section lp-features-section">
        <FadeIn>
          <div className="lp-section-label">What You Get</div>
          <h2 className="lp-section-headline">Everything you need to win in Rufus search</h2>
        </FadeIn>

        <div className="lp-features-grid">
          <FeatureCard
            icon={
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M12 7v5l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            }
            title="Real-Time Rufus Score"
            body="A single 0–100 score showing exactly how visible your listing is to Amazon's AI shopping assistant."
            delay={100}
            accent="#00f5ff"
          />
          <FeatureCard
            icon={
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M3 17l4-8 4 4 4-6 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            }
            title="4-Axis Breakdown"
            body="Granular scores across Intent Alignment, Attribute Density, Conversational Readability, and Q&A Coverage."
            delay={200}
            accent="#38bdf8"
          />
          <FeatureCard
            icon={
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17 5.8 21.3l2.4-7.4L2 9.4h7.6L12 2z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            }
            title="Competitor Comparison"
            body="See how your listing stacks up against the category average and understand exactly where you fall behind."
            delay={300}
            accent="#a78bfa"
          />
          <FeatureCard
            icon={
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            }
            title="Revenue Gap Estimate"
            body="Dollar-quantified impact: see the monthly and annual revenue you're missing due to low Rufus visibility."
            delay={400}
            accent="#10b981"
          />
          <FeatureCard
            icon={
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            }
            title="Invisible Query Detection"
            body="Discover the exact shopper questions Rufus can't answer with your current listing — the blind spots costing you clicks."
            delay={500}
            accent="#f59e0b"
          />
          <FeatureCard
            icon={
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M13 10V3L4 14h7v7l9-11h-7z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            }
            title="Instant, No Login Required"
            body="No account. No credit card. Just your ASIN and 90 seconds. See your real Rufus audit right now."
            delay={600}
            accent="#00f5ff"
          />
        </div>
      </section>

      {/* ── BOTTOM CTA ── */}
      <section className="lp-cta-banner">
        <FadeIn className="lp-cta-inner">
          <div className="lp-cta-glow" aria-hidden="true" />
          <div className="lp-section-label" style={{ marginBottom: '1rem' }}>Ready?</div>
          <h2 className="lp-cta-headline">
            Find out where Rufus<br />ranks your listing — free
          </h2>
          <p className="lp-cta-sub">
            Enter any Amazon ASIN and get your Rufus Visibility Score in under 90 seconds.
          </p>
          <Link to="/calculator" className="btn btn-primary btn-lg lp-cta-btn" style={{ marginTop: '2rem' }}>
            Run Free Audit Now
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </Link>
          <p className="lp-cta-disclaimer">Free · Instant results · No account needed</p>
        </FadeIn>
      </section>

      {/* ── FOOTER ── */}
      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <div className="lp-logo" style={{ opacity: 0.5 }}>
            <span className="lp-logo-icon">◈</span>
            <span className="lp-logo-text">OPTIMUS RUFUS</span>
          </div>
          <p className="lp-footer-copy">
            Not affiliated with Amazon. Rufus scoring is based on independently observed citation patterns.
          </p>
          <div className="lp-footer-links">
            <Link to="/calculator" style={{ color: 'var(--dark-400)', fontSize: '0.8rem', textDecoration: 'none' }}>Audit Tool</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
