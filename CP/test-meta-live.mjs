import { collectMetaAdEvidence } from "./agent/verification/metaAdEvidence.ts";
import { analyzeAdClaims } from "./agent/verification/adClaimAnalyzer.ts";

async function run() {
  console.log("==========================================");
  console.log("   LIVE META AD LIBRARY & COMPLIANCE TEST ");
  console.log("==========================================\n");

  const queryBrand = process.argv[2] || "boAt Lifestyle";
  const token = process.env.META_AD_LIBRARY_ACCESS_TOKEN;
  console.log(`Searching Meta Ad Library for: "${queryBrand}"`);
  console.log(`Country: ${process.env.META_AD_LIBRARY_COUNTRY || "IN"}`);
  console.log("Contacting Meta Graph API...\n");

  try {
    const rawCheckUrl = `https://graph.facebook.com/v20.0/ads_archive?access_token=${token}&ad_reached_countries=["IN"]&ad_type=ALL&search_terms=Nike&limit=1`;
    const checkRes = await fetch(rawCheckUrl);
    const checkJson = await checkRes.json();
    if (!checkRes.ok) {
      console.log("Meta API Response Diagnostic:", JSON.stringify(checkJson, null, 2));
    }
  } catch (diagErr) {
    console.error("Diagnostic error:", diagErr);
  }

  const mockEvidence = {
    source: { platform: "instagram", url: "https://www.instagram.com/reel/example" },
    account: { username: queryBrand.toLowerCase().replace(/\s+/g, ""), display_name: queryBrand },
    post: { type: "reel", caption: "Check out our latest product", timestamp: null },
    product: { name: "Headphones", brand: queryBrand, price: "₹1,499", category: "Electronics" },
    seller: { name: queryBrand, username: queryBrand.toLowerCase().replace(/\s+/g, ""), website: null, contact: null },
    claims: [],
    media: [],
    external_links: [],
    evidence: [],
    missing_information: [],
    errors: [],
  };

  const adEvidence = await collectMetaAdEvidence(mockEvidence, mockEvidence.product, mockEvidence.seller);

  if (adEvidence.status === "found") {
    console.log("✅ META AD FOUND!");
    console.log(`• Advertiser Name : ${adEvidence.advertiserName || "N/A"}`);
    console.log(`• Ad Library ID   : ${adEvidence.libraryId || "N/A"}`);
    console.log(`• Delivery Status : ${adEvidence.deliveryStart} → ${adEvidence.deliveryEnd || "Active"}`);
    console.log(`• Platforms       : ${adEvidence.publisherPlatforms?.join(", ") || "Instagram"}`);
    console.log(`• Destination URL : ${adEvidence.destinationUrl || "N/A"}`);
    console.log(`• Ad Snapshot URL : ${adEvidence.adSnapshotUrl || "N/A"}`);
    console.log(`\n--- Ad Copy (Excerpt) ---`);
    console.log(adEvidence.adText ? `"${adEvidence.adText.slice(0, 300)}..."` : "(No text body)");

    console.log("\n==========================================");
    console.log("   AUTOMATED COMPLIANCE & PRESSURE AUDIT  ");
    console.log("==========================================");

    const compliance = analyzeAdClaims(adEvidence.adText || "", "meta_ad");
    console.log(`Claims Detected       : ${compliance.claims_detected.length}`);
    console.log(`Compliance Risk Signals: ${compliance.ad_pressure_signals.length}\n`);

    if (compliance.price_claims.length > 0) {
      console.log(`💰 Price & Discount Claims: ${compliance.price_claims.join(", ")}`);
    }
    if (compliance.urgency_claims.length > 0) {
      console.log(`⏳ Urgency Signals: ${compliance.urgency_claims.join(", ")}`);
    }
    if (compliance.scarcity_claims.length > 0) {
      console.log(`📦 Scarcity Signals: ${compliance.scarcity_claims.join(", ")}`);
    }
    if (compliance.authenticity_claims.length > 0) {
      console.log(`🛡️ Authenticity Claims: ${compliance.authenticity_claims.join(", ")}`);
    }
    if (compliance.authority_claims.length > 0) {
      console.log(`📜 Authority / Certifications: ${compliance.authority_claims.join(", ")}`);
    }
    if (compliance.performance_claims.length > 0) {
      console.log(`🎯 Performance Guarantees: ${compliance.performance_claims.join(", ")}`);
    }

    if (compliance.ad_pressure_signals.length > 0) {
      console.log("\n⚠️ Flagged Pressure Signals:");
      compliance.ad_pressure_signals.forEach((sig, i) => {
        console.log(`  ${i + 1}. [${sig.type}] "${sig.text}": ${sig.meaning}`);
      });
    } else {
      console.log("\n✅ No high-pressure or misleading compliance flags detected in this ad copy.");
    }
  } else if (adEvidence.status === "unavailable") {
    console.log("❌ META API ERROR:");
    console.log(`Details: ${adEvidence.error}`);
  } else {
    console.log("⚪ No active ads found for this brand in the target country.");
  }
}

run().catch((err) => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
