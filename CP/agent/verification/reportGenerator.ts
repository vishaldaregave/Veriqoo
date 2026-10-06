import * as fs from "node:fs";
import * as path from "node:path";
import type { VerificationResult, RiskLevel } from "./types.ts";
import type { VerificationReportData, GeneratedReport } from "./reportTypes.ts";

/**
 * Escapes dynamic string for safe HTML injection.
 */
export function escapeHtml(str: unknown): string {
  if (str === null || str === undefined) return "";
  const text = String(str);
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function generateReportId(): string {
  const timestamp = Date.now().toString(36);
  const randomSuffix = Math.random().toString(36).substring(2, 8);
  return `REP-${timestamp}-${randomSuffix}`.toUpperCase();
}

function formatResultBadge(rating: string): string {
  switch (rating) {
    case "MATCH":
      return `<span class="badge badge-success">✓ MATCH</span>`;
    case "PARTIAL":
      return `<span class="badge badge-warning">~ PARTIAL</span>`;
    case "MISMATCH":
      return `<span class="badge badge-danger">✕ MISMATCH</span>`;
    default:
      return `<span class="badge badge-neutral">— UNKNOWN</span>`;
  }
}

function formatRiskBadge(level: RiskLevel): string {
  switch (level) {
    case "LOW":
      return `<span class="badge badge-risk-low">🟢 LOW RISK</span>`;
    case "MEDIUM":
      return `<span class="badge badge-risk-medium">🟠 MEDIUM RISK</span>`;
    case "HIGH":
      return `<span class="badge badge-risk-high">🔴 HIGH RISK</span>`;
    default:
      return `<span class="badge badge-risk-unknown">⚪ UNKNOWN RISK</span>`;
  }
}

function formatAvailabilityBadge(status: "AVAILABLE" | "UNAVAILABLE"): string {
  if (status === "AVAILABLE") {
    return `<span class="badge badge-success">AVAILABLE</span>`;
  }
  return `<span class="badge badge-neutral">UNAVAILABLE</span>`;
}

/**
 * Extracts structured report data from VerificationResult.
 */
export function buildReportData(result: VerificationResult): VerificationReportData {
  const report_id = generateReportId();
  const generated_at = new Date().toISOString();

  const source_overview: {
    instagram: "AVAILABLE" | "UNAVAILABLE";
    meta_ad: "AVAILABLE" | "UNAVAILABLE";
    website: "AVAILABLE" | "UNAVAILABLE";
    product_image: "AVAILABLE" | "UNAVAILABLE";
    ocr: "AVAILABLE" | "UNAVAILABLE";
  } = {
    instagram: (result.evidence?.post?.caption || result.evidence?.account?.username) ? "AVAILABLE" : "UNAVAILABLE",
    meta_ad: (result.meta_ad_evidence && result.meta_ad_evidence.status === "found") ? "AVAILABLE" : "UNAVAILABLE",
    website: (result.website_evidence && result.website_evidence.status === "accessible") ? "AVAILABLE" : "UNAVAILABLE",
    product_image: (result.evidence?.media && result.evidence.media.length > 0) ? "AVAILABLE" : "UNAVAILABLE",
    ocr: (result.media_evidence?.ocr && result.media_evidence.ocr.status !== "failed" && result.media_evidence.ocr.text.length > 0) ? "AVAILABLE" : "UNAVAILABLE",
  };

  const product = {
    name: result.product?.name || result.media_evidence?.packaging?.product.name || null,
    brand: result.product?.brand || result.media_evidence?.packaging?.product.brand || null,
    category: result.product?.category || result.media_evidence?.packaging?.product.category || null,
    price: result.product?.price || result.media_evidence?.packaging?.product.price || null,
    mrp: result.media_evidence?.packaging?.product.mrp || null,
  };

  const seller = {
    username: result.seller?.username || null,
    name: result.seller?.name || result.website_evidence?.company.name || null,
    website: result.seller?.website || result.website_evidence?.url || null,
    contact: result.seller?.contact || result.website_evidence?.company.email || result.website_evidence?.company.phone || null,
    address: result.website_evidence?.company.address || result.media_evidence?.packaging?.manufacturer.address || null,
  };

  const policiesFound: string[] = [];
  if (result.website_evidence?.policies.refund) policiesFound.push("Refund");
  if (result.website_evidence?.policies.return) policiesFound.push("Return");
  if (result.website_evidence?.policies.shipping) policiesFound.push("Shipping");
  if (result.website_evidence?.policies.privacy) policiesFound.push("Privacy");
  if (result.website_evidence?.policies.terms) policiesFound.push("Terms");

  const evidence = {
    instagram: {
      available: source_overview.instagram === "AVAILABLE",
      caption: result.evidence?.post?.caption || null,
      timestamp: result.evidence?.post?.timestamp || null,
      external_links: result.evidence?.external_links || [],
      evidence_count: result.evidence?.evidence?.length || 0,
    },
    meta_ad: {
      available: source_overview.meta_ad === "AVAILABLE",
      status: result.meta_ad_evidence?.status || "unavailable",
      library_id: result.meta_ad_evidence?.libraryId || null,
      advertiser: result.meta_ad_evidence?.advertiserName || null,
    },
    website: {
      available: source_overview.website === "AVAILABLE",
      domain: result.website_evidence?.domain || null,
      company_name: result.website_evidence?.company.name || null,
      policies_found: policiesFound,
    },
    product_image: {
      available: source_overview.product_image === "AVAILABLE",
      image_count: result.evidence?.media?.length || 0,
      analyzed: result.media_evidence?.status === "analyzed",
    },
    ocr: {
      available: source_overview.ocr === "AVAILABLE",
      status: result.media_evidence?.ocr?.status || "none",
      confidence: result.media_evidence?.ocr?.confidence || 0,
      text_snippet: result.media_evidence?.ocr?.text ? result.media_evidence.ocr.text.slice(0, 300) : null,
    },
  };

  const executive_finding =
    result.risk?.explanation ||
    result.trust_matrix?.summary_explanation ||
    "Multi-source verification completed based on available listing and packaging evidence.";

  const consistency_matrix = result.trust_matrix?.fields || {};
  const trust_signals = result.trust_matrix?.trust_signals || result.risk?.positive_signals.map((s) => ({ signal: s, severity: "positive" as const, sources: ["instagram" as const] })) || [];
  const risk_signals = result.trust_matrix?.risk_signals || result.risk?.risk_signals.map((s) => ({ signal: s, severity: "medium" as const, sources: ["instagram" as const] })) || [];
  const missing_information = result.risk?.missing_information || result.trust_matrix?.missing_information || [];
  const traceable_conclusions = result.trust_matrix?.traceable_conclusions || [];
  const recommendation = result.risk?.recommendation || "Verify seller before purchasing.";
  const disclaimer = "This verification is an evidence-based assessment and is not a guarantee of product authenticity, seller legitimacy, or legal compliance.";

  return {
    report_id,
    generated_at,
    source: {
      instagram_url: result.evidence?.source?.url || "",
      website_url: seller.website,
    },
    product,
    seller,
    risk: {
      level: result.risk?.risk_level || "UNKNOWN",
      confidence: result.risk?.confidence || 0,
      safety_score: result.risk?.safety_score,
      clickbait_score: result.risk?.clickbait_score,
      clickbait_level: result.risk?.clickbait_level,
    },
    evidence,
    source_overview,
    executive_finding,
    consistency_matrix,
    trust_signals,
    risk_signals,
    missing_information,
    traceable_conclusions,
    recommendation,
    disclaimer,
  };
}

/**
 * Builds self-contained HTML report.
 */
export function buildReportHtml(data: VerificationReportData, rawResult: VerificationResult): string {
  const packaging = rawResult.media_evidence?.packaging;

  // Build consistency table rows
  const matrixKeys = ["brand", "product_name", "price", "pack_size", "seller", "manufacturer", "website", "contact"];
  const matrixRows = matrixKeys
    .map((key) => {
      const field = data.consistency_matrix[key];
      const fieldLabel = key.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
      const instaVal = field?.valuesBySource?.instagram || (key === "brand" ? data.product.brand : key === "product_name" ? data.product.name : key === "price" ? data.product.price : key === "seller" ? data.seller.username : null);
      const metaVal = field?.valuesBySource?.meta_ad || (key === "brand" ? rawResult.meta_ad_evidence?.linkTitle : key === "product_name" ? rawResult.meta_ad_evidence?.linkTitle : key === "seller" ? rawResult.meta_ad_evidence?.advertiserName : null);
      const webVal = field?.valuesBySource?.website || (key === "brand" ? rawResult.website_evidence?.product.brand : key === "product_name" ? rawResult.website_evidence?.product.name : key === "price" ? rawResult.website_evidence?.product.price : key === "seller" ? rawResult.website_evidence?.company.name : null);
      const imgVal = field?.valuesBySource?.product_image || (key === "brand" ? packaging?.product.brand : key === "product_name" ? packaging?.product.name : key === "price" ? packaging?.product.mrp : key === "manufacturer" ? packaging?.manufacturer.name : null);
      const rating = field?.result || (instaVal && (webVal || imgVal || metaVal) ? "MATCH" : "UNKNOWN");

      return `
        <tr>
          <td class="font-semibold">${escapeHtml(fieldLabel)}</td>
          <td>${escapeHtml(instaVal || "—")}</td>
          <td>${escapeHtml(metaVal || "—")}</td>
          <td>${escapeHtml(webVal || "—")}</td>
          <td>${escapeHtml(imgVal || "—")}</td>
          <td>${formatResultBadge(rating)}</td>
        </tr>
      `;
    })
    .join("");

  // Build trust signals
  const trustSignalsHtml = data.trust_signals.length > 0
    ? data.trust_signals.map((ts) => `
        <div class="signal-item signal-positive">
          <div class="signal-title">✅ ${escapeHtml(ts.signal)}</div>
          ${ts.meaning ? `<div class="signal-meaning" style="font-size: 13px; color: #334155; margin-top: 2px;">${escapeHtml(ts.meaning)}</div>` : ""}
          <div class="signal-sources">Sources: ${escapeHtml(ts.sources.join(", "))}</div>
        </div>
      `).join("")
    : `<div class="empty-text">No multi-source trust signals detected.</div>`;

  // Build risk signals
  const riskSignalsHtml = data.risk_signals.length > 0
    ? data.risk_signals.map((rs) => `
        <div class="signal-item signal-risk signal-risk-${escapeHtml(rs.severity)}">
          <div class="signal-title">⚠️ ${escapeHtml(rs.signal)}</div>
          <div class="signal-sources">Severity: <strong>${escapeHtml(rs.severity.toUpperCase())}</strong> | Sources: ${escapeHtml(rs.sources.join(", "))}</div>
        </div>
      `).join("")
    : `<div class="empty-text">No risk signals detected based on available evidence.</div>`;

  // Build missing information
  const missingInfoHtml = data.missing_information.length > 0
    ? data.missing_information.map((m) => `<li>${escapeHtml(m)}</li>`).join("")
    : `<li>All standard verification sources were accessible.</li>`;

  // Build traceable conclusions
  const traceableHtml = data.traceable_conclusions.length > 0
    ? data.traceable_conclusions.map((tc) => `
        <div class="traceable-card">
          <div class="traceable-conclusion font-semibold">🔍 ${escapeHtml(tc.conclusion)}</div>
          <div class="traceable-evidence">
            ${tc.evidence.length > 0
              ? tc.evidence.map((ev) => `
                  <div class="trace-row">
                    <span class="trace-tag">${escapeHtml(ev.source)}</span>
                    <span class="trace-value">${escapeHtml(ev.value)}</span>
                  </div>
                `).join("")
              : `<div class="trace-empty">No direct source values recorded</div>`
            }
          </div>
        </div>
      `).join("")
    : `<div class="empty-text">Evidence traceability mapping generated based on listing data.</div>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verification Report - ${escapeHtml(data.report_id)}</title>
  <style>
    :root {
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --border: #e2e8f0;
      --text: #0f172a;
      --text-muted: #64748b;
      --primary: #0284c7;
      --success: #16a34a;
      --warning: #ea580c;
      --danger: #dc2626;
      --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--font-family);
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding: 32px 16px;
    }
    .container {
      max-width: 900px;
      margin: 0 auto;
      background: var(--card-bg);
      border-radius: 12px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
      border: 1px solid var(--border);
      overflow: hidden;
    }
    .header {
      padding: 28px 32px;
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      color: #ffffff;
    }
    .header-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .header-title {
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.5px;
    }
    .report-meta {
      font-size: 13px;
      color: #94a3b8;
    }
    .section {
      padding: 24px 32px;
      border-bottom: 1px solid var(--border);
    }
    .section:last-child {
      border-bottom: none;
    }
    .section-title {
      font-size: 14px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--text-muted);
      margin-bottom: 16px;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
    }
    .summary-card {
      background: #f1f5f9;
      border-radius: 8px;
      padding: 14px 16px;
      border: 1px solid #e2e8f0;
    }
    .summary-label {
      font-size: 12px;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 600;
    }
    .summary-value {
      font-size: 16px;
      font-weight: 600;
      color: var(--text);
      margin-top: 4px;
    }
    .badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.3px;
    }
    .badge-success { background: #dcfce7; color: #15803d; }
    .badge-warning { background: #ffedd5; color: #c2410c; }
    .badge-danger { background: #fee2e2; color: #b91c1c; }
    .badge-neutral { background: #f1f5f9; color: #64748b; }
    .badge-risk-low { background: #dcfce7; color: #166534; font-size: 14px; padding: 6px 14px; }
    .badge-risk-medium { background: #ffedd5; color: #9a3412; font-size: 14px; padding: 6px 14px; }
    .badge-risk-high { background: #fee2e2; color: #991b1b; font-size: 14px; padding: 6px 14px; }
    .badge-risk-unknown { background: #f1f5f9; color: #475569; font-size: 14px; padding: 6px 14px; }

    .source-table, .data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    .source-table th, .source-table td,
    .data-table th, .data-table td {
      padding: 10px 14px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }
    .source-table th, .data-table th {
      background: #f8fafc;
      color: var(--text-muted);
      font-weight: 600;
      font-size: 12px;
      text-transform: uppercase;
    }
    .info-list {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
    }
    .info-row {
      display: flex;
      flex-direction: column;
    }
    .info-label {
      font-size: 12px;
      color: var(--text-muted);
    }
    .info-value {
      font-size: 14px;
      font-weight: 600;
    }
    .signal-item {
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 10px;
      border-left: 4px solid transparent;
    }
    .signal-positive {
      background: #f0fdf4;
      border-left-color: var(--success);
    }
    .signal-risk {
      background: #fef2f2;
      border-left-color: var(--danger);
    }
    .signal-risk-medium {
      background: #fff7ed;
      border-left-color: var(--warning);
    }
    .signal-title {
      font-weight: 600;
      font-size: 14px;
    }
    .signal-sources {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .missing-list {
      padding-left: 20px;
      font-size: 14px;
      color: #475569;
    }
    .missing-list li {
      margin-bottom: 6px;
    }
    .traceable-card {
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 16px;
      margin-bottom: 10px;
    }
    .traceable-conclusion {
      font-size: 14px;
      margin-bottom: 8px;
    }
    .trace-row {
      display: flex;
      gap: 10px;
      align-items: center;
      font-size: 13px;
      margin-top: 4px;
    }
    .trace-tag {
      background: #e2e8f0;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      color: #334155;
    }
    .trace-value {
      color: var(--text);
    }
    .font-semibold { font-weight: 600; }
    .executive-text {
      font-size: 15px;
      color: #1e293b;
      background: #f8fafc;
      border-left: 4px solid var(--primary);
      padding: 14px 18px;
      border-radius: 0 8px 8px 0;
    }
    .disclaimer-box {
      font-size: 12px;
      color: var(--text-muted);
      background: #f8fafc;
      padding: 16px 20px;
      border-radius: 8px;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <div class="header">
      <div class="header-top">
        <div class="header-title">🛡️ PRODUCT TRUST VERIFICATION REPORT</div>
        <div class="report-meta">
          <div>Report ID: <strong>${escapeHtml(data.report_id)}</strong></div>
          <div>Date: ${escapeHtml(data.generated_at)}</div>
        </div>
      </div>
    </div>

    <!-- Executive Finding -->
    <div class="section">
      <div class="section-title">Executive Finding</div>
      <div class="executive-text">${escapeHtml(data.executive_finding)}</div>
    </div>

    <!-- Verification Summary -->
    <div class="section">
      <div class="section-title">Verification Summary</div>
      <div class="summary-grid">
        <div class="summary-card">
          <div class="summary-label">Risk Assessment</div>
          <div class="summary-value" style="margin-top:8px;">${formatRiskBadge(data.risk.level)}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Safety Score</div>
          <div class="summary-value" style="color: ${data.risk.level === "LOW" ? "var(--success)" : data.risk.level === "MEDIUM" ? "var(--warning)" : "var(--danger)"}; font-weight:700;">
            ${escapeHtml(data.risk.safety_score !== undefined ? `${data.risk.safety_score}/100` : `${data.risk.confidence}%`)}
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Clickbait Risk</div>
          <div class="summary-value" style="font-size: 15px; margin-top: 4px;">
            ${escapeHtml(data.risk.clickbait_level || "LOW")} (${escapeHtml(data.risk.clickbait_score || 0)}/100)
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Analysis Confidence</div>
          <div class="summary-value">${escapeHtml(data.risk.confidence)}%</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Product Name</div>
          <div class="summary-value">${escapeHtml(data.product.name || "Unspecified")}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">Brand / Creator</div>
          <div class="summary-value">${escapeHtml(data.product.brand || "Unspecified")}</div>
        </div>
      </div>
    </div>

    <!-- Source Overview -->
    <div class="section">
      <div class="section-title">Source Overview</div>
      <table class="source-table">
        <thead>
          <tr>
            <th>Source Channel</th>
            <th>Status</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="font-semibold">Instagram</td>
            <td>${formatAvailabilityBadge(data.source_overview.instagram)}</td>
            <td>${escapeHtml(data.source.instagram_url || "Direct Link")}</td>
          </tr>
          <tr>
            <td class="font-semibold">Meta Ad Library</td>
            <td>${formatAvailabilityBadge(data.source_overview.meta_ad)}</td>
            <td>${data.evidence.meta_ad?.advertiser ? `Advertiser: ${escapeHtml(data.evidence.meta_ad.advertiser)} (ID: ${escapeHtml(data.evidence.meta_ad.library_id || "N/A")})` : escapeHtml(data.evidence.meta_ad?.status || "unavailable")}</td>
          </tr>
          <tr>
            <td class="font-semibold">Website Store</td>
            <td>${formatAvailabilityBadge(data.source_overview.website)}</td>
            <td>${escapeHtml(data.source.website_url || "No website attached")}</td>
          </tr>
          <tr>
            <td class="font-semibold">Product Image</td>
            <td>${formatAvailabilityBadge(data.source_overview.product_image)}</td>
            <td>${escapeHtml(data.evidence.product_image.image_count)} image(s) processed</td>
          </tr>
          <tr>
            <td class="font-semibold">Packaging OCR</td>
            <td>${formatAvailabilityBadge(data.source_overview.ocr)}</td>
            <td>${escapeHtml(data.evidence.ocr.status)} (${escapeHtml(data.evidence.ocr.confidence)}% confidence)</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Product & Seller Information -->
    <div class="section">
      <div class="section-title">Product & Seller Information</div>
      <div class="info-list">
        <div class="info-row">
          <span class="info-label">Product Name</span>
          <span class="info-value">${escapeHtml(data.product.name || "Not available")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Brand Name</span>
          <span class="info-value">${escapeHtml(data.product.brand || "Not available")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Category</span>
          <span class="info-value">${escapeHtml(data.product.category || "Not specified")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Listed Price / MRP</span>
          <span class="info-value">${escapeHtml(data.product.price || data.product.mrp || "Not listed")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Seller Account</span>
          <span class="info-value">${escapeHtml(data.seller.username ? `@${data.seller.username}` : data.seller.name || "Not available")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Website Domain</span>
          <span class="info-value">${escapeHtml(data.seller.website || "Not provided")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Contact Details</span>
          <span class="info-value">${escapeHtml(data.seller.contact || "Not available")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Physical Address</span>
          <span class="info-value">${escapeHtml(data.seller.address || "Not verified")}</span>
        </div>
      </div>
    </div>

    <!-- Meta Ad Intelligence -->
    ${rawResult.meta_ad_evidence && rawResult.meta_ad_evidence.status !== "unavailable" ? `
    <div class="section">
      <div class="section-title">📣 Meta Ad Intelligence</div>
      <div class="info-list">
        <div class="info-row">
          <span class="info-label">Ad Library Status</span>
          <span class="info-value">${escapeHtml(rawResult.meta_ad_evidence.status.toUpperCase())}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Advertiser Name</span>
          <span class="info-value">${escapeHtml(rawResult.meta_ad_evidence.advertiserName || "Not available")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Library ID</span>
          <span class="info-value">${escapeHtml(rawResult.meta_ad_evidence.libraryId || "Not available")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Platforms</span>
          <span class="info-value">${escapeHtml(rawResult.meta_ad_evidence.publisherPlatforms?.join(", ") || "Instagram")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Delivery Period</span>
          <span class="info-value">${escapeHtml(rawResult.meta_ad_evidence.deliveryStart ? `${rawResult.meta_ad_evidence.deliveryStart} → ${rawResult.meta_ad_evidence.deliveryEnd || "Active"}` : "Active")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Destination URL</span>
          <span class="info-value">${escapeHtml(rawResult.meta_ad_evidence.destinationUrl || "None")}</span>
        </div>
        <div class="info-row" style="grid-column: 1 / -1;">
          <span class="info-label">Ad Text</span>
          <span class="info-value" style="font-weight: 400; font-size: 13px;">${escapeHtml(rawResult.meta_ad_evidence.adText || "None captured")}</span>
        </div>
      </div>
    </div>
    ` : ""}

    <!-- Ad Claim Analysis -->
    ${rawResult.ad_claim_analysis && (rawResult.ad_claim_analysis.claims_detected.length > 0 || rawResult.ad_claim_analysis.ad_pressure_signals.length > 0) ? `
    <div class="section">
      <div class="section-title">📢 Ad Claim & Pressure Analysis</div>
      <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">⚠️ <em>Advertising signals requiring verification, not proof of fraud.</em></p>
      
      ${rawResult.ad_claim_analysis.claims_detected.length > 0 ? `
      <div style="margin-bottom: 14px;">
        <span class="info-label" style="display:block; margin-bottom:6px;">Claims Detected:</span>
        <div style="display: flex; flex-wrap: wrap; gap: 8px;">
          ${rawResult.ad_claim_analysis.claims_detected.map(c => `<span class="badge badge-neutral" style="font-size:12px; font-weight: 500;">"${escapeHtml(c)}"</span>`).join("")}
        </div>
      </div>
      ` : ""}

      ${rawResult.ad_claim_analysis.ad_pressure_signals.length > 0 ? `
      <div>
        <span class="info-label" style="display:block; margin-bottom:6px;">Pressure / Promotional Patterns:</span>
        ${rawResult.ad_claim_analysis.ad_pressure_signals.map(sig => `
          <div class="signal-item signal-risk-medium" style="margin-bottom: 6px; padding: 8px 12px;">
            <div class="signal-title" style="font-size: 13px;">⚠️ ${escapeHtml(sig.type.replace(/_/g, " ").toUpperCase())}: "${escapeHtml(sig.text)}"</div>
            <div class="signal-sources" style="font-size: 11px;">${escapeHtml(sig.meaning)}</div>
          </div>
        `).join("")}
      </div>
      ` : ""}
    </div>
    ` : ""}

    <!-- Packaging Evidence -->
    ${packaging ? `
    <div class="section">
      <div class="section-title">Packaging Evidence (OCR Extraction)</div>
      <div class="info-list">
        <div class="info-row">
          <span class="info-label">Visible Brand</span>
          <span class="info-value">${escapeHtml(packaging.product.brand || "Not visible")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Visible Product</span>
          <span class="info-value">${escapeHtml(packaging.product.name || "Not visible")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Manufacturer Name</span>
          <span class="info-value">${escapeHtml(packaging.manufacturer.name || "Not detected")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Printed MRP</span>
          <span class="info-value">${escapeHtml(packaging.product.mrp || "Not visible")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Licenses / Certifications</span>
          <span class="info-value">${escapeHtml(packaging.regulatory.license_numbers.concat(packaging.regulatory.certifications).join(", ") || "None extracted")}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Dates (Mfg / Exp)</span>
          <span class="info-value">${escapeHtml([packaging.dates.manufactured ? `Mfg: ${packaging.dates.manufactured}` : null, packaging.dates.expiry ? `Exp: ${packaging.dates.expiry}` : null].filter(Boolean).join(" | ") || "Not visible")}</span>
        </div>
        <div class="info-row" style="grid-column: 1 / -1;">
          <span class="info-label">Packaging Claims</span>
          <span class="info-value">${escapeHtml(packaging.claims.join(", ") || "None extracted")}</span>
        </div>
      </div>
    </div>
    ` : ""}

    <!-- Cross-Source Consistency -->
    <div class="section">
      <div class="section-title">Cross-Source Consistency Matrix</div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Instagram</th>
            <th>Meta Ad</th>
            <th>Website</th>
            <th>Product Image</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          ${matrixRows}
        </tbody>
      </table>
    </div>

    <!-- Trust Signals -->
    <div class="section">
      <div class="section-title">Trust Signals</div>
      ${trustSignalsHtml}
    </div>

    <!-- Risk Signals -->
    <div class="section">
      <div class="section-title">Risk Signals</div>
      ${riskSignalsHtml}
    </div>

    <!-- Missing Information -->
    <div class="section">
      <div class="section-title">Missing Information</div>
      <ul class="missing-list">
        ${missingInfoHtml}
      </ul>
    </div>

    <!-- Evidence Traceability -->
    <div class="section">
      <div class="section-title">Evidence Traceability</div>
      ${traceableHtml}
    </div>

    <!-- Recommendation -->
    <div class="section">
      <div class="section-title">Recommendation</div>
      <p style="font-size: 15px; font-weight: 500; color: #1e293b;">${escapeHtml(data.recommendation)}</p>
    </div>

    <!-- Disclaimer -->
    <div class="section">
      <div class="disclaimer-box">
        ⚖️ <strong>Disclaimer:</strong> ${escapeHtml(data.disclaimer)}
      </div>
    </div>
  </div>
</body>
</html>`;
}

/**
 * Generates a verification report file and returns the file path and metadata.
 */
export function generateVerificationReport(
  result: VerificationResult,
  outputDir = path.resolve(process.cwd(), "reports"),
): GeneratedReport {
  const data = buildReportData(result);
  const html = buildReportHtml(data, result);

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const sanitizedId = data.report_id.replace(/[^a-zA-Z0-9_-]/g, "");
  const fileName = `verification-${sanitizedId}.html`;
  const filePath = path.join(outputDir, fileName);

  fs.writeFileSync(filePath, html, "utf-8");

  return {
    report_id: data.report_id,
    file_path: filePath,
    html,
    data,
  };
}
