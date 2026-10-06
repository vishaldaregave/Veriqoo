import { verifyInstagramProduct, formatVerificationResult, generateVerificationReport } from "./agent/verification/index.ts";

async function main() {
  console.log("===============================================================");
  console.log("  INSTAGRAM AD CLICKBAIT & SAFETY SCORE VERIFICATION DEMO  ");
  console.log("===============================================================\n");

  // Example 1: High Clickbait / Scammy Instagram Ad Reel
  console.log("---------------------------------------------------------------");
  console.log("CASE 1: Viral Instagram Ad with Extreme Discount & Fake Urgency");
  console.log("---------------------------------------------------------------");

  const sampleAdPost = `
    Check this out! Stop scrolling! 🚨
    Viral Smartwatch 2025: MRP ₹9,999 now only ₹499 (90% OFF)!
    Doctors recommended sleep tracking, 100% genuine guaranteed results.
    Flash sale ends tonight! Only 3 left in stock!
    Buy now at https://dailydeals-india.shop
    https://www.instagram.com/reel/DEAL_SCAM_SAMPLE/
  `;

  const result1 = await verifyInstagramProduct(
    "https://www.instagram.com/reel/DEAL_SCAM_SAMPLE/",
    sampleAdPost,
  );

  console.log("\n--- WHATSAPP BOT RESPONSE ---");
  const formattedMsg = formatVerificationResult(result1);
  console.log(formattedMsg);

  console.log("\n--- GENERATING DETAILED HTML REPORT ---");
  const report1 = generateVerificationReport(result1);
  console.log(`✅ Dossier Generated: ${report1.file_path} (ID: ${report1.report_id})`);

  // Example 2: Verified, Safe Brand Instagram Reel
  console.log("\n===============================================================");
  console.log("CASE 2: Legitimate Brand with Consistent Pricing & Real Store");
  console.log("===============================================================");

  const sampleLegitPost = `
    boAt Airdopes 141 with 42H playtime, ENx noise cancellation.
    Price: ₹1,299. Available on our official store at https://www.boat-lifestyle.com.
    https://www.instagram.com/reel/LEGIT_BOAT_SAMPLE/
  `;

  const result2 = await verifyInstagramProduct(
    "https://www.instagram.com/reel/LEGIT_BOAT_SAMPLE/",
    sampleLegitPost,
  );

  console.log("\n--- WHATSAPP BOT RESPONSE ---");
  const formattedMsg2 = formatVerificationResult(result2);
  console.log(formattedMsg2);

  const report2 = generateVerificationReport(result2);
  console.log(`✅ Dossier Generated: ${report2.file_path} (ID: ${report2.report_id})`);
}

main().catch(console.error);
