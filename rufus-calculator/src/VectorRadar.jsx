import { useState, useEffect, useRef } from 'react';

export default function VectorRadar({ scores, category = 'other', brand = 'Your Product' }) {
  const [activeNode, setActiveNode] = useState(null);
  const [rotation, setRotation] = useState(0);
  const [showCompetitors, setShowCompetitors] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  
  const speedRef = useRef(0.25);

  // Dynamic slow continuous rotation + speed boost scanning
  useEffect(() => {
    let frameId;
    const animate = () => {
      // Exponentially decay scan speed back to the baseline drift speed
      if (speedRef.current > 0.25) {
        speedRef.current = Math.max(0.25, speedRef.current * 0.96);
      } else {
        setIsScanning(false);
      }
      setRotation((prev) => (prev + speedRef.current) % 360);
      frameId = requestAnimationFrame(animate);
    };
    frameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameId);
  }, []);

  const triggerScan = () => {
    if (isScanning) return;
    setIsScanning(true);
    speedRef.current = 14.0; // Boost spin rate!
  };

  // Safe checks for scores
  const sIntent = scores?.intentAlignment ?? 12;
  const sAttribute = scores?.attributeDensity ?? 12;
  const sReadability = scores?.conversationalReadability ?? 12;
  const sQA = scores?.qaCoverage ?? 12;

  // Total and average for telemetry
  const totalScore = sIntent + sAttribute + sReadability + sQA;
  const alignmentPercent = Math.min(100, Math.round((totalScore / 100) * 100));
  const healthStatus = totalScore >= 70 ? 'OPTIMAL' : totalScore >= 45 ? 'MODERATE' : 'CRITICAL DRIFT';
  const healthColor = totalScore >= 70 ? '#10b981' : totalScore >= 45 ? '#fbbf24' : '#f43f5e';

  // Radar Center coordinates
  const cx = 300;
  const cy = 175;

  // Maximum and minimum cluster radius
  const maxR = 120;
  const minR = 45;

  // Inversely calculate distance based on score (Higher score = closer to center, tight semantic fit)
  const getRadius = (score) => {
    const pct = Math.min(25, Math.max(0, score)) / 25; // Clamp 0 to 25
    return maxR - pct * (maxR - minR);
  };

  const rIntent = getRadius(sIntent);
  const rAttribute = getRadius(sAttribute);
  const rReadability = getRadius(sReadability);
  const rQA = getRadius(sQA);

  // Position angles (in radians) for the 4 axes
  const aIntent = (225 * Math.PI) / 180;
  const aAttribute = (315 * Math.PI) / 180;
  const aReadability = (45 * Math.PI) / 180;
  const aQA = (135 * Math.PI) / 180;

  // Dynamic cluster positions (with smooth transition style variables)
  const pIntent = { x: cx + rIntent * Math.cos(aIntent), y: cy + rIntent * Math.sin(aIntent) };
  const pAttribute = { x: cx + rAttribute * Math.cos(aAttribute), y: cy + rAttribute * Math.sin(aAttribute) };
  const pReadability = { x: cx + rReadability * Math.cos(aReadability), y: cy + rReadability * Math.sin(aReadability) };
  const pQA = { x: cx + rQA * Math.cos(aQA), y: cy + rQA * Math.sin(aQA) };

  // Fixed annotation positions
  const labelRadius = maxR + 25;
  const pIntentLabel = { x: cx + labelRadius * Math.cos(aIntent), y: cy + labelRadius * Math.sin(aIntent) };
  const pAttributeLabel = { x: cx + labelRadius * Math.cos(aAttribute), y: cy + labelRadius * Math.sin(aAttribute) };
  const pReadabilityLabel = { x: cx + labelRadius * Math.cos(aReadability), y: cy + labelRadius * Math.sin(aReadability) };
  const pQALabel = { x: cx + labelRadius * Math.cos(aQA), y: cy + labelRadius * Math.sin(aQA) };

  // Score colors (cyberneon theme)
  const getScoreColor = (score) => {
    const percent = score / 25;
    if (percent >= 0.75) return '#10b981'; // Neon Emerald
    if (percent >= 0.45) return '#fbbf24'; // Neon Amber
    return '#f43f5e'; // Hot Crimson
  };

  const colorIntent = getScoreColor(sIntent);
  const colorAttribute = getScoreColor(sAttribute);
  const colorReadability = getScoreColor(sReadability);
  const colorQA = getScoreColor(sQA);

  // Competitor orbits and coordinates
  const comp1Angle = (rotation * Math.PI) / 180;
  const comp2Angle = ((rotation + 180) * Math.PI) / 180;
  const comp1 = { x: cx + 110 * Math.cos(comp1Angle), y: cy + 110 * Math.sin(comp1Angle) };
  const comp2 = { x: cx + 85 * Math.cos(comp2Angle), y: cy + 85 * Math.sin(comp2Angle) };

  // Generate sweep wedge path
  const getWedgePath = (cx, cy, radius, rotationAngle) => {
    const startAngle = rotationAngle - 20;
    const endAngle = rotationAngle;
    const startRad = (startAngle * Math.PI) / 180;
    const endRad = (endAngle * Math.PI) / 180;
    const x1 = cx + radius * Math.cos(startRad);
    const y1 = cy + radius * Math.sin(startRad);
    const x2 = cx + radius * Math.cos(endRad);
    const y2 = cy + radius * Math.sin(endRad);
    return `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 0 1 ${x2} ${y2} Z`;
  };

  const sweepWedge = getWedgePath(cx, cy, maxR, rotation);

  // Shared spring transition style for dynamic SVG positioning
  const springStyle = {
    transition: 'all 0.5s cubic-bezier(0.16, 1, 0.3, 1)'
  };

  // Polygon points
  const polyPoints = `${pIntent.x},${pIntent.y} ${pAttribute.x},${pAttribute.y} ${pReadability.x},${pReadability.y} ${pQA.x},${pQA.y}`;

  return (
    <div style={{ 
      position: 'relative', 
      width: '100%', 
      maxWidth: '620px', 
      margin: '0 auto', 
      background: 'linear-gradient(135deg, rgba(8, 12, 22, 0.95) 0%, rgba(4, 6, 12, 0.98) 100%)', 
      border: '1px solid rgba(0, 245, 255, 0.15)', 
      borderRadius: '16px', 
      padding: '20px', 
      boxSizing: 'border-box',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.05)'
    }}>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes pulse-led {
          0%, 100% { opacity: 0.4; transform: scale(0.95); }
          50% { opacity: 1; transform: scale(1.15); filter: drop-shadow(0 0 6px currentColor); }
        }
        @keyframes telemetry-flicker {
          0%, 100% { opacity: 0.98; }
          45% { opacity: 0.98; }
          50% { opacity: 0.88; }
          52% { opacity: 0.98; }
          85% { opacity: 0.98; }
          87% { opacity: 0.80; }
          90% { opacity: 0.98; }
        }
        .pulse-led-element {
          animation: pulse-led 2s infinite ease-in-out;
        }
        .telemetry-panel {
          animation: telemetry-flicker 10s infinite ease-in-out;
        }
      `}} />
      
      {/* High-Tech Radar Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', borderBottom: '1px solid rgba(0, 245, 255, 0.08)', paddingBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span 
            className="pulse-led-element"
            style={{ 
              display: 'inline-block', 
              width: '6px', 
              height: '6px', 
              borderRadius: '50%', 
              backgroundColor: isScanning ? '#00f5ff' : '#10b981',
              color: isScanning ? '#00f5ff' : '#10b981',
            }} 
          />
          <h5 style={{ 
            fontFamily: 'var(--font-display)', 
            fontSize: '0.75rem', 
            letterSpacing: '0.15em', 
            color: '#cbd5e1', 
            margin: 0,
            textTransform: 'uppercase'
          }}>
            COSMO VECTOR SPACE ANALYZER
          </h5>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: '#64748b', background: 'rgba(0, 245, 255, 0.04)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(0, 245, 255, 0.08)' }}>
          LATENCY: <span style={{ color: '#00f5ff' }}>0.04ms</span>
        </div>
      </div>

      {/* High-Tech Integrated Telemetry HUD Overlay Panel */}
      <div 
        className="telemetry-panel"
        style={{
          backgroundColor: 'rgba(5, 8, 16, 0.85)',
          border: activeNode ? `1px solid ${activeNode.color}` : '1px solid rgba(0, 245, 255, 0.15)',
          borderRadius: '10px',
          padding: '12px 16px',
          minHeight: '74px',
          marginBottom: '16px',
          fontSize: '0.78rem',
          color: '#cbd5e1',
          boxShadow: activeNode ? `0 0 15px ${activeNode.color}20` : 'none',
          backdropFilter: 'blur(10px)',
          transition: 'all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center'
        }}
      >
        {activeNode ? (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', alignItems: 'center' }}>
              <span style={{ 
                fontFamily: 'var(--font-display)', 
                fontSize: '0.82rem', 
                color: activeNode.color,
                fontWeight: 'bold', 
                letterSpacing: '0.05em' 
              }}>
                ◈ {activeNode.title.toUpperCase()}
              </span>
              <strong style={{ 
                fontFamily: 'var(--font-mono)', 
                color: activeNode.color,
                fontSize: '0.85rem',
                backgroundColor: `${activeNode.color}15`,
                padding: '1px 8px',
                borderRadius: '4px',
                border: `1px solid ${activeNode.color}30`
              }}>
                {activeNode.score}
              </strong>
            </div>
            <div style={{ fontSize: '0.74rem', color: '#94a3b8', lineHeight: '1.4' }}>{activeNode.desc}</div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '16px', alignItems: 'center' }}>
            <div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: '0.75rem', color: '#00f5ff', letterSpacing: '0.05em', marginBottom: '2px' }}>
                ◈ BRAND BEACON TARGET ACTIVE
              </div>
              <div style={{ fontSize: '0.72rem', color: '#64748b' }}>
                Hover over dynamic anchors or competitor noise vectors to parse real-time embedding coordinates.
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', borderLeft: '1px solid rgba(255,255,255,0.06)', paddingLeft: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', fontFamily: 'var(--font-mono)' }}>
                <span>ALIGNMENT INDEX:</span>
                <span style={{ color: '#00f5ff', fontWeight: 'bold' }}>{alignmentPercent}%</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', fontFamily: 'var(--font-mono)' }}>
                <span>VECTOR DRIFT:</span>
                <span style={{ color: healthColor, fontWeight: 'bold' }}>{healthStatus}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* SVG Vector Canvas */}
      <div style={{ position: 'relative', width: '100%', overflow: 'hidden' }}>
        <svg 
          viewBox="0 0 600 350" 
          style={{ width: '100%', height: 'auto', display: 'block', pointerEvents: 'auto' }}
        >
          <defs>
            {/* Ambient Radial Grids */}
            <radialGradient id="radar-mesh" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(0, 245, 255, 0.08)" />
              <stop offset="60%" stopColor="rgba(0, 245, 255, 0.02)" />
              <stop offset="100%" stopColor="rgba(0, 0, 0, 0)" />
            </radialGradient>

            {/* Area Web Gradient */}
            <radialGradient id="poly-grad" cx="50%" cy="50%" r="60%">
              <stop offset="0%" stopColor="rgba(0, 245, 255, 0.28)" />
              <stop offset="70%" stopColor="rgba(16, 185, 129, 0.12)" />
              <stop offset="100%" stopColor="rgba(244, 63, 94, 0.02)" />
            </radialGradient>

            {/* Sweep Sector Linear Gradient */}
            <linearGradient id="sweep-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="rgba(0, 245, 255, 0.25)" />
              <stop offset="100%" stopColor="rgba(0, 245, 255, 0)" />
            </linearGradient>

            {/* Glowing filter effects */}
            <filter id="radar-glow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            
            <filter id="line-glow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="3.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Radar Ambient Radial Background */}
          <circle cx={cx} cy={cy} r={maxR + 25} fill="url(#radar-mesh)" />

          {/* Concentric Radar Grid Rings (Attr Distance Limits) */}
          <circle cx={cx} cy={cy} r={maxR} fill="none" stroke="rgba(0, 245, 255, 0.08)" strokeWidth="1" />
          <text x={cx + 4} y={cy - maxR + 9} fill="#475569" fontSize="6.5" fontFamily="var(--font-mono)">100% DRIFT</text>

          <circle cx={cx} cy={cy} r={(maxR + minR) / 2} fill="none" stroke="rgba(0, 245, 255, 0.04)" strokeWidth="1" strokeDasharray="3,6" />
          <text x={cx + 4} y={cy - (maxR + minR)/2 + 9} fill="#475569" fontSize="6.5" fontFamily="var(--font-mono)">50% SIMILARITY</text>

          <circle cx={cx} cy={cy} r={minR} fill="none" stroke="rgba(0, 245, 255, 0.12)" strokeWidth="1.2" />
          <text x={cx + 4} y={cy - minR + 9} fill="#475569" fontSize="6.5" fontFamily="var(--font-mono)">0% DRIFT (TIGHT)</text>

          {/* Axis Ticks & Crosshair guidelines */}
          <line x1={cx - maxR - 15} y1={cy} x2={cx + maxR + 15} y2={cy} stroke="rgba(255, 255, 255, 0.03)" strokeWidth="1" />
          <line x1={cx} y1={cy - maxR - 15} x2={cx} y2={cy + maxR + 15} stroke="rgba(255, 255, 255, 0.03)" strokeWidth="1" />

          {/* Axis Spokes (Connecting fixed annotation anchors to center) */}
          <line x1={cx} y1={cy} x2={pIntentLabel.x} y2={pIntentLabel.y} stroke="rgba(0, 245, 255, 0.06)" strokeWidth="1" strokeDasharray="2,4" />
          <line x1={cx} y1={cy} x2={pAttributeLabel.x} y2={pAttributeLabel.y} stroke="rgba(0, 245, 255, 0.06)" strokeWidth="1" strokeDasharray="2,4" />
          <line x1={cx} y1={cy} x2={pReadabilityLabel.x} y2={pReadabilityLabel.y} stroke="rgba(0, 245, 255, 0.06)" strokeWidth="1" strokeDasharray="2,4" />
          <line x1={cx} y1={cy} x2={pQALabel.x} y2={pQALabel.y} stroke="rgba(0, 245, 255, 0.06)" strokeWidth="1" strokeDasharray="2,4" />

          {/* Rotating Radar Sweep Cone Wedge */}
          <path d={sweepWedge} fill="url(#sweep-grad)" opacity="0.6" style={{ pointerEvents: 'none' }} />

          {/* Glowing Radar Sweep Line */}
          <line 
            x1={cx} 
            y1={cy} 
            x2={cx + maxR * Math.cos((rotation * Math.PI) / 180)} 
            y2={cy + maxR * Math.sin((rotation * Math.PI) / 180)} 
            stroke="#00f5ff" 
            strokeWidth="1.8"
            opacity="0.85"
            filter="url(#radar-glow)"
            style={{ pointerEvents: 'none' }}
          />

          {/* Dynamic Vector Alignment Area Polygon (Fills the Attributed Web) */}
          <polygon 
            points={polyPoints} 
            fill="url(#poly-grad)" 
            stroke="rgba(0, 245, 255, 0.25)" 
            strokeWidth="1" 
            opacity="0.75"
            style={{ ...springStyle, pointerEvents: 'none' }} 
          />

          {/* Transition-safe Outer Border Lines for Polygon (Ensures smooth browser rendering) */}
          <line x1={pIntent.x} y1={pIntent.y} x2={pAttribute.x} y2={pAttribute.y} stroke="rgba(0, 245, 255, 0.4)" strokeWidth="1.5" filter="url(#line-glow)" style={springStyle} />
          <line x1={pAttribute.x} y1={pAttribute.y} x2={pReadability.x} y2={pReadability.y} stroke="rgba(0, 245, 255, 0.4)" strokeWidth="1.5" filter="url(#line-glow)" style={springStyle} />
          <line x1={pReadability.x} y1={pReadability.y} x2={pQA.x} y2={pQA.y} stroke="rgba(0, 245, 255, 0.4)" strokeWidth="1.5" filter="url(#line-glow)" style={springStyle} />
          <line x1={pQA.x} y1={pQA.y} x2={pIntent.x} y2={pIntent.y} stroke="rgba(0, 245, 255, 0.4)" strokeWidth="1.5" filter="url(#line-glow)" style={springStyle} />

          {/* Dynamic Vector Alignment Connection Lines (Center -> Dynamic Nodes) */}
          <line x1={cx} y1={cy} x2={pIntent.x} y2={pIntent.y} stroke={colorIntent} strokeWidth={2 + (sIntent / 25) * 2} opacity={0.65} filter="url(#line-glow)" style={springStyle} />
          <line x1={cx} y1={cy} x2={pAttribute.x} y2={pAttribute.y} stroke={colorAttribute} strokeWidth={2 + (sAttribute / 25) * 2} opacity={0.65} filter="url(#line-glow)" style={springStyle} />
          <line x1={cx} y1={cy} x2={pReadability.x} y2={pReadability.y} stroke={colorReadability} strokeWidth={2 + (sReadability / 25) * 2} opacity={0.65} filter="url(#line-glow)" style={springStyle} />
          <line x1={cx} y1={cy} x2={pQA.x} y2={pQA.y} stroke={colorQA} strokeWidth={2 + (sQA / 25) * 2} opacity={0.65} filter="url(#line-glow)" style={springStyle} />

          {/* Dynamic Leader Lines (Dynamic Nodes -> Fixed Outer Labels) */}
          <line x1={pIntent.x} y1={pIntent.y} x2={pIntentLabel.x} y2={pIntentLabel.y} stroke="rgba(255,255,255,0.15)" strokeWidth="0.8" strokeDasharray="3,3" style={springStyle} />
          <line x1={pAttribute.x} y1={pAttribute.y} x2={pAttributeLabel.x} y2={pAttributeLabel.y} stroke="rgba(255,255,255,0.15)" strokeWidth="0.8" strokeDasharray="3,3" style={springStyle} />
          <line x1={pReadability.x} y1={pReadability.y} x2={pReadabilityLabel.x} y2={pReadabilityLabel.y} stroke="rgba(255,255,255,0.15)" strokeWidth="0.8" strokeDasharray="3,3" style={springStyle} />
          <line x1={pQA.x} y1={pQA.y} x2={pQALabel.x} y2={pQALabel.y} stroke="rgba(255,255,255,0.15)" strokeWidth="0.8" strokeDasharray="3,3" style={springStyle} />

          {/* Competitor Nodes (Threat Vector Noise) */}
          {showCompetitors && (
            <g style={{ transition: 'opacity 0.4s ease' }}>
              {/* Orbits Tracks */}
              <circle cx={cx} cy={cy} r="110" fill="none" stroke="rgba(244, 63, 94, 0.05)" strokeWidth="0.8" strokeDasharray="2,5" />
              <circle cx={cx} cy={cy} r="85" fill="none" stroke="rgba(168, 85, 247, 0.05)" strokeWidth="0.8" strokeDasharray="2,5" />

              {/* Competitor ASIN A (Coral Threat) */}
              <g 
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setActiveNode({
                  title: 'Competitor ASIN A',
                  score: 'DRIFT: 110px',
                  color: '#f43f5e',
                  desc: 'Competitor listing has significant semantic drift from core customer search queries. This represents an extremely vulnerable listing open to capture.'
                })}
                onMouseLeave={() => setActiveNode(null)}
              >
                <circle cx={comp1.x} cy={comp1.y} r="8" fill="rgba(244, 63, 94, 0.1)" stroke="#f43f5e" strokeWidth="1.5" />
                <circle cx={comp1.x} cy={comp1.y} r="3" fill="#f43f5e" filter="url(#radar-glow)" />
                <text x={comp1.x + 8} y={comp1.y + 3} fill="#475569" fontSize="7.5" fontWeight="bold" fontFamily="var(--font-mono)">COMP_ASIN_A</text>
              </g>
              
              {/* Competitor ASIN B (Purple Threat) */}
              <g 
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setActiveNode({
                  title: 'Competitor ASIN B',
                  score: 'DRIFT: 85px',
                  color: '#a855f7',
                  desc: 'Competitor listing has moderate semantic proximity. Currently captures baseline relevance but lacks precise measurement anchors.'
                })}
                onMouseLeave={() => setActiveNode(null)}
              >
                <circle cx={comp2.x} cy={comp2.y} r="8" fill="rgba(168, 85, 247, 0.1)" stroke="#a855f7" strokeWidth="1.5" />
                <circle cx={comp2.x} cy={comp2.y} r="3" fill="#a855f7" filter="url(#radar-glow)" />
                <text x={comp2.x + 8} y={comp2.y + 3} fill="#475569" fontSize="7.5" fontWeight="bold" fontFamily="var(--font-mono)">COMP_ASIN_B</text>
              </g>
            </g>
          )}

          {/* Dynamic Cluster Hub Interactive Nodes */}

          {/* 1. Intent Alignment Hub */}
          <g 
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setActiveNode({
              title: 'Intent Alignment Cluster',
              score: `${sIntent} / 25`,
              color: colorIntent,
              desc: 'Reflects how cleanly your product title and core search terms map directly to real Amazon user semantic search queries in the embedding vector space.'
            })}
            onMouseLeave={() => setActiveNode(null)}
          >
            <circle cx={pIntent.x} cy={pIntent.y} r="12" fill="#04060c" stroke={colorIntent} strokeWidth="3" filter="url(#radar-glow)" style={springStyle} />
            <circle cx={pIntent.x} cy={pIntent.y} r="4.5" fill={colorIntent} style={springStyle} />
          </g>

          {/* 2. Attribute Density Hub */}
          <g 
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setActiveNode({
              title: 'Attribute Density Cluster',
              score: `${sAttribute} / 25`,
              color: colorAttribute,
              desc: 'Audits physical, chemical, or technical specification markers inside product bullet text. Rufus relies heavily on absolute measurements.'
            })}
            onMouseLeave={() => setActiveNode(null)}
          >
            <circle cx={pAttribute.x} cy={pAttribute.y} r="12" fill="#04060c" stroke={colorAttribute} strokeWidth="3" filter="url(#radar-glow)" style={springStyle} />
            <circle cx={pAttribute.x} cy={pAttribute.y} r="4.5" fill={colorAttribute} style={springStyle} />
          </g>

          {/* 3. Conversational Readability Hub */}
          <g 
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setActiveNode({
              title: 'Conversational Readability Cluster',
              score: `${sReadability} / 25`,
              color: colorReadability,
              desc: 'Measures structural dialogue accessibility. Reviews A+ content layout blocks and ensures descriptions answer natural conversational shopper flows.'
            })}
            onMouseLeave={() => setActiveNode(null)}
          >
            <circle cx={pReadability.x} cy={pReadability.y} r="12" fill="#04060c" stroke={colorReadability} strokeWidth="3" filter="url(#radar-glow)" style={springStyle} />
            <circle cx={pReadability.x} cy={pReadability.y} r="4.5" fill={colorReadability} style={springStyle} />
          </g>

          {/* 4. Q&A Coverage Hub */}
          <g 
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setActiveNode({
              title: 'Q&A Coverage Cluster',
              score: `${sQA} / 25`,
              color: colorQA,
              desc: 'Audits standard listing Q&A pairs. Pre-publishing seeds addressing friction points makes it easy for Rufus to cite your brand directly.'
            })}
            onMouseLeave={() => setActiveNode(null)}
          >
            <circle cx={pQA.x} cy={pQA.y} r="12" fill="#04060c" stroke={colorQA} strokeWidth="3" filter="url(#radar-glow)" style={springStyle} />
            <circle cx={pQA.x} cy={pQA.y} r="4.5" fill={colorQA} style={springStyle} />
          </g>

          {/* --- Central Client Product Beacon Node --- */}
          <g 
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setActiveNode({
              title: brand,
              score: 'ANCHOR ORIGIN',
              color: '#00f5ff',
              desc: 'Your listing starting coordinate in the Amazon RAG search vector space. S-Curve projections show optimization impact relative to this origin.'
            })}
            onMouseLeave={() => setActiveNode(null)}
          >
            {/* Pulsing Outer Rings */}
            <circle cx={cx} cy={cy} r="20" fill="none" stroke="#00f5ff" strokeWidth="1" opacity="0.4">
              <animate attributeName="r" values="14;28;14" dur="3s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.6;0;0.6" dur="3s" repeatCount="indefinite" />
            </circle>
            <circle cx={cx} cy={cy} r="14" fill="#04060c" stroke="#00f5ff" strokeWidth="3.5" filter="url(#radar-glow)" />
            <circle cx={cx} cy={cy} r="5" fill="#00f5ff" />
            
            {/* Sleek Central Text Label */}
            <rect x={cx - 50} y={cy + 24} width="100" height="15" rx="3" fill="rgba(8, 12, 22, 0.85)" stroke="rgba(0, 245, 255, 0.15)" strokeWidth="0.8" />
            <text x={cx} y={cy + 34} fill="#00f5ff" fontSize="8" fontWeight="bold" fontFamily="var(--font-mono)" letterSpacing="0.05em" textAnchor="middle">
              {brand.substring(0, 15).toUpperCase()}
            </text>
          </g>

          {/* --- Fixed Corner Annotations Text Labels --- */}
          
          {/* Top-Left: Intent */}
          <g>
            <text x={pIntentLabel.x - 8} y={pIntentLabel.y - 4} textAnchor="end" fontSize="9" fontFamily="var(--font-display)" letterSpacing="0.02em">
              <tspan fill="#e2e8f0" fontWeight="700">INTENT ALIGNMENT </tspan>
              <tspan fill={colorIntent} fontFamily="var(--font-mono)" fontWeight="bold">[{sIntent}/25]</tspan>
            </text>
            <circle cx={pIntentLabel.x} cy={pIntentLabel.y} r="3" fill={colorIntent} stroke="#04060c" strokeWidth="1" />
          </g>

          {/* Top-Right: Attribute */}
          <g>
            <text x={pAttributeLabel.x + 8} y={pAttributeLabel.y - 4} textAnchor="start" fontSize="9" fontFamily="var(--font-display)" letterSpacing="0.02em">
              <tspan fill="#e2e8f0" fontWeight="700">ATTRIBUTE DENSITY </tspan>
              <tspan fill={colorAttribute} fontFamily="var(--font-mono)" fontWeight="bold">[{sAttribute}/25]</tspan>
            </text>
            <circle cx={pAttributeLabel.x} cy={pAttributeLabel.y} r="3" fill={colorAttribute} stroke="#04060c" strokeWidth="1" />
          </g>

          {/* Bottom-Right: Readability */}
          <g>
            <text x={pReadabilityLabel.x + 8} y={pReadabilityLabel.y + 11} textAnchor="start" fontSize="9" fontFamily="var(--font-display)" letterSpacing="0.02em">
              <tspan fill="#e2e8f0" fontWeight="700">READABILITY </tspan>
              <tspan fill={colorReadability} fontFamily="var(--font-mono)" fontWeight="bold">[{sReadability}/25]</tspan>
            </text>
            <circle cx={pReadabilityLabel.x} cy={pReadabilityLabel.y} r="3" fill={colorReadability} stroke="#04060c" strokeWidth="1" />
          </g>

          {/* Bottom-Left: QA */}
          <g>
            <text x={pQALabel.x - 8} y={pQALabel.y + 11} textAnchor="end" fontSize="9" fontFamily="var(--font-display)" letterSpacing="0.02em">
              <tspan fill="#e2e8f0" fontWeight="700">Q&A COVERAGE </tspan>
              <tspan fill={colorQA} fontFamily="var(--font-mono)" fontWeight="bold">[{sQA}/25]</tspan>
            </text>
            <circle cx={pQALabel.x} cy={pQALabel.y} r="3" fill={colorQA} stroke="#04060c" strokeWidth="1" />
          </g>

        </svg>
      </div>
      
      {/* Cyber Radar Controls and Legend */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        borderTop: '1px solid rgba(0, 245, 255, 0.08)', 
        paddingTop: '12px', 
        marginTop: '12px', 
        fontSize: '0.68rem', 
        fontFamily: 'var(--font-mono)',
        color: '#64748b' 
      }}>
        
        {/* View Toggle Switches */}
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button 
            onClick={triggerScan}
            disabled={isScanning}
            style={{
              background: isScanning ? 'rgba(0, 245, 255, 0.15)' : 'rgba(0, 245, 255, 0.04)',
              border: isScanning ? '1px solid #00f5ff' : '1px solid rgba(0, 245, 255, 0.15)',
              borderRadius: '6px',
              color: isScanning ? '#00f5ff' : '#94a3b8',
              padding: '4px 10px',
              cursor: 'pointer',
              fontSize: '0.62rem',
              fontFamily: 'var(--font-display)',
              letterSpacing: '0.05em',
              transition: 'all 0.25s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              textTransform: 'uppercase'
            }}
          >
            <span style={{ 
              display: 'inline-block', 
              width: '4px', 
              height: '4px', 
              borderRadius: '50%', 
              backgroundColor: isScanning ? '#00f5ff' : 'transparent',
              border: '1px solid #00f5ff',
              boxShadow: isScanning ? '0 0 6px #00f5ff' : 'none'
            }} />
            {isScanning ? 'SCANNING...' : 'SCAN VECTOR SPACE'}
          </button>

          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', userSelect: 'none' }}>
            <input 
              type="checkbox" 
              checked={showCompetitors}
              onChange={() => setShowCompetitors(!showCompetitors)}
              style={{
                accentColor: '#00f5ff',
                cursor: 'pointer',
                width: '12px',
                height: '12px'
              }}
            />
            <span>SHOW NOISE ORBITS</span>
          </label>
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', gap: '10px' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
            <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#10b981' }} />
            ALIGNED
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
            <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#f43f5e' }} />
            DRIFT
          </span>
        </div>
      </div>
    </div>
  );
}
