import { useState, useEffect } from 'react';

// ---- Tooltip helper for axes ----
function getTooltipText(label) {
  switch (label) {
    case 'Intent Alignment':
      return 'Measures how effectively your listing title and keywords match BSR category shopper search intent.';
    case 'Attribute Density':
      return 'Audits the count and structured, measurable specifications populated inside your bullet points.';
    case 'Conversational Readability':
      return 'Evaluates consumer dialog accessibility and presence of A+ content structuring.';
    case 'Q&A Coverage':
      return 'Measures Q&A count and density to match dialogue-driven shopping queries.';
    default:
      return 'Visual structured metrics score.';
  }
}

// ---- Score Ring SVG Component ----
export function ScoreRing({ score, maxScore = 100, size = 200, animated = false }) {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(media.matches);
    const listener = (e) => setReducedMotion(e.matches);
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  }, []);

  const radius = (size - 20) / 2;
  const circumference = 2 * Math.PI * radius;
  const percent = score / maxScore;
  const offset = circumference * (1 - (animated && !reducedMotion ? percent : percent));

  // Continuous HSL color ramp: Red (0) -> Yellow (60) -> emerald green (120)
  const hue = percent * 120;
  const color = `hsl(${hue}, 75%, 48%)`;

  return (
    <div 
      className="score-ring" 
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Rufus Visibility Score: ${score} out of ${maxScore}. Citation probability: ${score >= 70 ? 'High' : score >= 40 ? 'Medium' : 'Low'}.`}
    >
      <svg viewBox={`0 0 ${size} ${size}`}>
        <circle
          className="score-ring-bg"
          cx={size / 2} cy={size / 2} r={radius}
        />
        <circle
          className="score-ring-fill"
          cx={size / 2} cy={size / 2} r={radius}
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={reducedMotion ? { transition: 'none' } : {}}
        />
      </svg>
      <span className="score-value" style={{ color }}>{animated ? score : '—'}</span>
    </div>
  );
}

// ---- Axis Bar Component ----
export function AxisBar({ label, score, maxScore = 25, animated = false, delay = 0 }) {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(media.matches);
    const listener = (e) => setReducedMotion(e.matches);
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  }, []);

  const percent = (score / maxScore) * 100;
  const hue = (score / maxScore) * 120;
  const color = `hsl(${hue}, 75%, 46%)`;

  return (
    <div className="axis-bar animate-fade-in-up group relative" style={{ animationDelay: `${delay}s`, cursor: 'help' }}>
      {/* Premium hover tooltip — upgraded to Cyber Obsidian theme */}
      <div className="absolute hidden group-hover:block bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-56 p-2.5 bg-[#0b1329]/95 border border-[#00f5ff]/30 text-[11px] text-[#cbd5e1] rounded-md shadow-[0_10px_30px_rgba(0,245,255,0.15)] pointer-events-none z-50 text-center font-sans leading-relaxed backdrop-blur-md">
        <div style={{ fontWeight: 600, color: 'var(--amber-400)', marginBottom: 4 }}>{label}</div>
        {getTooltipText(label)}
      </div>

      <div className="axis-bar-header">
        <span className="axis-bar-label">{label}</span>
        <span className="axis-bar-score" style={{ color }}>{score}/{maxScore}</span>
      </div>
      <div className="axis-bar-track">
        <div
          className="axis-bar-fill"
          style={{
            width: animated ? `${percent}%` : '0%',
            background: `linear-gradient(90deg, ${color}, ${color}88)`,
            transitionDelay: reducedMotion ? '0s' : `${delay}s`,
            transition: reducedMotion ? 'none' : undefined,
          }}
        />
      </div>
    </div>
  );
}

// ---- Scale Selector Component ----
export function ScaleSelector({ value, onChange, id }) {
  const options = [
    { num: 1, label: '1 - Poor' },
    { num: 2, label: '2' },
    { num: 3, label: '3 - Average' },
    { num: 4, label: '4' },
    { num: 5, label: '5 - Excellent' },
  ];

  const handleKeyDown = (e, n) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      const next = n === 5 ? 1 : n + 1;
      onChange(next);
      document.getElementById(`${id}-opt-${next}`)?.focus();
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = n === 1 ? 5 : n - 1;
      onChange(prev);
      document.getElementById(`${id}-opt-${prev}`)?.focus();
    } else if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      onChange(n);
    }
  };

  return (
    <div className="scale-selector-wrap" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div className="scale-selector" id={id} role="radiogroup" aria-label="Quality Assessment Scale (1 to 5)">
        {options.map(o => (
          <button
            id={`${id}-opt-${o.num}`}
            key={o.num}
            type="button"
            className={`scale-option ${value === o.num ? 'active' : ''}`}
            onClick={() => onChange(o.num)}
            onKeyDown={(e) => handleKeyDown(e, o.num)}
            role="radio"
            aria-checked={value === o.num}
            tabIndex={value === o.num ? 0 : -1}
          >
            {o.num}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 4px', fontSize: '0.7rem' }} className="text-muted">
        <span>Poor (1)</span>
        <span>Average (3)</span>
        <span>Excellent (5)</span>
      </div>
    </div>
  );
}

// ---- Progress Indicator ----
export function ProgressSteps({ current, steps = ['Listing Details', 'Your Email', 'Rufus Score'] }) {
  return (
    <div className="progress-steps">
      {steps.map((label, i) => (
        <div key={i} className="progress-step">
          <div className={`progress-dot ${i + 1 === current ? 'active' : i + 1 < current ? 'completed' : ''}`} />
          <span className={`text-xs ${i + 1 === current ? '' : 'text-muted'}`}>{label}</span>
          {i < steps.length - 1 && (
            <div className={`progress-line ${i + 1 < current ? 'active' : ''}`} />
          )}
        </div>
      ))}
    </div>
  );
}
