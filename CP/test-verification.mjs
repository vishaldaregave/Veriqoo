import test from "node:test";
import assert from "node:assert/strict";

import {
  parseInstagramUrl,
  extractInstagramUrl,
  extractProductAndSeller,
  collectWebsiteEvidence,
  downloadMedia,
  extractPackagingInfo,
  compareInstagramAndWebsite,
  compareImageWithInstagramAndWebsite,
  normalizeEvidence,
  buildTrustMatrix,
  evaluateRisk,
  formatVerificationResult,
  generateVerificationReport,
  buildReportHtml,
  buildReportData,
  escapeHtml,
  collectMetaAdEvidence,
  analyzeAdClaims,
} from "./agent/verification/index.ts";
import * as fs from "node:fs";
import * as path from "node:path";

test("parseInstagramUrl extracts clean canonical URL and shortcode", () => {
  const reel = parseInstagramUrl("https://www.instagram.com/reel/C8XYZ123/?igsh=token123");
  assert.equal(reel.canonicalUrl, "https://www.instagram.com/reel/C8XYZ123/");
  assert.equal(reel.type, "reel");
  assert.equal(reel.shortcode, "C8XYZ123");

  const post = parseInstagramUrl("https://instagram.com/p/ABC999/");
  assert.equal(post.canonicalUrl, "https://www.instagram.com/p/ABC999/");
  assert.equal(post.type, "post");
  assert.equal(post.shortcode, "ABC999");
});

test("extractInstagramUrl extracts Instagram URLs embedded in text", () => {
  assert.equal(
    extractInstagramUrl("Hey check this out https://www.instagram.com/reel/ABC123/ please"),
    "https://www.instagram.com/reel/ABC123/",
  );
  assert.equal(
    extractInstagramUrl("Visit https://example.com/?next=instagram.com"),
    null,
  );
});

test("collectWebsiteEvidence handles null and empty URLs gracefully", async () => {
  const res = await collectWebsiteEvidence(null);
  assert.equal(res.status, "not_found");
  assert.equal(res.domain, "");
  assert.ok(res.missing_information.length > 0);
});

test("downloadMedia handles null or invalid URLs gracefully", async () => {
  const res = await downloadMedia("invalid-url");
  assert.equal(res, null);
});

test("extractPackagingInfo parses OCR text into structured product & regulatory facts", () => {
  const ocrSample = `
    ABC NUTRITION
    100% WHEY PROTEIN POWDER
    Net Weight: 2kg
    Mfd by: ABC Health Supplements Pvt Ltd
    Plot 45, Industrial Area, Mumbai
    FSSAI Lic No: 11521018000234
    ISO 22000:2018 Certified
    GMP Certified
    100% Organic
    Sugar Free
    MRP: Rs. 3,499 (Incl. of all taxes)
    Mfg: 01/2026
    Exp: 12/2027
    Care: support@abchealth.com, +91 9876543210
    Website: www.abchealth.com
  `;

  const packaging = extractPackagingInfo(ocrSample, "product_image_1");

  assert.equal(packaging.product.brand, "ABC NUTRITION");
  assert.equal(packaging.product.name, "100% WHEY PROTEIN POWDER");
  assert.ok(packaging.product.mrp?.includes("3,499"));
  assert.equal(packaging.manufacturer.name, "ABC Health Supplements Pvt Ltd");
  assert.ok(packaging.regulatory.license_numbers.some((l) => l.includes("11521018000234")));
  assert.ok(packaging.regulatory.certifications.some((c) => c.includes("ISO 22000")));
  assert.ok(packaging.regulatory.certifications.some((c) => c.includes("GMP Certified")));
  assert.equal(packaging.dates.manufactured, "01/2026");
  assert.equal(packaging.dates.expiry, "12/2027");
  assert.ok(packaging.claims.includes("Sugar Free"));
  assert.ok(packaging.websites.includes("www.abchealth.com"));
  assert.ok(packaging.contact_information.includes("support@abchealth.com"));

  assert.ok(packaging.facts.length >= 5);
  assert.equal(packaging.facts[0].source, "product_image_1");
  assert.equal(packaging.facts[0].method, "OCR");
});

test("compareImageWithInstagramAndWebsite performs cross-checks correctly", () => {
  const sampleEvidence = {
    source: { platform: "instagram", url: "https://www.instagram.com/p/123/" },
    account: { username: "abc_nutrition", display_name: "ABC Nutrition" },
    post: { type: "post", caption: "100% Whey Protein Powder for Rs. 3499. Visit https://abchealth.com", timestamp: null },
    product: { name: "100% Whey Protein Powder", brand: "ABC Nutrition", price: "Rs. 3499", category: "Nutrition" },
    seller: { name: "ABC Nutrition", username: "abc_nutrition", website: "https://abchealth.com", contact: null },
    claims: [],
    media: [{ type: "image", url: "https://instagram.com/p/123/media.jpg", source: "instagram" }],
    external_links: ["https://abchealth.com"],
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const packagingSample = {
    product: { name: "100% Whey Protein Powder", brand: "ABC Nutrition", category: null, price: "Rs. 3499", mrp: "Rs. 3499" },
    manufacturer: { name: "ABC Health Supplements", address: null, contact: null },
    regulatory: { license_numbers: ["FSSAI Lic: 11521018000234"], certifications: ["GMP Certified"] },
    dates: { manufactured: "01/2026", expiry: "12/2027", best_before: null },
    claims: ["Sugar Free"],
    websites: ["abchealth.com"],
    contact_information: ["support@abchealth.com"],
    facts: [],
  };

  const websiteSample = {
    url: "https://abchealth.com",
    domain: "abchealth.com",
    status: "accessible",
    company: { name: "ABC Health Supplements", email: "support@abchealth.com", phone: "+919876543210", address: null },
    product: { name: "100% Whey Protein Powder", brand: "ABC Nutrition", price: "Rs. 3499", description: "Pure whey protein" },
    policies: { refund: true, return: true, shipping: true, privacy: true, terms: true },
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const crossCheck = compareImageWithInstagramAndWebsite(
    packagingSample,
    sampleEvidence,
    sampleEvidence.product,
    sampleEvidence.seller,
    websiteSample,
  );

  assert.equal(crossCheck.image_vs_instagram.brand, "MATCH");
  assert.equal(crossCheck.image_vs_instagram.product, "MATCH");
  assert.equal(crossCheck.image_vs_instagram.price, "MATCH");
  assert.equal(crossCheck.image_vs_website.brand, "MATCH");
  assert.equal(crossCheck.image_vs_website.product, "MATCH");
  assert.equal(crossCheck.image_vs_website.manufacturer, "MATCH");
  assert.equal(crossCheck.image_vs_website.contact, "MATCH");
});

test("formatVerificationResult generates complete Feature 4 layout", () => {
  const result = {
    evidence: {
      source: { platform: "instagram", url: "https://www.instagram.com/p/123/" },
      account: { username: "abc_nutrition", display_name: "ABC Nutrition" },
      post: { type: "post", caption: "ABC Protein Powder", timestamp: null },
      product: { name: "ABC Protein Powder", brand: "ABC", price: "$49.99", category: null },
      seller: { name: "ABC Nutrition", username: "abc_nutrition", website: "https://abc.com", contact: null },
      claims: [],
      media: [{ type: "image", url: "https://instagram.com/img.jpg", source: "instagram" }],
      external_links: ["https://abc.com"],
      evidence: [],
      missing_information: [],
      errors: [],
    },
    media_evidence: {
      media: [{ type: "image", url: "https://instagram.com/img.jpg", source: "instagram" }],
      ocr: { text: "ABC Protein Powder MRP $49.99", confidence: 92, status: "success" },
      packaging: {
        product: { name: "ABC Protein Powder", brand: "ABC", category: null, price: "$49.99", mrp: "$49.99" },
        manufacturer: { name: "ABC Labs", address: null, contact: null },
        regulatory: { license_numbers: ["FDA Approved"], certifications: [] },
        dates: { manufactured: null, expiry: null, best_before: null },
        claims: [],
        websites: [],
        contact_information: [],
        facts: [],
      },
      video_analysis: null,
      status: "analyzed",
      evidence: [],
      errors: [],
    },
    website_evidence: {
      url: "https://abc.com",
      domain: "abc.com",
      status: "accessible",
      company: { name: "ABC Labs", email: "help@abc.com", phone: null, address: null },
      product: { name: "ABC Protein Powder", brand: "ABC", price: "$49.99", description: "Pure protein" },
      policies: { refund: true, return: true, shipping: true, privacy: true, terms: true },
      evidence: [],
      missing_information: [],
      errors: [],
    },
    product: { name: "ABC Protein Powder", brand: "ABC", price: "$49.99", category: null },
    seller: { name: "ABC Nutrition", username: "abc_nutrition", website: "https://abc.com", contact: null },
    risk: {
      risk_level: "LOW",
      confidence: 91,
      positive_signals: [
        "Brand matches across all sources",
        "Product name is consistent",
        "Packaging matches website",
        "Seller information is consistent",
      ],
      risk_signals: [],
      missing_information: ["Independent company registration not checked"],
      consistency_checks: [],
      recommendation: "Proceed with normal purchasing precautions.",
      explanation: "The available Instagram, website, and packaging evidence is broadly consistent.",
      evidence_check: {
        instagram: true,
        website: true,
        product_image: true,
        ocr: true,
      },
    },
    status: "EVIDENCE_COLLECTED",
  };

  const formatted = formatVerificationResult(result);
  assert.ok(formatted.includes("🔍 PRODUCT VERIFICATION"));
  assert.ok(formatted.includes("Product:\nABC Protein Powder"));
  assert.ok(formatted.includes("Brand:\nABC"));
  assert.ok(formatted.includes("🟢 RISK: LOW"));
  assert.ok(formatted.includes("Confidence:\n91%"));
  assert.ok(formatted.includes("🔎 EVIDENCE CHECK"));
  assert.ok(formatted.includes("Instagram      ✅"));
  assert.ok(formatted.includes("Website        ✅"));
  assert.ok(formatted.includes("Product Image  ✅"));
  assert.ok(formatted.includes("OCR            ✅"));
  assert.ok(formatted.includes("✅ TRUST SIGNALS"));
  assert.ok(formatted.includes("⚠️ RISK SIGNALS"));
  assert.ok(formatted.includes("• None detected"));
  assert.ok(formatted.includes("❓ MISSING INFORMATION"));
  assert.ok(formatted.includes("💡 WHY?"));
  assert.ok(formatted.includes("RECOMMENDATION"));
});

// =========================================================================
// FEATURE 4 TESTS (TEST 1 to TEST 8)
// =========================================================================

test("TEST 1: All sources match -> LOW risk, High confidence", () => {
  const instagram = {
    source: { platform: "instagram", url: "https://instagram.com/p/test1" },
    account: { username: "abc_nutrition", display_name: "ABC Nutrition" },
    post: { type: "post", caption: "ABC Whey Protein - $50. Visit https://abc.com", timestamp: null },
    product: { name: "ABC Whey Protein", brand: "ABC Nutrition", price: "$50", category: "Supplements" },
    seller: { name: "ABC Nutrition", username: "abc_nutrition", website: "https://abc.com", contact: null },
    claims: [],
    media: [{ type: "image", url: "https://instagram.com/img1.jpg", source: "instagram" }],
    external_links: ["https://abc.com"],
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const website = {
    url: "https://abc.com",
    domain: "abc.com",
    status: "accessible",
    company: { name: "ABC Nutrition", email: "support@abc.com", phone: null, address: null },
    product: { name: "ABC Whey Protein", brand: "ABC Nutrition", price: "$50", description: "Top whey protein" },
    policies: { refund: true, return: true, shipping: true, privacy: true, terms: true },
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const media = {
    media: [{ type: "image", url: "https://instagram.com/img1.jpg", source: "instagram" }],
    ocr: { text: "ABC Nutrition ABC Whey Protein MRP $50 FSSAI 11521018000234", confidence: 95, status: "success" },
    packaging: {
      product: { name: "ABC Whey Protein", brand: "ABC Nutrition", category: "Supplements", price: "$50", mrp: "$50" },
      manufacturer: { name: "ABC Nutrition Pvt Ltd", address: null, contact: null },
      regulatory: { license_numbers: ["FSSAI 11521018000234"], certifications: [] },
      dates: { manufactured: null, expiry: null, best_before: null },
      claims: [],
      websites: ["abc.com"],
      contact_information: [],
      facts: [],
    },
    video_analysis: null,
    status: "analyzed",
    evidence: [],
    errors: [],
  };

  const normalized = normalizeEvidence(instagram, instagram.product, instagram.seller, website, media);
  const matrix = buildTrustMatrix(normalized, instagram, website, media);
  const risk = evaluateRisk(instagram, instagram.product, instagram.seller, [], website, null, media, null, matrix);

  assert.equal(risk.risk_level, "LOW");
  assert.ok(risk.confidence >= 80, `Expected confidence >= 80%, got ${risk.confidence}%`);
  assert.equal(risk.risk_signals.length, 0);
  assert.ok(matrix.fields.brand.result === "MATCH");
  assert.ok(matrix.fields.product_name.result === "MATCH");
});

test("TEST 2: Brand mismatch -> Risk increases, Risk signal explains mismatch", () => {
  const instagram = {
    source: { platform: "instagram", url: "https://instagram.com/p/test2" },
    account: { username: "fake_store", display_name: "Fake Store" },
    post: { type: "post", caption: "Original Nike Air Max Sneakers for sale", timestamp: null },
    product: { name: "Nike Air Max Sneakers", brand: "Nike", price: "$40", category: "Shoes" },
    seller: { name: "Fake Store", username: "fake_store", website: null, contact: null },
    claims: [],
    media: [{ type: "image", url: "https://instagram.com/img2.jpg", source: "instagram" }],
    external_links: [],
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const media = {
    media: [{ type: "image", url: "https://instagram.com/img2.jpg", source: "instagram" }],
    ocr: { text: "Abibas Super Sport Shoes", confidence: 90, status: "success" },
    packaging: {
      product: { name: "Abibas Super Sport", brand: "Abibas", category: "Shoes", price: "$40", mrp: "$40" },
      manufacturer: { name: "Abibas Corp", address: null, contact: null },
      regulatory: { license_numbers: [], certifications: [] },
      dates: { manufactured: null, expiry: null, best_before: null },
      claims: [],
      websites: [],
      contact_information: [],
      facts: [],
    },
    video_analysis: null,
    status: "analyzed",
    evidence: [],
    errors: [],
  };

  const normalized = normalizeEvidence(instagram, instagram.product, instagram.seller, null, media);
  const matrix = buildTrustMatrix(normalized, instagram, null, media);
  const risk = evaluateRisk(instagram, instagram.product, instagram.seller, [], null, null, media, null, matrix);

  assert.equal(matrix.fields.brand.result, "MISMATCH");
  assert.equal(risk.risk_level, "HIGH");
  assert.ok(risk.risk_signals.some((s) => s.toLowerCase().includes("brand mismatch")));
});

test("TEST 3: Product mismatch -> Risk increases", () => {
  const instagram = {
    source: { platform: "instagram", url: "https://instagram.com/p/test3" },
    account: { username: "tech_reseller", display_name: "Tech Reseller" },
    post: { type: "post", caption: "Brand New iPhone 16 Pro Max", timestamp: null },
    product: { name: "iPhone 16 Pro Max", brand: "Apple", price: "$999", category: "Smartphones" },
    seller: { name: "Tech Reseller", username: "tech_reseller", website: "https://techstore.com", contact: null },
    claims: [],
    media: [{ type: "image", url: "https://instagram.com/img3.jpg", source: "instagram" }],
    external_links: ["https://techstore.com"],
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const website = {
    url: "https://techstore.com",
    domain: "techstore.com",
    status: "accessible",
    company: { name: "Tech Store", email: "tech@store.com", phone: null, address: null },
    product: { name: "Wireless Bluetooth Earbuds Pro", brand: "TechStore", price: "$29", description: "Wireless earbuds" },
    policies: { refund: true, return: true, shipping: true, privacy: true, terms: true },
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const normalized = normalizeEvidence(instagram, instagram.product, instagram.seller, website, null);
  const matrix = buildTrustMatrix(normalized, instagram, website, null);
  const risk = evaluateRisk(instagram, instagram.product, instagram.seller, [], website, null, null, null, matrix);

  assert.equal(matrix.fields.product_name.result, "MISMATCH");
  assert.equal(risk.risk_level, "HIGH");
  assert.ok(risk.risk_signals.some((s) => s.toLowerCase().includes("product mismatch")));
});

test("TEST 4: Only Instagram available -> UNKNOWN/LOW confidence", () => {
  const instagram = {
    source: { platform: "instagram", url: "https://instagram.com/p/test4" },
    account: { username: "handmade_crafts", display_name: "Handmade Crafts" },
    post: { type: "post", caption: "Handmade Ceramic Mug - DM to order", timestamp: null },
    product: { name: "Handmade Ceramic Mug", brand: null, price: null, category: "Crafts" },
    seller: { name: "Handmade Crafts", username: "handmade_crafts", website: null, contact: null },
    claims: [],
    media: [],
    external_links: [],
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const normalized = normalizeEvidence(instagram, instagram.product, instagram.seller, null, null);
  const matrix = buildTrustMatrix(normalized, instagram, null, null);
  const risk = evaluateRisk(instagram, instagram.product, instagram.seller, [], null, null, null, null, matrix);

  assert.equal(risk.risk_level, "UNKNOWN");
  assert.ok(risk.confidence <= 35, `Expected confidence <= 35%, got ${risk.confidence}%`);
  assert.equal(risk.risk_signals.length, 0); // Not marked as fraudulent just because single source
});

test("TEST 5: OCR unavailable -> Pipeline still works", () => {
  const instagram = {
    source: { platform: "instagram", url: "https://instagram.com/p/test5" },
    account: { username: "glow_skincare", display_name: "Glow Skincare" },
    post: { type: "post", caption: "Vitamin C Serum. Visit https://glowskin.com", timestamp: null },
    product: { name: "Vitamin C Serum", brand: "Glow Skincare", price: "$25", category: "Skincare" },
    seller: { name: "Glow Skincare", username: "glow_skincare", website: "https://glowskin.com", contact: null },
    claims: [],
    media: [{ type: "image", url: "https://instagram.com/img5.jpg", source: "instagram" }],
    external_links: ["https://glowskin.com"],
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const website = {
    url: "https://glowskin.com",
    domain: "glowskin.com",
    status: "accessible",
    company: { name: "Glow Skincare LLC", email: "info@glowskin.com", phone: null, address: null },
    product: { name: "Vitamin C Serum", brand: "Glow Skincare", price: "$25", description: "Brightening serum" },
    policies: { refund: true, return: true, shipping: true, privacy: true, terms: true },
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const mediaFailedOcr = {
    media: [{ type: "image", url: "https://instagram.com/img5.jpg", source: "instagram" }],
    ocr: null,
    packaging: null,
    video_analysis: null,
    status: "not_available",
    evidence: [],
    errors: ["OCR failed to extract text"],
  };

  const normalized = normalizeEvidence(instagram, instagram.product, instagram.seller, website, mediaFailedOcr);
  const matrix = buildTrustMatrix(normalized, instagram, website, mediaFailedOcr);
  const risk = evaluateRisk(instagram, instagram.product, instagram.seller, [], website, null, mediaFailedOcr, null, matrix);

  assert.equal(risk.risk_level, "LOW");
  assert.ok(matrix.evidence_check.ocr === false);
  assert.ok(matrix.missing_information.some((m) => m.includes("OCR") || m.includes("Packaging")));
  assert.ok(!risk.risk_signals.some((s) => s.toLowerCase().includes("ocr")));
});

test("TEST 6: Website unavailable -> Pipeline still works", () => {
  const instagram = {
    source: { platform: "instagram", url: "https://instagram.com/p/test6" },
    account: { username: "pure_honey", display_name: "Pure Honey Co" },
    post: { type: "post", caption: "Raw Organic Honey 500g", timestamp: null },
    product: { name: "Raw Organic Honey", brand: "Pure Honey Co", price: "$15", category: "Food" },
    seller: { name: "Pure Honey Co", username: "pure_honey", website: null, contact: null },
    claims: [],
    media: [{ type: "image", url: "https://instagram.com/img6.jpg", source: "instagram" }],
    external_links: [],
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const media = {
    media: [{ type: "image", url: "https://instagram.com/img6.jpg", source: "instagram" }],
    ocr: { text: "Pure Honey Co Raw Organic Honey Net Wt 500g FSSAI 1122334455", confidence: 92, status: "success" },
    packaging: {
      product: { name: "Raw Organic Honey", brand: "Pure Honey Co", category: "Food", price: "$15", mrp: "$15" },
      manufacturer: { name: "Pure Honey Farms", address: null, contact: null },
      regulatory: { license_numbers: ["FSSAI 1122334455"], certifications: [] },
      dates: { manufactured: null, expiry: null, best_before: null },
      claims: ["Raw Organic"],
      websites: [],
      contact_information: [],
      facts: [],
    },
    video_analysis: null,
    status: "analyzed",
    evidence: [],
    errors: [],
  };

  const normalized = normalizeEvidence(instagram, instagram.product, instagram.seller, null, media);
  const matrix = buildTrustMatrix(normalized, instagram, null, media);
  const risk = evaluateRisk(instagram, instagram.product, instagram.seller, [], null, null, media, null, matrix);

  assert.equal(risk.risk_level, "LOW");
  assert.ok(matrix.evidence_check.website === false);
  assert.ok(matrix.fields.brand.result === "MATCH");
  assert.ok(matrix.trust_signals.length >= 1);
});

test("TEST 7: No evidence -> UNKNOWN", () => {
  const emptyInstagram = {
    source: { platform: "instagram", url: "https://instagram.com/p/empty" },
    account: { username: null, display_name: null },
    post: { type: null, caption: null, timestamp: null },
    product: { name: null, brand: null, price: null, category: null },
    seller: { name: null, username: null, website: null, contact: null },
    claims: [],
    media: [],
    external_links: [],
    evidence: [],
    missing_information: ["Instagram metadata could not be fetched"],
    errors: ["Private post or invalid URL"],
  };

  const risk = evaluateRisk(emptyInstagram, emptyInstagram.product, emptyInstagram.seller, [], null, null, null, null, null);

  assert.equal(risk.risk_level, "UNKNOWN");
  assert.equal(risk.confidence, 0);
  assert.ok(risk.missing_information.length > 0);
});

test("TEST 8: Multiple positive signals + one missing field -> Missing field does not create a risk signal", () => {
  const instagram = {
    source: { platform: "instagram", url: "https://instagram.com/p/test8" },
    account: { username: "fit_nutrition", display_name: "Fit Nutrition" },
    post: { type: "post", caption: "Fit Nutrition Creatine Monohydrate 250g. Visit https://fitnutrition.com", timestamp: null },
    product: { name: "Creatine Monohydrate", brand: "Fit Nutrition", price: "$20", category: "Supplements" },
    seller: { name: "Fit Nutrition", username: "fit_nutrition", website: "https://fitnutrition.com", contact: null },
    claims: [],
    media: [{ type: "image", url: "https://instagram.com/img8.jpg", source: "instagram" }],
    external_links: ["https://fitnutrition.com"],
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const website = {
    url: "https://fitnutrition.com",
    domain: "fitnutrition.com",
    status: "accessible",
    company: { name: "Fit Nutrition", email: "info@fitnutrition.com", phone: null, address: null },
    product: { name: "Creatine Monohydrate", brand: "Fit Nutrition", price: "$20", description: "Pure creatine" },
    policies: { refund: true, return: true, shipping: true, privacy: true, terms: true },
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const mediaMissingContact = {
    media: [{ type: "image", url: "https://instagram.com/img8.jpg", source: "instagram" }],
    ocr: { text: "Fit Nutrition Creatine Monohydrate 250g", confidence: 90, status: "success" },
    packaging: {
      product: { name: "Creatine Monohydrate", brand: "Fit Nutrition", category: "Supplements", price: "$20", mrp: "$20" },
      manufacturer: { name: null, address: null, contact: null }, // Missing manufacturer & contact
      regulatory: { license_numbers: [], certifications: [] },
      dates: { manufactured: null, expiry: null, best_before: null },
      claims: [],
      websites: [],
      contact_information: [],
      facts: [],
    },
    video_analysis: null,
    status: "analyzed",
    evidence: [],
    errors: [],
  };

  const normalized = normalizeEvidence(instagram, instagram.product, instagram.seller, website, mediaMissingContact);
  const matrix = buildTrustMatrix(normalized, instagram, website, mediaMissingContact);
  const risk = evaluateRisk(instagram, instagram.product, instagram.seller, [], website, null, mediaMissingContact, null, matrix);

  // Missing manufacturer on packaging is MISSING INFO, not RISK SIGNAL
  assert.equal(risk.risk_level, "LOW");
  assert.equal(risk.risk_signals.length, 0);
  assert.ok(matrix.trust_signals.length >= 2);
  assert.ok(matrix.traceable_conclusions.length >= 3);
});

// =========================================================================
// FEATURE 5 TESTS (DETAILED VERIFICATION REPORT)
// =========================================================================

test("FEATURE 5 - TEST 1: Report generation succeeds and creates file", () => {
  const sampleResult = {
    evidence: {
      source: { platform: "instagram", url: "https://instagram.com/p/rep1" },
      account: { username: "official_brand", display_name: "Official Brand" },
      post: { type: "post", caption: "Premium Protein Powder. Visit https://officialbrand.com", timestamp: null },
      product: { name: "Premium Protein Powder", brand: "Official Brand", price: "$60", category: "Nutrition" },
      seller: { name: "Official Brand", username: "official_brand", website: "https://officialbrand.com", contact: "help@brand.com" },
      claims: [],
      media: [{ type: "image", url: "https://instagram.com/img.jpg", source: "instagram" }],
      external_links: ["https://officialbrand.com"],
      evidence: ["Caption found", "Profile verified"],
      missing_information: [],
      errors: [],
    },
    website_evidence: {
      url: "https://officialbrand.com",
      domain: "officialbrand.com",
      status: "accessible",
      company: { name: "Official Brand LLC", email: "help@brand.com", phone: "+1234567890", address: "100 Brand Way" },
      product: { name: "Premium Protein Powder", brand: "Official Brand", price: "$60", description: "Clean whey" },
      policies: { refund: true, return: true, shipping: true, privacy: true, terms: true },
      evidence: [],
      missing_information: [],
      errors: [],
    },
    media_evidence: {
      media: [{ type: "image", url: "https://instagram.com/img.jpg", source: "instagram" }],
      ocr: { text: "Official Brand Premium Protein Powder MRP $60", confidence: 95, status: "success" },
      packaging: {
        product: { name: "Premium Protein Powder", brand: "Official Brand", category: "Nutrition", price: "$60", mrp: "$60" },
        manufacturer: { name: "Official Brand LLC", address: "100 Brand Way", contact: "help@brand.com" },
        regulatory: { license_numbers: ["FDA-12345"], certifications: ["ISO-9001"] },
        dates: { manufactured: "01/2026", expiry: "12/2027", best_before: null },
        claims: ["GMP Certified"],
        websites: ["officialbrand.com"],
        contact_information: ["help@brand.com"],
        facts: [],
      },
      video_analysis: null,
      status: "analyzed",
      evidence: [],
      errors: [],
    },
    product: { name: "Premium Protein Powder", brand: "Official Brand", price: "$60", category: "Nutrition" },
    seller: { name: "Official Brand", username: "official_brand", website: "https://officialbrand.com", contact: "help@brand.com" },
    risk: {
      risk_level: "LOW",
      confidence: 92,
      positive_signals: ["Brand matches across all sources", "Product name is consistent"],
      risk_signals: [],
      missing_information: ["Independent business registration not checked"],
      consistency_checks: [],
      recommendation: "Proceed with normal purchasing precautions.",
      explanation: "All sources are consistent.",
      evidence_check: { instagram: true, website: true, product_image: true, ocr: true },
    },
    trust_matrix: {
      fields: {
        brand: { field: "brand", valuesBySource: { instagram: "Official Brand", website: "Official Brand", product_image: "Official Brand" }, result: "MATCH", explanation: "Brand matches" },
        product_name: { field: "product_name", valuesBySource: { instagram: "Premium Protein Powder", website: "Premium Protein Powder", product_image: "Premium Protein Powder" }, result: "MATCH", explanation: "Product matches" },
      },
      available_sources: ["instagram", "website", "product_image", "seller"],
      evidence_check: { instagram: true, website: true, product_image: true, ocr: true },
      trust_signals: [{ signal: "Brand matches across sources", severity: "positive", sources: ["instagram", "website", "product_image"] }],
      risk_signals: [],
      missing_information: ["Independent business registration not checked"],
      traceable_conclusions: [
        { conclusion: "Brand is consistent", evidence: [{ source: "instagram", value: "Official Brand" }, { source: "website", value: "Official Brand" }] },
      ],
      summary_explanation: "Broadly consistent evidence across all channels.",
    },
    status: "EVIDENCE_COLLECTED",
  };

  const report = generateVerificationReport(sampleResult);
  assert.ok(report.report_id.startsWith("REP-"));
  assert.ok(fs.existsSync(report.file_path));
  assert.ok(report.html.length > 500);
});

test("FEATURE 5 - TEST 2: HTML contains product information", () => {
  const result = {
    product: { name: "Super Vitamin C Serum", brand: "Radiant Skin", price: "$28", category: "Cosmetics" },
    seller: { name: "Radiant Skin", username: "radiant_skin", website: null, contact: null },
    risk: { risk_level: "LOW", confidence: 80, positive_signals: [], risk_signals: [], missing_information: [], consistency_checks: [], recommendation: "OK" },
    evidence: { source: { platform: "instagram", url: "https://instagram.com/p/c1" }, account: { username: "radiant_skin" }, post: { caption: "Vitamin C" }, media: [], external_links: [], evidence: [], missing_information: [], errors: [] },
    status: "EVIDENCE_COLLECTED",
  };
  const data = buildReportData(result);
  const html = buildReportHtml(data, result);

  assert.ok(html.includes("Super Vitamin C Serum"));
  assert.ok(html.includes("Radiant Skin"));
  assert.ok(html.includes("$28"));
  assert.ok(html.includes("Cosmetics"));
});

test("FEATURE 5 - TEST 3: HTML contains risk level", () => {
  const lowResult = {
    product: { name: "Item", brand: "B" },
    seller: {},
    risk: { risk_level: "LOW", confidence: 85, positive_signals: [], risk_signals: [], missing_information: [], consistency_checks: [], recommendation: "Safe" },
    evidence: { source: { platform: "instagram", url: "https://instagram.com/p/1" }, account: {}, post: {}, media: [], external_links: [], evidence: [], missing_information: [], errors: [] },
    status: "EVIDENCE_COLLECTED",
  };
  const data = buildReportData(lowResult);
  const html = buildReportHtml(data, lowResult);
  assert.ok(html.includes("LOW RISK"));

  const highResult = { ...lowResult, risk: { ...lowResult.risk, risk_level: "HIGH" } };
  const dataHigh = buildReportData(highResult);
  const htmlHigh = buildReportHtml(dataHigh, highResult);
  assert.ok(htmlHigh.includes("HIGH RISK"));
});

test("FEATURE 5 - TEST 4: HTML contains confidence score", () => {
  const result = {
    product: { name: "Item", brand: "B" },
    seller: {},
    risk: { risk_level: "MEDIUM", confidence: 73, positive_signals: [], risk_signals: [], missing_information: [], consistency_checks: [], recommendation: "Proceed with caution" },
    evidence: { source: { platform: "instagram", url: "https://instagram.com/p/1" }, account: {}, post: {}, media: [], external_links: [], evidence: [], missing_information: [], errors: [] },
    status: "EVIDENCE_COLLECTED",
  };
  const data = buildReportData(result);
  const html = buildReportHtml(data, result);
  assert.ok(html.includes("73%"));
});

test("FEATURE 5 - TEST 5: HTML contains evidence sections", () => {
  const result = {
    product: { name: "Item", brand: "B" },
    seller: { username: "shop_owner", website: "https://shop.com" },
    risk: { risk_level: "LOW", confidence: 90, positive_signals: [], risk_signals: [], missing_information: [], consistency_checks: [], recommendation: "OK" },
    evidence: { source: { platform: "instagram", url: "https://instagram.com/p/1" }, account: { username: "shop_owner" }, post: { caption: "Caption text" }, media: [{ type: "image", url: "https://img.jpg", source: "instagram" }], external_links: ["https://shop.com"], evidence: [], missing_information: [], errors: [] },
    website_evidence: { url: "https://shop.com", domain: "shop.com", status: "accessible", company: { name: "Shop Inc", email: null, phone: null, address: null }, product: { name: "Item", brand: "B", price: null, description: null }, policies: { refund: true, return: true, shipping: true, privacy: true, terms: true }, evidence: [], missing_information: [], errors: [] },
    status: "EVIDENCE_COLLECTED",
  };
  const data = buildReportData(result);
  const html = buildReportHtml(data, result);

  assert.ok(html.includes("Source Overview"));
  assert.ok(html.includes("Product &amp; Seller Information") || html.includes("Product & Seller Information"));
  assert.ok(html.includes("Cross-Source Consistency Matrix"));
  assert.ok(html.includes("Executive Finding"));
});

test("FEATURE 5 - TEST 6: HTML contains trust signals", () => {
  const result = {
    product: { name: "Item", brand: "B" },
    seller: {},
    risk: { risk_level: "LOW", confidence: 85, positive_signals: [], risk_signals: [], missing_information: [], consistency_checks: [], recommendation: "OK" },
    trust_matrix: {
      fields: {},
      available_sources: ["instagram", "website"],
      evidence_check: { instagram: true, website: true, product_image: false, ocr: false },
      trust_signals: [
        { signal: "Packaging matches website", severity: "positive", sources: ["product_image", "website"] },
        { signal: "Verified FSSAI license", severity: "positive", sources: ["product_image"] },
      ],
      risk_signals: [],
      missing_information: [],
      traceable_conclusions: [],
      summary_explanation: "",
    },
    evidence: { source: { platform: "instagram", url: "https://instagram.com/p/1" }, account: {}, post: {}, media: [], external_links: [], evidence: [], missing_information: [], errors: [] },
    status: "EVIDENCE_COLLECTED",
  };
  const data = buildReportData(result);
  const html = buildReportHtml(data, result);

  assert.ok(html.includes("Packaging matches website"));
  assert.ok(html.includes("Verified FSSAI license"));
  assert.ok(html.includes("Sources: product_image, website"));
});

test("FEATURE 5 - TEST 7: HTML contains risk signals", () => {
  const result = {
    product: { name: "Item", brand: "B" },
    seller: {},
    risk: { risk_level: "HIGH", confidence: 88, positive_signals: [], risk_signals: [], missing_information: [], consistency_checks: [], recommendation: "Avoid" },
    trust_matrix: {
      fields: {},
      available_sources: ["instagram", "website"],
      evidence_check: { instagram: true, website: true, product_image: false, ocr: false },
      trust_signals: [],
      risk_signals: [
        { signal: "Brand mismatch detected between listing and packaging", severity: "high", sources: ["instagram", "product_image"] },
      ],
      missing_information: [],
      traceable_conclusions: [],
      summary_explanation: "",
    },
    evidence: { source: { platform: "instagram", url: "https://instagram.com/p/1" }, account: {}, post: {}, media: [], external_links: [], evidence: [], missing_information: [], errors: [] },
    status: "EVIDENCE_COLLECTED",
  };
  const data = buildReportData(result);
  const html = buildReportHtml(data, result);

  assert.ok(html.includes("Brand mismatch detected between listing and packaging"));
  assert.ok(html.includes("HIGH"));
});

test("FEATURE 5 - TEST 8: HTML contains missing information distinctly", () => {
  const result = {
    product: { name: "Item", brand: "B" },
    seller: {},
    risk: {
      risk_level: "LOW",
      confidence: 70,
      positive_signals: [],
      risk_signals: [],
      missing_information: ["Company registration was not independently verified.", "Packaging OCR was partially obscured."],
      consistency_checks: [],
      recommendation: "OK",
    },
    evidence: { source: { platform: "instagram", url: "https://instagram.com/p/1" }, account: {}, post: {}, media: [], external_links: [], evidence: [], missing_information: [], errors: [] },
    status: "EVIDENCE_COLLECTED",
  };
  const data = buildReportData(result);
  const html = buildReportHtml(data, result);

  assert.ok(html.includes("Missing Information"));
  assert.ok(html.includes("Company registration was not independently verified."));
  assert.ok(html.includes("Packaging OCR was partially obscured."));
});

test("FEATURE 5 - TEST 9: HTML contains traceable conclusions", () => {
  const result = {
    product: { name: "Item", brand: "B" },
    seller: {},
    risk: { risk_level: "LOW", confidence: 90, positive_signals: [], risk_signals: [], missing_information: [], consistency_checks: [], recommendation: "OK" },
    trust_matrix: {
      fields: {},
      available_sources: ["instagram", "website"],
      evidence_check: { instagram: true, website: true, product_image: false, ocr: false },
      trust_signals: [],
      risk_signals: [],
      missing_information: [],
      traceable_conclusions: [
        {
          conclusion: "Brand is consistent across all sources",
          evidence: [
            { source: "instagram", value: "Nike Shoes" },
            { source: "website", value: "Nike Shoes" },
          ],
        },
      ],
      summary_explanation: "",
    },
    evidence: { source: { platform: "instagram", url: "https://instagram.com/p/1" }, account: {}, post: {}, media: [], external_links: [], evidence: [], missing_information: [], errors: [] },
    status: "EVIDENCE_COLLECTED",
  };
  const data = buildReportData(result);
  const html = buildReportHtml(data, result);

  assert.ok(html.includes("Evidence Traceability"));
  assert.ok(html.includes("Brand is consistent across all sources"));
  assert.ok(html.includes("Nike Shoes"));
});

test("FEATURE 5 - TEST 10: Dynamic HTML is properly escaped", () => {
  const maliciousInput = `<script>alert('XSS')</script>" onclick="hack()`;
  const escaped = escapeHtml(maliciousInput);
  assert.ok(!escaped.includes("<script>"));
  assert.ok(escaped.includes("&lt;script&gt;"));
  assert.ok(escaped.includes("&quot;"));

  const result = {
    product: { name: "<img src=x onerror=alert(1)>", brand: "<b>BoldBrand</b>" },
    seller: { username: "seller<script>", name: "Malicious' OR '1'='1" },
    risk: { risk_level: "LOW", confidence: 50, positive_signals: ["<svg onload=alert(2)>"], risk_signals: [], missing_information: [], consistency_checks: [], recommendation: "Safe" },
    evidence: { source: { platform: "instagram", url: "https://instagram.com/<xss>" }, account: {}, post: {}, media: [], external_links: [], evidence: [], missing_information: [], errors: [] },
    status: "EVIDENCE_COLLECTED",
  };
  const data = buildReportData(result);
  const html = buildReportHtml(data, result);

  assert.ok(!html.includes("<img src=x onerror=alert(1)>"));
  assert.ok(!html.includes("<script>"));
  assert.ok(!html.includes("<svg onload=alert(2)>"));
  assert.ok(html.includes("&lt;img src=x onerror=alert(1)&gt;"));
});

test("FEATURE 5 - TEST 11: Missing evidence does not crash report generation", () => {
  const resultWithoutWebsiteOrMedia = {
    product: { name: "Handmade Mug", brand: null, price: null, category: null },
    seller: { name: null, username: "craft_maker", website: null, contact: null },
    risk: { risk_level: "UNKNOWN", confidence: 25, positive_signals: [], risk_signals: [], missing_information: ["No website"], consistency_checks: [], recommendation: "Verify" },
    evidence: { source: { platform: "instagram", url: "https://instagram.com/p/test" }, account: { username: "craft_maker" }, post: { caption: "My mug" }, media: [], external_links: [], evidence: [], missing_information: [], errors: [] },
    website_evidence: null,
    media_evidence: null,
    status: "EVIDENCE_COLLECTED",
  };

  const report = generateVerificationReport(resultWithoutWebsiteOrMedia);
  assert.ok(report.html.includes("Handmade Mug"));
  assert.ok(report.html.includes("UNAVAILABLE"));
});

test("FEATURE 5 - TEST 12: Empty VerificationResult is handled safely", () => {
  const emptyResult = {
    product: { name: null, brand: null, price: null, category: null },
    seller: { name: null, username: null, website: null, contact: null },
    risk: { risk_level: "UNKNOWN", confidence: 0, positive_signals: [], risk_signals: [], missing_information: ["No data"], consistency_checks: [], recommendation: "Unable to verify" },
    evidence: { source: { platform: "instagram", url: "" }, account: { username: null, display_name: null }, post: { type: null, caption: null, timestamp: null }, media: [], external_links: [], evidence: [], missing_information: [], errors: [] },
    status: "INSUFFICIENT_EVIDENCE",
  };

  const report = generateVerificationReport(emptyResult);
  assert.ok(report.html.includes("UNKNOWN RISK"));
  assert.ok(report.html.includes("Not available") || report.html.includes("Unspecified"));
});

// ==========================================
// META AD INTELLIGENCE & AD CLAIM TESTS
// ==========================================

test("META TEST 1: Missing Meta token returns status 'unavailable'", async () => {
  const originalToken = process.env.META_AD_LIBRARY_ACCESS_TOKEN;
  delete process.env.META_AD_LIBRARY_ACCESS_TOKEN;
  try {
    const evidence = {
      source: { platform: "instagram", url: "https://instagram.com/p/test" },
      account: { username: "xyzstore" },
      post: { caption: "Shoes for sale" },
      media: [],
      external_links: [],
      evidence: [],
      missing_information: [],
      errors: [],
    };
    const product = { name: "Shoes", brand: "Nike" };
    const seller = { username: "xyzstore" };

    const result = await collectMetaAdEvidence(evidence, product, seller);
    assert.equal(result.status, "unavailable");
    assert.ok(result.error?.includes("No Meta Ad Library access token configured"));
    assert.equal(result.evidenceSource, "Meta Ad Library");
  } finally {
    if (originalToken) {
      process.env.META_AD_LIBRARY_ACCESS_TOKEN = originalToken;
    }
  }
});

test("META TEST 2: Meta API unavailable or invalid token handled gracefully", async () => {
  process.env.META_AD_LIBRARY_ACCESS_TOKEN = "EAAB_TEST_INVALID_TOKEN";
  try {
    const evidence = {
      source: { platform: "instagram", url: "https://instagram.com/p/test" },
      account: { username: "xyzstore" },
      post: { caption: "Shoes for sale" },
      media: [],
      external_links: [],
      evidence: [],
      missing_information: [],
      errors: [],
    };
    const product = { name: "Shoes", brand: "Nike" };
    const seller = { username: "xyzstore" };

    const result = await collectMetaAdEvidence(evidence, product, seller);
    // Invalid token against real Graph API returns unavailable with error
    assert.ok(["unavailable", "not_found"].includes(result.status));
    assert.equal(result.evidenceSource, "Meta Ad Library");
  } finally {
    delete process.env.META_AD_LIBRARY_ACCESS_TOKEN;
  }
});

test("META TEST 3: Ad Claim Analyzer extracts extreme discounts (e.g. 90% OFF)", () => {
  const text = "Get flat 90% OFF on all Nike items today!";
  const analysis = analyzeAdClaims(text, "meta_ad");

  assert.ok(analysis.claims_detected.some((c) => c.includes("90% OFF")));
  assert.ok(analysis.ad_pressure_signals.some((s) => s.type === "extreme_discount"));
  assert.equal(analysis.ad_pressure_signals[0].source, "meta_ad");
});

test("META TEST 4: Ad Claim Analyzer extracts urgency claims", () => {
  const text = "Special sale ending tonight! Last chance to buy.";
  const analysis = analyzeAdClaims(text, "instagram");

  assert.ok(analysis.claims_detected.some((c) => /ending tonight|last chance/i.test(c)));
  assert.ok(analysis.ad_pressure_signals.some((s) => s.type === "urgency"));
});

test("META TEST 5: Ad Claim Analyzer extracts scarcity claims", () => {
  const text = "Hurry! Only 3 left in stock! Limited quantity available.";
  const analysis = analyzeAdClaims(text, "meta_ad");

  assert.ok(analysis.claims_detected.some((c) => /only 3 left|limited/i.test(c)));
  assert.ok(analysis.ad_pressure_signals.some((s) => s.type === "scarcity"));
});

test("META TEST 6: Ad Claim Analyzer extracts authenticity claims", () => {
  const text = "100% original imported shoes with genuine leather guarantee!";
  const analysis = analyzeAdClaims(text, "meta_ad");

  assert.ok(analysis.claims_detected.some((c) => /100% original|genuine/i.test(c)));
  assert.ok(analysis.ad_pressure_signals.some((s) => s.type === "authenticity_claim"));
});

test("META TEST 7: Ad Claim Analyzer extracts certification and authority claims", () => {
  const text = "FDA approved and ISO certified formula. Doctor recommended.";
  const analysis = analyzeAdClaims(text, "meta_ad");

  assert.ok(analysis.claims_detected.some((c) => /FDA approved|ISO certified|Doctor recommended/i.test(c)));
  assert.ok(analysis.ad_pressure_signals.some((s) => s.type === "authority_certification"));
});

test("META TEST 8: Ad Claim Analyzer extracts multi-buy and price anchoring claims", () => {
  const text = "Mega offer: Buy 1 Get 3 Free! MRP ₹10,000 now only ₹499.";
  const analysis = analyzeAdClaims(text, "meta_ad");

  assert.ok(analysis.claims_detected.some((c) => /buy 1 get 3|mrp.*499/i.test(c)));
  assert.ok(analysis.ad_pressure_signals.some((s) => s.type === "extreme_discount" || s.type === "price_anchoring"));
});

test("META TEST 9: Advertiser match adds positive consistency signal", () => {
  const normalized = {
    product_name: [{ source: "instagram", value: "Smart Watch" }],
    brand: [{ source: "instagram", value: "FitBrand" }],
    seller: [{ source: "instagram", value: "fitbrand_official" }, { source: "meta_ad", value: "FitBrand Official" }],
    price: [],
    manufacturer: [],
    website: [],
    contact: [],
    claims: [],
    license_certification: [],
    product_category: [],
  };
  const evidence = {
    source: { platform: "instagram", url: "https://instagram.com/p/1" },
    account: { username: "fitbrand_official", display_name: "FitBrand Official" },
    post: { caption: "Smart Watch" },
    media: [],
    external_links: [],
    evidence: [],
    missing_information: [],
    errors: [],
  };
  const metaAd = {
    status: "found",
    libraryId: "123456",
    advertiserName: "FitBrand Official",
    evidenceSource: "Meta Ad Library",
  };

  const matrix = buildTrustMatrix(normalized, evidence, null, null, metaAd);
  assert.ok(matrix.trust_signals.some((s) => s.signal.includes("Meta Ad advertiser identity aligns with Instagram seller")));
});

test("META TEST 10: Advertiser mismatch with website flags risk signal", () => {
  const normalized = {
    product_name: [],
    brand: [],
    seller: [{ source: "meta_ad", value: "XYZ Global Marketing" }, { source: "website", value: "ABC Logistics Pvt Ltd" }],
    price: [],
    manufacturer: [],
    website: [],
    contact: [],
    claims: [],
    license_certification: [],
    product_category: [],
  };
  const evidence = {
    source: { platform: "instagram", url: "https://instagram.com/p/1" },
    account: { username: "random_store" },
    post: { caption: "Sale" },
    media: [],
    external_links: ["https://abclogistics.in"],
    evidence: [],
    missing_information: [],
    errors: [],
  };
  const website = {
    status: "accessible",
    domain: "abclogistics.in",
    url: "https://abclogistics.in",
    company: { name: "ABC Logistics Pvt Ltd" },
    product: { name: null, brand: null, price: null },
    contact: {},
    policies: { refund: true, return: true, shipping: true, privacy: true, terms: true },
    social_links: {},
    evidence: [],
    missing_information: [],
    errors: [],
  };
  const metaAd = {
    status: "found",
    libraryId: "987654",
    advertiserName: "XYZ Global Marketing",
    evidenceSource: "Meta Ad Library",
  };

  const matrix = buildTrustMatrix(normalized, evidence, website, null, metaAd);
  assert.ok(matrix.risk_signals.some((s) => s.signal.includes("Meta advertiser and external website business identities are inconsistent")));
});

test("META TEST 11: Pack size / quantity contradiction detected", () => {
  const normalized = {
    product_name: [],
    brand: [],
    seller: [],
    price: [],
    manufacturer: [],
    website: [],
    contact: [],
    claims: [{ source: "meta_ad", value: "Somat 80 tablets ₹499" }],
    license_certification: [],
    product_category: [],
  };
  const evidence = {
    source: { platform: "instagram", url: "https://instagram.com/p/1" },
    account: { username: "somat_seller" },
    post: { caption: "Somat 80 tablets ₹499" },
    media: [],
    external_links: [],
    evidence: [],
    missing_information: [],
    errors: [],
  };
  const media = {
    status: "analyzed",
    media: [],
    ocr: { status: "success", text: "Somat Dishwasher 40 tablets pack", confidence: 90, words: [] },
    packaging: {
      product: { name: "Somat Dishwasher", brand: "Somat", price: null, mrp: null, net_quantity: "40 tablets", category: null },
      manufacturer: { name: null, address: null },
      regulatory: { license_numbers: [], certifications: [] },
      dates: { manufactured: null, expiry: null, best_before: null },
      claims: ["40 tablets"],
      contact_information: [],
      websites: [],
      facts: [],
    },
    video_analysis: null,
    evidence: [],
    errors: [],
  };
  const metaAd = {
    status: "found",
    adText: "Somat 80 tablets ₹499",
    evidenceSource: "Meta Ad Library",
  };

  const matrix = buildTrustMatrix(normalized, evidence, null, media, metaAd);
  assert.ok(matrix.risk_signals.some((s) => s.signal.includes("Pack size / quantity contradiction")));
});

test("META TEST 12: Multiple aggressive ad pressure signals generate risk warning", () => {
  const adClaims = {
    claims_detected: ["90% OFF", "TODAY ONLY", "ONLY 2 LEFT", "100% ORIGINAL GUARANTEED"],
    ad_pressure_signals: [
      { type: "extreme_discount", text: "90% OFF", source: "meta_ad", meaning: "Unusually large discount claim" },
      { type: "urgency", text: "TODAY ONLY", source: "meta_ad", meaning: "Urgency language" },
      { type: "scarcity", text: "ONLY 2 LEFT", source: "meta_ad", meaning: "Scarcity language" },
    ],
  };

  const normalized = {
    product_name: [],
    brand: [],
    seller: [],
    price: [],
    manufacturer: [],
    website: [],
    contact: [],
    claims: [],
    license_certification: [],
    product_category: [],
  };
  const evidence = {
    source: { platform: "instagram", url: "https://instagram.com/p/1" },
    account: { username: "deal_hunter" },
    post: { caption: "Deal" },
    media: [],
    external_links: [],
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const matrix = buildTrustMatrix(normalized, evidence, null, null, null, adClaims);
  assert.ok(matrix.risk_signals.some((s) => s.signal.includes("Multiple unverified high-pressure advertising patterns")));
});

test("META TEST 13: Meta evidence presence does NOT automatically make risk LOW", () => {
  const evidence = {
    source: { platform: "instagram", url: "https://instagram.com/p/1" },
    account: { username: "unknown_seller" },
    post: { caption: "Buy now" },
    media: [],
    external_links: [],
    evidence: [],
    missing_information: ["No external website"],
    errors: [],
  };
  const product = { name: "Mystery Gadget", brand: null };
  const seller = { username: "unknown_seller" };
  const metaAd = {
    status: "found",
    libraryId: "12345",
    advertiserName: "Random LLC",
    evidenceSource: "Meta Ad Library",
  };

  const risk = evaluateRisk(evidence, product, seller, [], null, null, null, null, null, metaAd);
  // Absence of independent website or product proof should NOT force LOW risk just because Meta Ad exists
  assert.notEqual(risk.risk_level, "LOW");
});

test("META TEST 14: Meta absence does NOT automatically mark HIGH risk", () => {
  const evidence = {
    source: { platform: "instagram", url: "https://instagram.com/p/1" },
    account: { username: "handmade_pottery" },
    post: { caption: "Handmade clay pots" },
    media: [],
    external_links: [],
    evidence: [],
    missing_information: [],
    errors: [],
  };
  const product = { name: "Handmade Clay Pot", brand: "Artisan Pots" };
  const seller = { username: "handmade_pottery" };
  const metaAd = {
    status: "not_found",
    evidenceSource: "Meta Ad Library",
  };

  const risk = evaluateRisk(evidence, product, seller, [], null, null, null, null, null, metaAd);
  // Organic/non-ad posts shouldn't be high risk simply because they don't run paid ads
  assert.notEqual(risk.risk_level, "HIGH");
});

test("META TEST 15: Formatter includes Meta Ad intelligence & Claim sections when present", () => {
  const result = {
    product: { name: "Nike Air Max", brand: "Nike", price: "₹1,499" },
    seller: { username: "nikedeals_in", name: "Nike Deals India" },
    risk: {
      risk_level: "MEDIUM",
      confidence: 65,
      positive_signals: [],
      risk_signals: ["Unusually low price compared to authentic market rate"],
      missing_information: ["No website provided"],
      consistency_checks: [],
      recommendation: "Check authenticity before payment",
    },
    meta_ad_evidence: {
      status: "found",
      libraryId: "777888",
      advertiserName: "Nike Deals India",
      publisherPlatforms: ["instagram", "facebook"],
      deliveryStart: "2026-09-20",
      deliveryEnd: "Active",
      adText: "Original Nike Shoes ₹1,499. Today Only! 90% OFF.",
      evidenceSource: "Meta Ad Library",
    },
    ad_claim_analysis: {
      claims_detected: ["₹1,499", "90% OFF", "Today Only", "Original"],
      ad_pressure_signals: [
        { type: "extreme_discount", text: "90% OFF", source: "meta_ad", meaning: "Unusually large discount" },
        { type: "urgency", text: "Today Only", source: "meta_ad", meaning: "Urgency language" },
      ],
    },
    evidence: {
      source: { platform: "instagram", url: "https://instagram.com/p/nike1" },
      account: { username: "nikedeals_in" },
      post: { caption: "Original Nike Shoes ₹1,499" },
      media: [],
      external_links: [],
      evidence: [],
      missing_information: [],
      errors: [],
    },
    status: "EVIDENCE_COLLECTED",
  };

  const formatted = formatVerificationResult(result);
  assert.ok(formatted.includes("META AD INTELLIGENCE"));
  assert.ok(formatted.includes("Nike Deals India"));
  assert.ok(formatted.includes("777888"));
  assert.ok(formatted.includes("AD CLAIM ANALYSIS"));
  assert.ok(formatted.includes("90% OFF"));
  assert.ok(formatted.includes("Meta Ad        ✅"));
});

test("META TEST 16: HTML report includes Meta Ad section and provenance", () => {
  const result = {
    product: { name: "Nike Shoes", brand: "Nike" },
    seller: { username: "nikedeals" },
    risk: { risk_level: "MEDIUM", confidence: 60, positive_signals: [], risk_signals: [], missing_information: [], consistency_checks: [], recommendation: "Verify" },
    meta_ad_evidence: {
      status: "found",
      libraryId: "LIB-999",
      advertiserName: "Global Shoes Co",
      publisherPlatforms: ["instagram"],
      adText: "Buy 1 Get 3 Free Nike shoes",
      evidenceSource: "Meta Ad Library",
    },
    ad_claim_analysis: {
      claims_detected: ["Buy 1 Get 3 Free"],
      ad_pressure_signals: [
        { type: "extreme_discount", text: "Buy 1 Get 3 Free", source: "meta_ad", meaning: "High pressure discount" },
      ],
    },
    evidence: { source: { platform: "instagram", url: "https://instagram.com/p/1" }, account: {}, post: {}, media: [], external_links: [], evidence: [], missing_information: [], errors: [] },
    status: "EVIDENCE_COLLECTED",
  };

  const data = buildReportData(result);
  const html = buildReportHtml(data, result);

  assert.ok(html.includes("Meta Ad Intelligence"));
  assert.ok(html.includes("Global Shoes Co"));
  assert.ok(html.includes("LIB-999"));
  assert.ok(html.includes("Ad Claim &amp; Pressure Analysis") || html.includes("Ad Claim & Pressure Analysis"));
  assert.ok(html.includes("Buy 1 Get 3 Free"));
});

test("META TEST 17: No fabricated Meta data returned", () => {
  const metaAd = {
    status: "not_found",
    evidenceSource: "Meta Ad Library",
  };
  assert.equal(metaAd.libraryId, undefined);
  assert.equal(metaAd.advertiserName, undefined);
  assert.equal(metaAd.adText, undefined);
});

test("META TEST 18: Meta failure does not break orchestrator normalization or report", () => {
  const failedResult = {
    product: { name: "Handmade Shirt", brand: "LocalBrand" },
    seller: { username: "local_artisan" },
    risk: { risk_level: "LOW", confidence: 75, positive_signals: [], risk_signals: [], missing_information: [], consistency_checks: [], recommendation: "Safe" },
    meta_ad_evidence: {
      status: "unavailable",
      error: "Timeout contacting Meta Graph API",
      evidenceSource: "Meta Ad Library",
    },
    evidence: { source: { platform: "instagram", url: "https://instagram.com/p/1" }, account: {}, post: {}, media: [], external_links: [], evidence: [], missing_information: [], errors: [] },
    status: "EVIDENCE_COLLECTED",
  };

  const data = buildReportData(failedResult);
  const html = buildReportHtml(data, failedResult);
  assert.ok(html.includes("Handmade Shirt"));
  assert.ok(!html.includes("LIB-"));
});
