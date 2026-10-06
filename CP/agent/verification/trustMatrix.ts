import type {
  NormalizedEvidence,
  InstagramEvidence,
  WebsiteEvidence,
  MediaEvidence,
  MetaAdEvidence,
  AdClaimAnalysis,
  TrustMatrix,
  MatrixFieldResult,
  TrustSignal,
  ConsistencyRating,
  SourceType,
} from "./types.ts";

function cleanStr(str?: string | null): string {
  if (!str) return "";
  return str.toLowerCase().replace(/[^a-z0-9]/g, "");
}

/**
 * Compares multi-source values for a single field and determines consistency.
 */
function evaluateFieldConsistency(
  field: string,
  sources: { source: SourceType; value: string }[],
): MatrixFieldResult {
  const valuesBySource: Record<string, string | null> = {
    instagram: null,
    website: null,
    product_image: null,
    seller: null,
    meta_ad: null,
  };

  for (const s of sources) {
    if (!valuesBySource[s.source]) {
      valuesBySource[s.source] = s.value;
    }
  }

  const distinctSources = Object.keys(valuesBySource).filter((k) => valuesBySource[k] !== null);

  if (distinctSources.length <= 1) {
    return {
      field,
      valuesBySource,
      result: distinctSources.length === 1 ? "MATCH" : "UNKNOWN",
      explanation: distinctSources.length === 1
        ? `${field} identified from single source (${distinctSources[0]}).`
        : `No ${field} data available across sources.`,
    };
  }

  const cleanedValues = distinctSources.map((k) => ({
    source: k as SourceType,
    raw: valuesBySource[k]!,
    clean: cleanStr(valuesBySource[k]!),
  }));

  // Check direct matches or substrings
  let allMatch = true;
  let hasContradiction = false;

  const base = cleanedValues[0].clean;
  for (let i = 1; i < cleanedValues.length; i++) {
    const curr = cleanedValues[i].clean;
    if (!curr || !base) continue;

    const isMatch = base === curr || base.includes(curr) || curr.includes(base);
    if (!isMatch) {
      allMatch = false;
      // If words are completely disjoint and length > 3, it's a contradiction
      const baseWords = cleanedValues[0].raw.toLowerCase().split(/\s+/).filter((w) => w.length > 3);
      const currWords = cleanedValues[i].raw.toLowerCase().split(/\s+/).filter((w) => w.length > 3);
      const overlap = baseWords.some((w) => currWords.includes(w) || curr.includes(w));
      if (!overlap && baseWords.length > 0 && currWords.length > 0) {
        hasContradiction = true;
      }
    }
  }

  let result: ConsistencyRating = "UNKNOWN";
  let explanation = "";

  if (hasContradiction) {
    result = "MISMATCH";
    explanation = `${field} contradicts across sources: ${cleanedValues.map((v) => `${v.source}="${v.raw}"`).join(" vs ")}`;
  } else if (allMatch) {
    result = "MATCH";
    explanation = `${field} is consistent across all ${distinctSources.length} sources.`;
  } else {
    result = "PARTIAL";
    explanation = `${field} partially aligns between sources.`;
  }

  return {
    field,
    valuesBySource,
    result,
    explanation,
  };
}

/**
 * Builds the Cross-Source Trust Matrix and evaluates signals.
 */
export function buildTrustMatrix(
  normalized: NormalizedEvidence,
  evidence: InstagramEvidence,
  website: WebsiteEvidence | null,
  media: MediaEvidence | null,
  metaAd?: MetaAdEvidence | null,
  adClaims?: AdClaimAnalysis | null,
): TrustMatrix {
  const fields: Record<string, MatrixFieldResult> = {
    brand: evaluateFieldConsistency("brand", normalized.brand),
    product_name: evaluateFieldConsistency("product_name", normalized.product_name),
    seller: evaluateFieldConsistency("seller", normalized.seller),
    price: evaluateFieldConsistency("price", normalized.price),
    manufacturer: evaluateFieldConsistency("manufacturer", normalized.manufacturer),
    website: evaluateFieldConsistency("website", normalized.website),
    contact: evaluateFieldConsistency("contact", normalized.contact),
  };

  const evidence_check = {
    instagram: Boolean(evidence.post.caption || evidence.account.username),
    meta_ad: metaAd?.status === "found",
    website: Boolean(website && website.status === "accessible"),
    product_image: Boolean(evidence.media.length > 0),
    ocr: Boolean(media?.ocr && media.ocr.status !== "failed" && media.ocr.text.length > 0),
  };

  const available_sources: SourceType[] = [];
  if (evidence_check.instagram) available_sources.push("instagram");
  if (evidence_check.meta_ad) available_sources.push("meta_ad");
  if (evidence_check.website) available_sources.push("website");
  if (evidence_check.product_image) available_sources.push("product_image");
  if (normalized.seller.length > 0) available_sources.push("seller");

  const trust_signals: TrustSignal[] = [];
  const risk_signals: TrustSignal[] = [];
  const missing_information: string[] = [];

  const hasWebsiteSource = evidence_check.website && website?.status === "accessible";
  const hasRegisteredEntity = Boolean(hasWebsiteSource && website?.company?.name);

  // 1. Trust Signals from Matrix with Provenance & Meaning
  if (fields.brand.result === "MATCH" && normalized.brand.length >= 2) {
    const brandSources = normalized.brand.map((s) => s.source);
    const includesWeb = brandSources.includes("website");
    trust_signals.push({
      signal: includesWeb
        ? "Brand matches across Instagram and independent external website"
        : "Brand text is consistent between Instagram listing and packaging OCR",
      severity: "positive",
      sources: brandSources,
      meaning: includesWeb
        ? "Brand name matches between social listing and external web store"
        : "Brand text in image OCR matches the post caption (does not verify brand authorization)",
    });
  }

  if (fields.product_name.result === "MATCH" && normalized.product_name.length >= 2) {
    const prodSources = normalized.product_name.map((s) => s.source);
    const includesWeb = prodSources.includes("website");
    trust_signals.push({
      signal: includesWeb
        ? "Product name is consistent across Instagram and independent website"
        : "Product name text is consistent between Instagram and packaging OCR",
      severity: "positive",
      sources: prodSources,
      meaning: includesWeb
        ? "Product name aligns between Instagram listing and external web store"
        : "Product name in image OCR matches the post text",
    });
  }

  // Meta Advertiser ↔ Instagram Account Alignment
  if (metaAd?.status === "found" && metaAd.advertiserName) {
    const cleanAdName = cleanStr(metaAd.advertiserName);
    const cleanInsta = cleanStr(evidence.account.username || "");
    const cleanDisplay = cleanStr(evidence.account.display_name || "");
    if (cleanAdName && (cleanAdName.includes(cleanInsta) || cleanInsta.includes(cleanAdName) || cleanAdName === cleanDisplay)) {
      trust_signals.push({
        signal: `Meta Ad advertiser identity aligns with Instagram seller (${metaAd.advertiserName})`,
        severity: "positive",
        sources: ["meta_ad", "instagram"],
        meaning: "Meta Ad Library records corroborate the advertiser page name with the Instagram profile",
      });
    }
  }

  // Only generate seller registered entity trust signal if independent entity evidence was collected
  if (fields.seller.result === "MATCH" && hasRegisteredEntity && normalized.seller.some((s) => s.source === "website")) {
    trust_signals.push({
      signal: `Seller identity matches registered entity on external store (${website?.company.name})`,
      severity: "positive",
      sources: ["seller", "website"],
      meaning: `Seller handle aligns with registered company entity "${website?.company.name}" on standalone website`,
    });
  }

  if (hasWebsiteSource && website) {
    trust_signals.push({
      signal: `External store website is active and accessible (${website.domain})`,
      severity: "positive",
      sources: ["website"],
      meaning: "Seller provides an active, accessible standalone web store",
    });
    if (website.policies.refund || website.policies.return) {
      trust_signals.push({
        signal: "Clear refund and return policy published on external store",
        severity: "positive",
        sources: ["website"],
        meaning: "Transparent return/refund terms found on store website",
      });
    }
  }

  if (media?.packaging?.regulatory.license_numbers && media.packaging.regulatory.license_numbers.length > 0) {
    trust_signals.push({
      signal: `Regulatory license number identified on packaging (${media.packaging.regulatory.license_numbers[0]})`,
      severity: "positive",
      sources: ["product_image"],
      meaning: "Packaging displays formal regulatory registration marks",
    });
  }

  // 2. Risk Signals from Matrix
  if (fields.brand.result === "MISMATCH") {
    risk_signals.push({
      signal: `Brand mismatch detected: ${fields.brand.explanation}`,
      severity: "high",
      sources: ["instagram", "product_image"],
      meaning: "Brand identified in packaging contradicts brand claimed in post listing",
    });
  }

  if (fields.product_name.result === "MISMATCH") {
    risk_signals.push({
      signal: `Product mismatch: ${fields.product_name.explanation}`,
      severity: "high",
      sources: ["instagram", "website"],
      meaning: "Product name on external link differs from Instagram post",
    });
  }

  if (fields.seller.result === "MISMATCH") {
    risk_signals.push({
      signal: "Seller identity differs significantly between Instagram and website",
      severity: "medium",
      sources: ["instagram", "website"],
      meaning: "Seller name or handle does not correspond to store website",
    });
  }

  // Check Meta Advertiser vs Website Company Contradiction
  if (
    metaAd?.status === "found" &&
    metaAd.advertiserName &&
    website?.status === "accessible" &&
    website.company.name &&
    cleanStr(metaAd.advertiserName) !== cleanStr(website.company.name) &&
    !cleanStr(metaAd.advertiserName).includes(cleanStr(website.company.name)) &&
    !cleanStr(website.company.name).includes(cleanStr(metaAd.advertiserName))
  ) {
    risk_signals.push({
      signal: `Meta advertiser and external website business identities are inconsistent: advertiser (${metaAd.advertiserName}) vs website company (${website.company.name})`,
      severity: "medium",
      sources: ["meta_ad", "website"],
      meaning: "Meta Ad is operated under a different entity name than the linked web store",
    });
  }

  // Pack size / quantity contradiction check
  const adOrCaption = `${evidence.post.caption || ""} ${metaAd?.adText || ""}`;
  const packMatch = adOrCaption.match(/(\d+)\s*(?:tablets?|capsules?|pieces?|pcs|pack|count|gm|g|ml|kg)/i);
  const ocrText = media?.ocr?.text || media?.packaging?.claims?.join(" ") || "";
  const ocrPackMatch = ocrText.match(/(\d+)\s*(?:tablets?|capsules?|pieces?|pcs|pack|count|gm|g|ml|kg)/i);
  if (packMatch && ocrPackMatch && packMatch[1] !== ocrPackMatch[1]) {
    risk_signals.push({
      signal: `Pack size / quantity contradiction: ad/listing claims ${packMatch[0]} while packaging evidence indicates ${ocrPackMatch[0]}`,
      severity: "high",
      sources: ["meta_ad", "product_image"],
      meaning: "Advertisement or caption claims a pack quantity that contradicts physical packaging OCR",
    });
  }

  // Ad Pressure Patterns (Informational Risk Indicators)
  const pressureCount =
    (adClaims?.pressure_signals?.length || 0) +
    (adClaims?.ad_pressure_signals?.length || 0);
  if (pressureCount >= 3 || (adClaims && (adClaims.claims_detected?.length || 0) >= 4)) {
    risk_signals.push({
      signal: "Multiple unverified high-pressure advertising patterns detected in ad creative",
      severity: "medium",
      sources: ["meta_ad"],
      meaning: "Ad creative combines extreme discounts, urgency, and scarcity claims that require independent verification",
    });
  }

  const caption = (evidence.post.caption || "").toLowerCase();
  if (/first\s*copy|master\s*copy|7a\s*quality|replica/i.test(caption)) {
    risk_signals.push({
      signal: "Post explicitly mentions replica or counterfeit terminology",
      severity: "high",
      sources: ["instagram"],
      meaning: "Listing caption contains keywords associated with unauthorized counterfeit goods",
    });
  }

  if (website && website.status === "inaccessible" && evidence.external_links.length > 0) {
    risk_signals.push({
      signal: `External store link provided (${website.domain}) is unreachable or down`,
      severity: "medium",
      sources: ["website"],
      meaning: "Linked domain returned connection or HTTP errors",
    });
  }

  // 3. Missing Information (NEVER treated automatically as risk/fraud)
  if (!evidence_check.website) {
    missing_information.push("No independent website store provided in listing");
  }
  if (!evidence_check.ocr) {
    missing_information.push("Packaging text could not be extracted via OCR");
  }
  if (!hasRegisteredEntity) {
    missing_information.push("Independent business registration not checked");
  }
  if (metaAd?.status === "not_found") {
    missing_information.push("No active Meta Ad Library campaigns found for advertiser/product");
  } else if (metaAd?.status === "unavailable") {
    missing_information.push("Meta Ad Library data was unavailable during verification");
  }

  // 4. Traceable Conclusions
  const traceable_conclusions = [
    { conclusion: `Brand verification: ${fields.brand.result}`, evidence: normalized.brand },
    { conclusion: `Product verification: ${fields.product_name.result}`, evidence: normalized.product_name },
    { conclusion: `Seller verification: ${fields.seller.result}`, evidence: normalized.seller },
  ];

  // 5. Dynamic Summary Explanation
  let summary_explanation = "";
  if (risk_signals.length > 0 && risk_signals.some((r) => r.severity === "high")) {
    summary_explanation = `Contradictory evidence detected across sources (${risk_signals[0].signal}).`;
  } else if (trust_signals.length >= 2 && hasWebsiteSource) {
    summary_explanation = "Multi-source evidence across Instagram and independent web store is broadly consistent.";
  } else if (evidence_check.product_image && evidence_check.instagram && !hasWebsiteSource) {
    summary_explanation = "Instagram post text and product image OCR are consistent, but no independent web store or business registration is available.";
  } else if (available_sources.length <= 1) {
    summary_explanation = "Verification is based on limited available sources. Please verify seller independently.";
  } else {
    summary_explanation = "Evidence is partially consistent with minor missing business information.";
  }

  return {
    fields,
    available_sources,
    evidence_check,
    trust_signals,
    risk_signals,
    missing_information,
    traceable_conclusions,
    summary_explanation,
  };
}
