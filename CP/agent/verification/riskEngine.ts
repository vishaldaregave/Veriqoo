import type {
  InstagramEvidence,
  ProductInfo,
  SellerInfo,
  Claim,
  WebsiteEvidence,
  ConsistencyResult,
  MediaEvidence,
  ImageCrossCheckResult,
  MetaAdEvidence,
  AdClaimAnalysis,
  TrustMatrix,
  RiskAnalysisResult,
  RiskLevel,
} from "./types.ts";

/**
 * Evaluates risk and calculated confidence based on multi-source evidence,
 * normalized trust matrix, and cross-source consistency checks.
 */
export function evaluateRisk(
  evidence: InstagramEvidence,
  product: ProductInfo,
  seller: SellerInfo,
  claims: Claim[],
  website?: WebsiteEvidence | null,
  consistency?: ConsistencyResult | null,
  mediaEvidence?: MediaEvidence | null,
  imageCrossCheck?: ImageCrossCheckResult | null,
  trustMatrix?: TrustMatrix | null,
  metaAd?: MetaAdEvidence | null,
  adClaims?: AdClaimAnalysis | null,
): RiskAnalysisResult {
  const hasCaption = Boolean(evidence.post.caption);
  const hasUsername = Boolean(evidence.account.username);

  // If evidence was not obtainable from Instagram, return UNKNOWN / Insufficient data
  if (!hasCaption && !hasUsername) {
    return {
      risk_level: "UNKNOWN",
      confidence: 0,
      positive_signals: [],
      risk_signals: [],
      missing_information: [
        "Instagram metadata could not be fetched (private post, login wall, or network limitation).",
      ],
      consistency_checks: [],
      recommendation:
        "Do not treat this result as proof that the product is fake. Verify the seller independently before purchasing.",
      explanation: "No meaningful Instagram evidence could be retrieved.",
      evidence_check: {
        instagram: false,
        meta_ad: false,
        website: false,
        product_image: false,
        ocr: false,
      },
    };
  }

  const positive_signals: string[] = [];
  const risk_signals: string[] = [];
  const missing_information: string[] = [
    ...(evidence.missing_information || []),
    ...(trustMatrix?.missing_information || []),
  ];
  const consistency_checks: string[] = [
    ...(consistency?.details || []),
    ...(imageCrossCheck?.details || []),
    ...(adClaims?.pressure_signals.map((p) => `[Ad Pattern] ${p.text} (${p.type})`) || []),
  ];

  // Populate signals from Trust Matrix if available
  if (trustMatrix) {
    for (const ts of trustMatrix.trust_signals) {
      positive_signals.push(ts.signal);
    }
    for (const rs of trustMatrix.risk_signals) {
      risk_signals.push(rs.signal);
    }
  }

  // Fallback / direct signals if trust matrix is not provided
  if (positive_signals.length === 0) {
    if (seller.username) positive_signals.push(`Seller account identified: @${seller.username}`);
    if (product.name) positive_signals.push("Product information found in listing");
    if (website?.status === "accessible") positive_signals.push(`Website accessible (${website.domain})`);
  }

  // Evaluate Evidence Coverage & Independent Corroboration
  const hasWebsite = Boolean(website && website.status === "accessible");
  const hasMedia = evidence.media.length > 0;
  const hasOcr = Boolean(mediaEvidence?.ocr && mediaEvidence.ocr.status !== "failed" && mediaEvidence.ocr.text.length > 0);
  const hasPackagingLicense = Boolean(mediaEvidence?.packaging?.regulatory.license_numbers && mediaEvidence.packaging.regulatory.license_numbers.length > 0);
  const hasIndependentEvidence = hasWebsite || hasPackagingLicense;

  // Calculated Confidence Model based on genuine multi-source coverage
  let confidence = 25; // Base confidence for single Instagram source
  if (hasMedia && hasOcr && !hasWebsite) {
    confidence = 45; // Instagram + Media OCR (sparse, same publisher)
  } else if (hasWebsite && !hasMedia) {
    confidence = 65; // Instagram + Independent Website
  } else if (hasWebsite && (hasMedia || hasOcr)) {
    confidence = 80; // Full multi-source (Social + Independent Store + Packaging)
  }

  // Agreement adjustments
  if (trustMatrix && hasWebsite) {
    if (trustMatrix.fields.brand.result === "MATCH") confidence += 5;
    if (trustMatrix.fields.product_name.result === "MATCH") confidence += 5;
  }

  // High Risk Signal Check
  const hasHighRiskSignal = risk_signals.some(
    (s) =>
      s.toLowerCase().includes("mismatch") ||
      s.toLowerCase().includes("replica") ||
      s.toLowerCase().includes("counterfeit") ||
      s.toLowerCase().includes("unreachable"),
  );

  // -------------------------------------------------------------
  // Safety Score Calculation (0 - 100)
  // -------------------------------------------------------------
  let safety_score = 65; // Baseline neutral score for a public post

  // Positive trust boosters:
  if (seller.username) safety_score += 5;
  if (hasWebsite) safety_score += 10;
  if (website?.policies?.refund || website?.policies?.returns) safety_score += 15;
  if (website?.contact?.email || website?.contact?.phone) safety_score += 10;
  if (hasPackagingLicense) safety_score += 15;
  if (trustMatrix && trustMatrix.fields.brand.result === "MATCH") safety_score += 10;
  if (trustMatrix && trustMatrix.fields.product_name.result === "MATCH") safety_score += 5;
  if (metaAd && metaAd.status === "found") safety_score += 10;

  // Clickbait & Deceptive Advertising Deductions:
  const cbScore = adClaims?.clickbait_score || 0;
  const cbLevel = adClaims?.clickbait_level || "LOW";
  if (cbScore >= 75) {
    safety_score -= 35;
    risk_signals.push(`Aggressive advertising pressure detected (Clickbait Index: ${cbScore}/100)`);
  } else if (cbScore >= 45) {
    safety_score -= 20;
    risk_signals.push(`High advertising pressure detected (Clickbait Index: ${cbScore}/100)`);
  } else if (cbScore >= 20) {
    safety_score -= 10;
  }

  // Severe risk deductions:
  if (hasHighRiskSignal) {
    safety_score -= 40;
  }
  if (trustMatrix && trustMatrix.fields.price.result === "MISMATCH") {
    safety_score -= 25;
  }
  if (!hasWebsite && !hasPackagingLicense) {
    safety_score -= 15; // Zero independent store or regulatory corroboration
  }

  // Bound safety_score between 5 and 98
  safety_score = Math.max(5, Math.min(98, Math.round(safety_score)));

  // Determine Risk Level based on Safety Score and corroboration
  let risk_level: RiskLevel = "UNKNOWN";
  if (safety_score < 45 || hasHighRiskSignal || risk_signals.length >= 2) {
    risk_level = "HIGH";
    confidence = Math.max(confidence, 80);
  } else if (safety_score >= 72 && positive_signals.length >= 1 && hasIndependentEvidence) {
    risk_level = "LOW";
    confidence = Math.min(90, Math.max(65, confidence));
  } else if (!hasIndependentEvidence && !hasMedia && !hasOcr) {
    risk_level = "UNKNOWN";
    confidence = Math.min(30, confidence);
  } else if (!hasCaption && !hasUsername) {
    risk_level = "UNKNOWN";
    confidence = Math.min(30, confidence);
  } else {
    risk_level = "MEDIUM";
    confidence = Math.max(50, Math.min(75, confidence));
  }

  // Cap confidence between 10 and 95
  confidence = Math.max(10, Math.min(95, confidence));

  // Recommendation construction
  let recommendation = "";
  if (risk_level === "HIGH") {
    recommendation = `High risk detected (Safety Score: ${safety_score}/100). Unverified seller, high clickbait, or conflicting claims found. Do NOT make advance online payments; insist on Cash on Delivery (COD) or avoid purchasing.`;
  } else if (risk_level === "MEDIUM") {
    if (cbScore >= 45) {
      recommendation = `Moderate risk (Safety Score: ${safety_score}/100). Heavy promotional pressure detected (${cbScore}/100). Verify real customer reviews and refund policies before purchasing.`;
    } else if (!hasIndependentEvidence) {
      recommendation = `Proceed with caution (Safety Score: ${safety_score}/100). No independent web store or registered entity was found. Verify the seller and return policies before making advance payments.`;
    } else {
      recommendation = `Proceed with caution (Safety Score: ${safety_score}/100). Check seller reviews and verify return policies independently before purchasing.`;
    }
  } else if (risk_level === "LOW") {
    recommendation = `Low risk (Safety Score: ${safety_score}/100). Multi-source evidence is consistent across independent platforms. Proceed with standard online purchasing precautions.`;
  } else {
    recommendation =
      "Only limited single-source evidence was available. Verify the seller and product details independently.";
  }

  const explanation =
    trustMatrix?.summary_explanation ||
    (risk_level === "LOW"
      ? "Multi-source evidence across Instagram and independent web store is broadly consistent."
      : "Multi-source evidence check completed.");

  return {
    risk_level,
    confidence,
    safety_score,
    clickbait_score: cbScore,
    clickbait_level: cbLevel,
    positive_signals: Array.from(new Set(positive_signals)),
    risk_signals: Array.from(new Set(risk_signals)),
    missing_information: Array.from(new Set(missing_information)),
    consistency_checks: Array.from(new Set(consistency_checks)),
    recommendation,
    explanation,
    evidence_check: trustMatrix?.evidence_check || {
      instagram: true,
      website: Boolean(website?.status === "accessible"),
      product_image: evidence.media.length > 0,
      ocr: Boolean(mediaEvidence?.ocr?.text),
    },
    trust_matrix: trustMatrix || undefined,
  };
}
