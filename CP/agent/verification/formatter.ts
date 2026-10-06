import type { VerificationResult, RiskLevel } from "./types.ts";

function getRiskHeader(level: RiskLevel): string {
  switch (level) {
    case "LOW":
      return "🟢 RISK: LOW";
    case "MEDIUM":
      return "🟠 RISK: MEDIUM";
    case "HIGH":
      return "🔴 RISK: HIGH";
    case "UNKNOWN":
    default:
      return "⚪ RISK: UNKNOWN";
  }
}

/**
 * Formats the VerificationResult into the complete Feature 4 Multi-Source Trust Verification layout.
 */
export function formatVerificationResult(result: VerificationResult): string {
  if (result.status === "INSUFFICIENT_EVIDENCE") {
    const reason =
      result.failure_reason ||
      result.evidence.errors[0] ||
      result.evidence.missing_information[0] ||
      "Post is private, deleted, or requires login to access.";

    return [
      "🔍 PRODUCT VERIFICATION",
      "",
      "Status: ⚪ INSUFFICIENT EVIDENCE",
      "",
      "I could not collect enough Instagram evidence to verify this product.",
      "",
      "Reason:",
      reason,
      "",
      "Recommendation:",
      "Do not treat this result as proof that the product is fake. Verify the seller independently before purchasing.",
    ].join("\n");
  }

  const { product, risk, evidence, media_evidence, trust_matrix } = result;
  const productName = product.name || media_evidence?.packaging?.product.name || "Instagram Product / Item";
  const brandName =
    product.brand ||
    media_evidence?.packaging?.product.brand ||
    (evidence.account.username ? `@${evidence.account.username}` : "Unspecified");

  const evidenceCheck = risk.evidence_check || {
    instagram: true,
    meta_ad: Boolean(result.meta_ad_evidence?.status === "found"),
    website: Boolean(result.website_evidence?.status === "accessible"),
    product_image: evidence.media.length > 0,
    ocr: Boolean(media_evidence?.ocr?.status === "success" || media_evidence?.ocr?.status === "partial"),
  };

  const safetyScoreText = risk.safety_score !== undefined ? `${risk.safety_score}/100` : "N/A";
  const clickbaitText = `${risk.clickbait_level || "LOW"} (${risk.clickbait_score ?? 0}/100)`;

  const lines: string[] = [
    "🔍 PRODUCT VERIFICATION",
    "",
    "Product:",
    productName,
    "",
    "Brand:",
    brandName,
    "",
    "━━━━━━━━━━━━━━",
    "",
    getRiskHeader(risk.risk_level),
    "",
    "Confidence:",
    `${risk.confidence}%`,
    "",
    `🛡️ Safety Score: ${safetyScoreText}`,
    `🎣 Clickbait Risk: ${clickbaitText}`,
    "",
    "━━━━━━━━━━━━━━",
    "",
    "🔎 EVIDENCE CHECK",
    "",
    `Instagram      ${evidenceCheck.instagram ? "✅" : "⚪"}`,
    `Meta Ad        ${evidenceCheck.meta_ad ? "✅" : "⚪"}`,
    `Website        ${evidenceCheck.website ? "✅" : "⚪"}`,
    `Product Image  ${evidenceCheck.product_image ? "✅" : "⚪"}`,
    `OCR            ${evidenceCheck.ocr ? "✅" : "⚪"}`,
  ];

  // Optional: Meta Ad Intelligence Section
  if (result.meta_ad_evidence && result.meta_ad_evidence.status === "found") {
    lines.push("");
    lines.push("━━━━━━━━━━━━━━");
    lines.push("");
    lines.push("📣 META AD INTELLIGENCE");
    lines.push("");
    lines.push(`Status: FOUND`);
    if (result.meta_ad_evidence.advertiserName) {
      lines.push(`Advertiser: ${result.meta_ad_evidence.advertiserName}`);
    }
    if (result.meta_ad_evidence.libraryId) {
      lines.push(`Library ID: ${result.meta_ad_evidence.libraryId}`);
    }
    if (result.meta_ad_evidence.publisherPlatforms && result.meta_ad_evidence.publisherPlatforms.length > 0) {
      lines.push(`Platforms: ${result.meta_ad_evidence.publisherPlatforms.join(", ")}`);
    }
    if (result.meta_ad_evidence.deliveryStart) {
      lines.push(`Delivery: ${result.meta_ad_evidence.deliveryStart} → ${result.meta_ad_evidence.deliveryEnd || "Active"}`);
    }
  }

  // Optional: Ad Claim Analysis Section
  const allClaims: string[] = [
    ...(result.ad_claim_analysis?.claims_detected || []),
    ...(result.ad_claim_analysis?.price_claims || []),
    ...(result.ad_claim_analysis?.authenticity_claims || []),
    ...(result.ad_claim_analysis?.urgency_claims || []),
    ...(result.ad_claim_analysis?.scarcity_claims || []),
    ...(result.ad_claim_analysis?.authority_claims || []),
  ];
  const uniqueClaims = Array.from(new Set(allClaims));
  const pressureSignals =
    result.ad_claim_analysis?.ad_pressure_signals ||
    result.ad_claim_analysis?.pressure_signals ||
    [];

  if (uniqueClaims.length > 0 || pressureSignals.length > 0) {
    lines.push("");
    lines.push("━━━━━━━━━━━━━━");
    lines.push("");
    lines.push("📢 AD CLAIM ANALYSIS & CLICKBAIT AUDIT");
    lines.push("");
    if (result.ad_claim_analysis?.clickbait_score !== undefined) {
      lines.push(`Clickbait Level: ${result.ad_claim_analysis.clickbait_level || "LOW"} (${result.ad_claim_analysis.clickbait_score}/100)`);
    }
    if (result.ad_claim_analysis?.clickbait_flags && result.ad_claim_analysis.clickbait_flags.length > 0) {
      lines.push("");
      lines.push("🚩 Clickbait & Pressure Triggers:");
      for (const flag of result.ad_claim_analysis.clickbait_flags.slice(0, 4)) {
        lines.push(`• ${flag}`);
      }
    }
    if (uniqueClaims.length > 0) {
      lines.push("");
      lines.push("Key claims detected:");
      for (const c of uniqueClaims.slice(0, 4)) {
        lines.push(`• "${c}"`);
      }
    }
    if (pressureSignals.length > 0) {
      lines.push("");
      lines.push("Tactics flagged:");
      for (const p of pressureSignals.slice(0, 3)) {
        lines.push(`⚠️ ${p.type.replace(/_/g, " ")}: "${p.text}"`);
      }
    }
    lines.push("");
    lines.push("_High promotional pressure indicates need for independent price & seller verification._");
  }

  lines.push("");
  lines.push("━━━━━━━━━━━━━━");
  lines.push("");
  lines.push("✅ TRUST SIGNALS");
  lines.push("");

  if (risk.positive_signals.length > 0) {
    for (const sig of risk.positive_signals.slice(0, 5)) {
      lines.push(`• ${sig}`);
    }
  } else {
    lines.push("• Single-source listing (no multi-platform corroboration)");
  }

  lines.push("");
  lines.push("━━━━━━━━━━━━━━");
  lines.push("");
  lines.push("⚠️ RISK SIGNALS");
  lines.push("");

  if (risk.risk_signals.length > 0) {
    for (const rs of risk.risk_signals) {
      lines.push(`• ${rs}`);
    }
  } else {
    lines.push("• None detected");
  }

  if (risk.missing_information.length > 0) {
    lines.push("");
    lines.push("━━━━━━━━━━━━━━");
    lines.push("");
    lines.push("❓ MISSING INFORMATION");
    lines.push("");
    for (const m of risk.missing_information.slice(0, 3)) {
      lines.push(`• ${m}`);
    }
  }

  lines.push("");
  lines.push("━━━━━━━━━━━━━━");
  lines.push("");
  lines.push("💡 WHY?");
  lines.push("");
  lines.push(risk.explanation || trust_matrix?.summary_explanation || "Evidence-based multi-source verification completed.");

  lines.push("");
  lines.push("━━━━━━━━━━━━━━");
  lines.push("");
  lines.push("RECOMMENDATION");
  lines.push("");
  lines.push(risk.recommendation);

  return lines.join("\n");
}
