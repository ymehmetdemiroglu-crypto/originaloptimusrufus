/**
 * Optimus Rufus — Rufus Visibility Calculator Engine
 * 
 * Mirrors the 4-axis scoring model from rufus_scorer.py:
 *   - Intent Alignment (0-25)
 *   - Attribute Density (0-25) 
 *   - Conversational Readability (0-25)
 *   - Q&A Coverage (0-25)
 * 
 * Total: 0-100 Rufus Visibility Score
 */

// ---- Category averages (from real data — Rufus scores of prospected brands) ----
const CATEGORY_AVERAGES = {
  supplements: 32,
  beauty: 38,
  skincare: 38,
  electronics: 45,
  pet: 42,
  sports: 40,
  fitness: 40,
  kitchen: 48,
  home: 48,
  'essential oils': 35,
  'golf apparel': 40,
  nutrition: 34,
  other: 40,
};

/**
 * Determine the citation probability band using a smooth continuous Sigmoid S-curve:
 * P(x) = 1 / (1 + e^(-k * (x - midpoint)))
 * where midpoint = 50, k = 0.08.
 * High probability: >= 75%
 * Medium probability: >= 35%
 * Low probability: < 35%
 */
export function getCitationProbability(score) {
  const p = 1 / (1 + Math.exp(-0.08 * (score - 50)));
  if (p >= 0.75) return 'high';
  if (p >= 0.35) return 'medium';
  return 'low';
}

/**
 * Compute precise client-side visibility score based on active metrics.
 */
function computeClientSideScore(data) {
  const titleLen = (data.post_title || '').length || 70;
  const bulletCount = data.bullet_count || 0;
  const qaCount = data.qa_count || 0;
  const hasAPlus = !!data.has_a_plus;

  // Axis 1: Intent Alignment (0-25)
  let intentAlignment = 5;
  if (titleLen >= 120) intentAlignment = 25;
  else if (titleLen >= 80) intentAlignment = 15;

  // Axis 2: Attribute Density (0-25)
  let attributeDensity = 5;
  if (bulletCount >= 5) attributeDensity = 25;
  else if (bulletCount >= 3) attributeDensity = 15;

  // Axis 3: Conversational Readability (0-25)
  let conversationalReadability = hasAPlus ? 25 : 12;

  // Axis 4: Q&A Coverage (0-25)
  let qaCoverage = 0;
  if (qaCount >= 15) qaCoverage = 25;
  else if (qaCount >= 5) qaCoverage = 15;
  else if (qaCount >= 1) qaCoverage = 8;

  const total = intentAlignment + attributeDensity + conversationalReadability + qaCoverage;

  return {
    displayScore: Math.min(100, Math.max(0, total)),
    displayScores: {
      intentAlignment,
      attributeDensity,
      conversationalReadability,
      qaCoverage,
    }
  };
}

/**
 * Run the Rufus Visibility Score display engine.
 *
 * @param {Object} inputs — minimal inputs (just category for fallback)
 * @param {Object|null} actualData — Actual Rufus data from Supabase (if ASIN found)
 * @param {Object|null} backendAnalysis — Backend COSMO analysis (if available)
 *
 * @returns {Object} Full calculation results for display
 */
export function calculateRufusScore(inputs, actualData = null, backendAnalysis = null) {
  const hasActual = actualData && actualData.rufus_score != null;
  
  let displayScore = 0;
  let displayScores = {
    intentAlignment: 0,
    attributeDensity: 0,
    conversationalReadability: 0,
    qaCoverage: 0,
  };

  if (hasActual) {
    displayScore = actualData.rufus_score;
    displayScores = {
      intentAlignment: actualData.intent_alignment_score || 0,
      attributeDensity: actualData.attribute_density_score || 0,
      conversationalReadability: actualData.conversational_readability_score || 0,
      qaCoverage: actualData.qa_coverage_score || 0,
    };
  } else if (actualData) {
    // Dynamically calculate from crawled metrics in real time (instant score)
    const computed = computeClientSideScore(actualData);
    displayScore = computed.displayScore;
    displayScores = computed.displayScores;
  } else {
    // Generate baseline fallback metrics for brand new ASINs
    const fallbackData = {
      post_title: 'Sample Product Listing Title',
      bullet_count: 3,
      qa_count: 0,
      has_a_plus: false,
    };
    const computed = computeClientSideScore(fallbackData);
    displayScore = computed.displayScore;
    displayScores = computed.displayScores;
  }

  const categoryAvg = CATEGORY_AVERAGES[inputs.category] || 40;
  const citationProbability = getCitationProbability(displayScore);

  // Weakest axes (ordered worst first)
  const axisLabels = {
    intentAlignment: 'Intent Alignment',
    attributeDensity: 'Attribute Density',
    conversationalReadability: 'Conversational Readability',
    qaCoverage: 'Q&A Coverage',
  };

  const weakestAxes = Object.entries(displayScores)
    .map(([key, score]) => ({ key, label: axisLabels[key], score: score || 0 }))
    .sort((a, b) => a.score - b.score);

  // Actual listing metadata or standard baseline
  const dataForMeta = actualData || {
    post_title: 'Sample Product Listing Title',
    bullet_count: 3,
    image_count: 3,
    has_a_plus: false,
    qa_count: 0,
    listing_rating: 4.2,
    listing_review_count: 120,
    rufus_summary: 'This listing has not been analyzed yet. It has a projected low visibility score due to short title length, lack of Q&A blocks, and missing A+ content.',
    rufus_top_weaknesses: 'Short Title, Few Bullets, Zero Q&A'
  };

  const listingMeta = {
    title: dataForMeta.post_title,
    bulletCount: dataForMeta.bullet_count,
    imageCount: dataForMeta.image_count || 3,
    hasAPlus: dataForMeta.has_a_plus,
    qaCount: dataForMeta.qa_count,
    rating: dataForMeta.listing_rating || 4.2,
    reviewCount: dataForMeta.listing_review_count || 120,
    citationProbability: dataForMeta.rufus_citation_probability || citationProbability,
    summary: dataForMeta.rufus_summary || 'Listing not fully scrape-audited yet. Running projected baseline analysis.',
    topWeaknesses: dataForMeta.rufus_top_weaknesses || 'Short Title, Missing Q&A',
  };

  // Process backend COSMO analysis into display-friendly clusters
  let backendClusters = null;
  if (backendAnalysis && backendAnalysis.relations) {
    const clusterMap = {};
    backendAnalysis.relations.forEach(r => {
      const c = r.cluster || 'Unknown';
      if (!clusterMap[c]) clusterMap[c] = { scores: [], relations: [] };
      clusterMap[c].scores.push(r.confidence_score || 0);
      clusterMap[c].relations.push({
        relation: r.relation,
        confidence: r.confidence_score || 0,
        grade: r.coverage_grade || '?',
        signals: (r.detected_signals || []).slice(0, 2),
      });
    });
    backendClusters = Object.entries(clusterMap).map(([name, data]) => {
      const avg = data.scores.reduce((a, b) => a + b, 0) / data.scores.length;
      return {
        name,
        avgConfidence: Math.round(avg * 100),
        grade: avg >= 0.8 ? 'A' : avg >= 0.65 ? 'B' : avg >= 0.5 ? 'C' : avg >= 0.35 ? 'D' : 'F',
        relations: data.relations.sort((a, b) => a.confidence - b.confidence),
      };
    }).sort((a, b) => a.avgConfidence - b.avgConfidence);
  }

  return {
    displayScore,
    displayScores,
    categoryAvg,
    citationProbability,
    weakestAxes,
    listingMeta,
    backendAnalysis: backendClusters ? {
      overallScore: backendAnalysis.overall_score || 0,
      keywordSafety: backendAnalysis.keyword_safety || 'N/A',
      clusters: backendClusters,
    } : null,
  };
}

/**
 * Optional: fetch backend COSMO semantic analysis for an ASIN.
 * In production this should call a Netlify function or Supabase edge function
 * that proxies to the Rufus/COSMO backend (avoids CORS + exposes backend securely).
 *
 * Example Netlify function at /.netlify/functions/backend-proxy:
 *   export const handler = async (event) => {
 *     const { asin } = JSON.parse(event.body);
 *     const res = await fetch(`${BACKEND_URL}/api/analyze`, { method: 'POST', body: JSON.stringify({ asin }) });
 *     return { statusCode: 200, body: await res.text() };
 *   };
 */
export async function fetchBackendAnalysis(asin) {
  // Try direct backend call first (works in local dev when backend is on localhost:8000)
  const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
  try {
    const res = await fetch(`${BACKEND_URL}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asin }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    // Backend unreachable or CORS blocked — silently return null
    return null;
  }
}

/**
 * Calculate dynamic ROI revenue growth projections based on listing scores and self-assessments.
 *
 * @param {number} monthlyRevenue - Current monthly revenue of the listing
 * @param {string} category - Category slug
 * @param {number} imageScore - Self-reported Image Quality (1-5)
 * @param {number} copyScore - Self-reported Copy Quality (1-5)
 * @param {number} ppcScore - Self-reported PPC Structure (1-5)
 * @param {number} rating - Average listing rating (1.0 - 5.0)
 * @param {number} reviewCount - Number of listing reviews
 *
 * @returns {Object} Complete revenue impact projections structure
 */
export function calculateRevenueImpact(monthlyRevenue, category, imageScore, copyScore, ppcScore, rating = 4.2, reviewCount = 120) {
  const parsedRevenue = parseFloat(monthlyRevenue) || 0;
  if (parsedRevenue <= 0) return null;

  // 1. Per-Area Lift Models
  const imageLift = ((5 - imageScore) / 4) * 0.17;
  const copyLift = ((5 - copyScore) / 4) * 0.12;
  const ppcLift = ((5 - ppcScore) / 4) * 0.22;

  // 2. Count areas being improved
  let areasImproved = 0;
  if (imageScore < 5) areasImproved++;
  if (copyScore < 5) areasImproved++;
  if (ppcScore < 5) areasImproved++;

  // 3. Dynamic Lift Overlap Dampening
  let baseLift = imageLift + copyLift + ppcLift;
  let dampening = 1.0;
  if (areasImproved > 1) {
    dampening = 1.0 - 0.05 * (areasImproved - 1);
  }
  dampening = Math.max(0.70, dampening);
  let combinedLift = baseLift * dampening;

  // 4. Category Modifier
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
  let adjustedLift = combinedLift * modifier;

  // 5. Review & Rating Double Bottleneck
  let countMultiplier = 1.0;
  if (reviewCount < 10) countMultiplier = 0.70;
  else if (reviewCount < 50) countMultiplier = 0.85;

  const ratingMultiplier = Math.pow(Math.max(1.0, Math.min(5.0, rating)) / 5.0, 0.5);
  const reviewMultiplier = countMultiplier * ratingMultiplier;
  
  const finalLift = adjustedLift * reviewMultiplier;

  // 6. Outcome Bands & S-Curve Time-Decay Projections
  // S-Curve realization multipliers: Day 30: 0.20, Day 60: 0.65, Day 90: 1.00
  const timeDecay = {
    day30: 0.20,
    day60: 0.65,
    day90: 1.00,
  };

  const bands = {
    conservative: 0.6,
    realistic: 1.0,
    aggressive: 1.3,
  };

  const projections = {
    day30: {},
    day60: {},
    day90: {},
  };

  for (const [day, decayMult] of Object.entries(timeDecay)) {
    projections[day] = {
      conservative: Math.round(parsedRevenue * finalLift * bands.conservative * decayMult),
      realistic: Math.round(parsedRevenue * finalLift * bands.realistic * decayMult),
      aggressive: Math.round(parsedRevenue * finalLift * bands.aggressive * decayMult),
    };
  }

  const annualGap = Math.round(parsedRevenue * finalLift * 12);

  return {
    finalLift,
    annualGap,
    projections,
  };
}

export { CATEGORY_AVERAGES };
