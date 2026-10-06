import type { AdClaimAnalysis, AdPressureSignal } from "./types.ts";

/**
 * Analyzes advertisement copy, titles, descriptions, or post captions
 * to extract structured promotional claims and advertising pressure indicators.
 *
 * NOTE: Claim extraction does NOT decide whether a claim is fraudulent;
 * it identifies claims and high-pressure patterns that require cross-source verification.
 */
export function analyzeAdClaims(
  text: string,
  source: "meta_ad" | "instagram_caption" | "instagram" = "meta_ad",
): AdClaimAnalysis {
  const clean = (text || "").trim();
  if (!clean) {
    return {
      clickbait_score: 0,
      clickbait_level: "LOW",
      clickbait_flags: [],
      claims_detected: [],
      ad_pressure_signals: [],
      price_claims: [],
      authenticity_claims: [],
      urgency_claims: [],
      scarcity_claims: [],
      authority_claims: [],
      performance_claims: [],
      social_proof_claims: [],
      price_anchoring_claims: [],
      pressure_signals: [],
    };
  }

  const price_claims: string[] = [];
  const authenticity_claims: string[] = [];
  const urgency_claims: string[] = [];
  const scarcity_claims: string[] = [];
  const authority_claims: string[] = [];
  const performance_claims: string[] = [];
  const social_proof_claims: string[] = [];
  const price_anchoring_claims: string[] = [];
  const pressure_signals: AdPressureSignal[] = [];

  // 1. Price Claims & Discounts
  const discountRegex = /\b(\d{1,2}%\s*(?:off|discount|sale))\b/gi;
  let dMatch: RegExpExecArray | null;
  while ((dMatch = discountRegex.exec(clean)) !== null) {
    const matched = dMatch[1];
    if (!price_claims.includes(matched)) price_claims.push(matched);

    const percent = parseInt(matched, 10);
    if (percent >= 60) {
      pressure_signals.push({
        type: "extreme_discount",
        text: matched,
        source,
        meaning: `Advertisement advertises an extreme discount (${matched}) which is commonly used to incentivize unverified impulse purchases.`,
      });
    }
  }

  const multiBuyRegex = /\b(buy\s*\d+\s*get\s*\d+(?:\s*free)?|bogo|buy\s*1\s*get\s*[2345])\b/gi;
  let mbMatch: RegExpExecArray | null;
  while ((mbMatch = multiBuyRegex.exec(clean)) !== null) {
    const matched = mbMatch[1];
    if (!price_claims.includes(matched)) price_claims.push(matched);
    pressure_signals.push({
      type: "extreme_discount",
      text: matched,
      source,
      meaning: `Advertisement uses high-volume bundle incentives (${matched}).`,
    });
  }

  const currencyPriceRegex = /(?:₹|rs\.?|inr|\$)\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+)/gi;
  let pMatch: RegExpExecArray | null;
  while ((pMatch = currencyPriceRegex.exec(clean)) !== null) {
    const matched = pMatch[0].trim();
    if (!price_claims.includes(matched)) price_claims.push(matched);
  }

  // 2. Price Anchoring (e.g. ₹9999 -> ₹999 or MRP 10000 at 499)
  const anchoringRegex = /(?:mrp|was|originally|worth)\s*(?:₹|rs\.?|\$)?\s*(\d+[\d,]*)\s*(?:now|only|at|for|→|->)\s*(?:₹|rs\.?|\$)?\s*(\d+[\d,]*)/gi;
  let aMatch: RegExpExecArray | null;
  while ((aMatch = anchoringRegex.exec(clean)) !== null) {
    const matched = aMatch[0].trim();
    price_anchoring_claims.push(matched);
    pressure_signals.push({
      type: "price_anchoring",
      text: matched,
      source,
      meaning: `Advertisement anchors perceived value against a steep original price (${matched}).`,
    });
  }

  // 3. Authenticity Claims
  const authRegex = /\b(100%\s*(?:original|genuine|authentic|real)|authentic|genuine|official\s*(?:store|product|dealer)|authorized\s*(?:seller|reseller|dealer))\b/gi;
  let authMatch: RegExpExecArray | null;
  while ((authMatch = authRegex.exec(clean)) !== null) {
    const matched = authMatch[1];
    if (!authenticity_claims.includes(matched)) authenticity_claims.push(matched);
    pressure_signals.push({
      type: "authenticity_claim",
      text: matched,
      source,
      meaning: `Advertisement makes an explicit authenticity claim ("${matched}") that requires independent verification.`,
    });
  }

  // 4. Urgency Claims
  const urgencyRegex = /\b(today\s*only|last\s*chance|ending\s*(?:tonight|soon|today)|limited\s*time(?:\s*offer)?|hurry\s*up|valid\s*till\s*(?:midnight|today)|flash\s*sale|few\s*hours\s*left)\b/gi;
  let uMatch: RegExpExecArray | null;
  while ((uMatch = urgencyRegex.exec(clean)) !== null) {
    const matched = uMatch[1];
    if (!urgency_claims.includes(matched)) urgency_claims.push(matched);
    pressure_signals.push({
      type: "urgency",
      text: matched,
      source,
      meaning: `Advertisement uses urgency language ("${matched}") to create purchase pressure.`,
    });
  }

  // 5. Scarcity Claims
  const scarcityRegex = /\b(only\s*\d+\s*(?:left|remaining|pieces?|stock)|few\s*remaining|limited\s*stock|almost\s*sold\s*out|last\s*few\s*pieces?)\b/gi;
  let sMatch: RegExpExecArray | null;
  while ((sMatch = scarcityRegex.exec(clean)) !== null) {
    const matched = sMatch[1];
    if (!scarcity_claims.includes(matched)) scarcity_claims.push(matched);
    pressure_signals.push({
      type: "scarcity",
      text: matched,
      source,
      meaning: `Advertisement uses artificial scarcity language ("${matched}").`,
    });
  }

  // 6. Authority & Certification Claims
  const certRegex = /\b(fda\s*approved|iso\s*certified|government\s*approved|clinically\s*proven|doctor\s*recommended|gmp\s*certified|ce\s*certified|ayush\s*certified)\b/gi;
  let cMatch: RegExpExecArray | null;
  while ((cMatch = certRegex.exec(clean)) !== null) {
    const matched = cMatch[1];
    if (!authority_claims.includes(matched)) authority_claims.push(matched);
    pressure_signals.push({
      type: "authority_certification",
      text: matched,
      source,
      meaning: `Advertisement claims formal regulatory authorization or clinical backing ("${matched}").`,
    });
  }

  // 7. Performance & Guarantee Claims
  const perfRegex = /\b(guaranteed\s*results|100%\s*effective|permanent\s*results|instant\s*results|results\s*in\s*\d+\s*(?:days?|minutes?|hours?)|money\s*back\s*guarantee)\b/gi;
  let pfmMatch: RegExpExecArray | null;
  while ((pfmMatch = perfRegex.exec(clean)) !== null) {
    const matched = pfmMatch[1];
    if (!performance_claims.includes(matched)) performance_claims.push(matched);
    pressure_signals.push({
      type: "performance_guarantee",
      text: matched,
      source,
      meaning: `Advertisement makes absolute outcome guarantees ("${matched}").`,
    });
  }

  // 8. Social Proof Claims
  const socialRegex = /\b(\d+[\d,]*\+?\s*(?:happy\s*)?customers?|5-?star\s*(?:rated|rating)|everyone\s*is\s*buying|#1\s*(?:best\s*)?selling|trusted\s*by\s*(?:millions|thousands))\b/gi;
  let socMatch: RegExpExecArray | null;
  while ((socMatch = socialRegex.exec(clean)) !== null) {
    const matched = socMatch[1];
    if (!social_proof_claims.includes(matched)) social_proof_claims.push(matched);
    pressure_signals.push({
      type: "social_proof",
      text: matched,
      source,
      meaning: `Advertisement leverages unverified social proof metrics ("${matched}").`,
    });
  }

  // 9. Clickbait Hooks & Sensationalist Language
  const clickbaitHookRegex = /\b(you won't believe|secret trick|doctors? (?:hate|don't want you to know)|shocking results?|must watch|don't buy before|stop scrolling|viral (?:hack|gadget|product)|crazy deal|mind-?blowing|before it gets banned|life-?changing)\b/gi;
  let cbMatch: RegExpExecArray | null;
  while ((cbMatch = clickbaitHookRegex.exec(clean)) !== null) {
    const matched = cbMatch[1];
    pressure_signals.push({
      type: "clickbait_hook",
      text: matched,
      source,
      meaning: `Advertisement uses an exaggerated clickbait hook ("${matched}") designed to manipulate emotional curiosity.`,
    });
  }

  // 10. Free Bait & Micro-Price Anchoring
  const freeBaitRegex = /\b(100%\s*free|pay only shipping|free gift inside|zero cost today|free\s*delivery|free\s*shipping)\b/gi;
  let fbMatch: RegExpExecArray | null;
  while ((fbMatch = freeBaitRegex.exec(clean)) !== null) {
    const matched = fbMatch[1];
    pressure_signals.push({
      type: "price_anchoring",
      text: matched,
      source,
      meaning: `Advertisement uses a free incentive ("${matched}") often associated with hidden recurring charges, conditional minimum carts, or platform promotion hooks.`,
    });
  }

  const microPriceRegex = /\b(?:at|for|only|just)\s*(?:₹|rs\.?|\$)\s*[01]\b|\b(?:₹|rs\.?|\$)\s*1\s*(?:deal|offer|sale)?\b/gi;
  let mpMatch: RegExpExecArray | null;
  while ((mpMatch = microPriceRegex.exec(clean)) !== null) {
    const matched = mpMatch[0];
    pressure_signals.push({
      type: "price_anchoring",
      text: matched,
      source,
      meaning: `Advertisement uses aggressive micro-price anchoring ("${matched}") designed to drive impulse clicks.`,
    });
  }

  // Deduplicate pressure signals by type and text
  const uniquePressureSignals: AdPressureSignal[] = [];
  const seenKeys = new Set<string>();
  for (const sig of pressure_signals) {
    const key = `${sig.type}:${sig.text.toLowerCase()}`;
    if (!seenKeys.has(key)) {
      seenKeys.add(key);
      uniquePressureSignals.push(sig);
    }
  }

  // Calculate Clickbait Score & Risk Level
  let rawScore = 0;
  const clickbait_flags: string[] = [];

  const extremeDiscounts = uniquePressureSignals.filter((s) => s.type === "extreme_discount");
  if (extremeDiscounts.length > 0) {
    rawScore += Math.min(35, extremeDiscounts.length * 20);
    clickbait_flags.push(`Extreme discount claims (${extremeDiscounts.map((d) => d.text).join(", ")})`);
  }

  const urgencySignals = uniquePressureSignals.filter((s) => s.type === "urgency");
  if (urgencySignals.length > 0) {
    rawScore += Math.min(25, urgencySignals.length * 15);
    clickbait_flags.push(`Artificial purchase urgency (${urgencySignals.map((u) => u.text).join(", ")})`);
  }

  const scarcitySignals = uniquePressureSignals.filter((s) => s.type === "scarcity");
  if (scarcitySignals.length > 0) {
    rawScore += Math.min(20, scarcitySignals.length * 10);
    clickbait_flags.push(`Manufactured scarcity (${scarcitySignals.map((s) => s.text).join(", ")})`);
  }

  const anchoringSignals = uniquePressureSignals.filter((s) => s.type === "price_anchoring");
  if (anchoringSignals.length > 0) {
    rawScore += Math.min(25, anchoringSignals.length * 15);
    clickbait_flags.push(`Aggressive price anchoring (${anchoringSignals.map((a) => a.text).join(", ")})`);
  }

  const guaranteeSignals = uniquePressureSignals.filter((s) => s.type === "performance_guarantee");
  if (guaranteeSignals.length > 0) {
    rawScore += Math.min(30, guaranteeSignals.length * 20);
    clickbait_flags.push(`Unsubstantiated outcome guarantees (${guaranteeSignals.map((g) => g.text).join(", ")})`);
  }

  const hookSignals = uniquePressureSignals.filter((s) => s.type === "clickbait_hook");
  if (hookSignals.length > 0) {
    rawScore += Math.min(25, hookSignals.length * 15);
    clickbait_flags.push(`Sensationalist clickbait hook (${hookSignals.map((h) => h.text).join(", ")})`);
  }

  const authSignals = uniquePressureSignals.filter((s) => s.type === "authority_certification");
  if (authSignals.length > 0) {
    rawScore += Math.min(20, authSignals.length * 10);
    clickbait_flags.push(`Unverified regulatory/clinical claims (${authSignals.map((a) => a.text).join(", ")})`);
  }

  const clickbait_score = Math.min(100, Math.max(0, rawScore));

  let clickbait_level: "LOW" | "MODERATE" | "HIGH" | "AGGRESSIVE" = "LOW";
  if (clickbait_score >= 70) {
    clickbait_level = "AGGRESSIVE";
  } else if (clickbait_score >= 45) {
    clickbait_level = "HIGH";
  } else if (clickbait_score >= 20) {
    clickbait_level = "MODERATE";
  }

  const claims_detected = Array.from(
    new Set([
      ...price_claims,
      ...authenticity_claims,
      ...urgency_claims,
      ...scarcity_claims,
      ...authority_claims,
      ...performance_claims,
      ...social_proof_claims,
      ...price_anchoring_claims,
      ...hookSignals.map((h) => h.text),
    ]),
  );

  return {
    clickbait_score,
    clickbait_level,
    clickbait_flags,
    claims_detected,
    ad_pressure_signals: uniquePressureSignals,
    price_claims: Array.from(new Set(price_claims)),
    authenticity_claims: Array.from(new Set(authenticity_claims)),
    urgency_claims: Array.from(new Set(urgency_claims)),
    scarcity_claims: Array.from(new Set(scarcity_claims)),
    authority_claims: Array.from(new Set(authority_claims)),
    performance_claims: Array.from(new Set(performance_claims)),
    social_proof_claims: Array.from(new Set(social_proof_claims)),
    price_anchoring_claims: Array.from(new Set(price_anchoring_claims)),
    pressure_signals: uniquePressureSignals,
  };
}
