#!/usr/bin/env node
import http from "node:http";
import {
  verifyInstagramProduct,
  formatVerificationResult,
  generateVerificationReport,
  extractInstagramUrl,
} from "./agent/verification/index.ts";

const PORT = parseInt(process.env.PORT || process.env.CP_API_PORT || "5050", 10);
const HOST = "0.0.0.0";

const SAMPLE_ADS = [
  {
    title: "Instamart ₹1 Breakfast Deal",
    url: "https://www.instagram.com/p/DdtozWUM5Dh/?stkn=MTgycXoxazUwYXFh",
    context: "Pick any breakfast favourite at ₹1 and get free delivery too! 🥚🍞🥛🛵",
    brand: "Instamart",
    category: "Quick Commerce / Grocery",
    knownPrice: "₹1",
  },
  {
    title: "SwissTime Replica Watch (98% OFF)",
    url: "https://www.instagram.com/reel/C8XYZ12345/",
    context: "Original Luxury Automatic Chronograph - Direct Factory Outlet ₹85,000 now ₹1,499 (98% OFF) ending tonight at https://swisstime-deals.in",
    brand: "SwissTime Replica Store",
    category: "Luxury Goods / Counterfeit",
    knownPrice: "₹1,499",
  },
  {
    title: "AyurRoot Miracle Hair Regrowth",
    url: "https://www.instagram.com/reel/DB987654321/",
    context: "Stops Baldness & Regrows Full Hair in 48 Hours! Doctor recommended 100% organic ₹4,999 now ₹299 (94% OFF)",
    brand: "AyurRoot Remedies",
    category: "Health & Supplements",
    knownPrice: "₹299",
  },
];

function setCorsHeaders(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, Accept");
}

function sendJson(res, statusCode, data) {
  setCorsHeaders(res);
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.writeHead(statusCode);
  res.end(JSON.stringify(data, null, 2));
}

function parseJsonBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 1e6) {
        req.destroy();
        reject(new Error("Request payload too large"));
      }
    });
    req.on("end", () => {
      if (!body.trim()) return resolve({});
      try {
        resolve(JSON.parse(body));
      } catch (err) {
        reject(new Error("Invalid JSON body"));
      }
    });
    req.on("error", reject);
  });
}

const server = http.createServer(async (req, res) => {
  setCorsHeaders(res);

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  const parsedUrl = new URL(req.url, `http://${req.headers.host || "localhost"}`);
  const pathname = parsedUrl.pathname;

  // 1. Health Endpoint
  if (req.method === "GET" && (pathname === "/health" || pathname === "/api/health" || pathname === "/")) {
    sendJson(res, 200, {
      status: "ok",
      service: "veriqoo-cp-instagram-detector",
      version: "1.0.0",
      timestamp: new Date().toISOString(),
      samples_count: SAMPLE_ADS.length,
    });
    return;
  }

  // 2. Samples Endpoint
  if (req.method === "GET" && pathname === "/api/samples") {
    sendJson(res, 200, {
      status: "success",
      samples: SAMPLE_ADS,
    });
    return;
  }

  // 3. Verification Endpoint
  if (req.method === "POST" && (pathname === "/api/verify" || pathname === "/verify")) {
    try {
      const body = await parseJsonBody(req);
      const rawUrl = body.url || body.link || body.instagram_url;
      const contextText = body.context || body.caption || "";

      if (!rawUrl || typeof rawUrl !== "string") {
        sendJson(res, 400, {
          success: false,
          error: "Missing required 'url' field in request body",
        });
        return;
      }

      console.info(`[CP API] Inbound verification request: url="${rawUrl}"`);
      const startTime = Date.now();

      const detectedUrl = extractInstagramUrl(rawUrl) || rawUrl.trim();
      const combinedContext = [detectedUrl, contextText].filter(Boolean).join("\n");

      const result = await verifyInstagramProduct(detectedUrl, combinedContext);
      const report = generateVerificationReport(result);
      const durationMs = Date.now() - startTime;

      const pressureSignals = (result.ad_claim_analysis?.ad_pressure_signals || []).map((s) => ({
        type: s.type,
        text: s.text,
        meaning: s.meaning,
      }));

      const clickbaitFlags = result.risk.clickbait_flags || [];
      const trustSignals = result.risk.positive_signals || [];
      const riskSignals = result.risk.risk_signals || [];
      const missingInfo = result.risk.missing_information || [];

      const responsePayload = {
        success: true,
        url: detectedUrl,
        duration_ms: durationMs,
        safety_score: result.risk.safety_score ?? 50,
        clickbait_score: result.risk.clickbait_score ?? 0,
        clickbait_level: result.risk.clickbait_level ?? "LOW",
        risk_level: result.risk.risk_level ?? "UNKNOWN",
        confidence: result.risk.confidence ?? 0,
        product: {
          name: result.product.name,
          brand: result.product.brand,
          price: result.product.price,
          category: result.product.category,
        },
        seller: {
          name: result.seller.name,
          username: result.seller.username,
          website: result.seller.website,
          contact: result.seller.contact,
          verification_status: result.seller.verification_status,
        },
        claims: result.claims || [],
        clickbait_flags: clickbaitFlags,
        pressure_signals: pressureSignals,
        trust_signals: trustSignals,
        risk_signals: riskSignals,
        missing_information: missingInfo,
        recommendation: result.risk.recommendation,
        evidence_check: {
          instagram: Boolean(result.evidence && result.evidence.post),
          meta_ad: Boolean(result.meta_ad_evidence && result.meta_ad_evidence.status === "available"),
          website: Boolean(result.website_evidence && result.website_evidence.status === "available"),
          product_image: (result.evidence?.media?.length ?? 0) > 0,
          ocr: Boolean(result.media_evidence && result.media_evidence.url_available),
        },
        report: {
          id: report.report_id,
          file_path: report.file_path,
        },
        formatted_message: formatVerificationResult(result),
      };

      sendJson(res, 200, responsePayload);
    } catch (err) {
      console.error("[CP API] Verification exception:", err);
      sendJson(res, 500, {
        success: false,
        error: err instanceof Error ? err.message : "Internal verification error",
      });
    }
    return;
  }

  // Not Found
  sendJson(res, 404, {
    error: "Endpoint not found",
    supported_endpoints: ["GET /health", "GET /api/samples", "POST /api/verify"],
  });
});

server.listen(PORT, HOST, () => {
  console.log(`
===================================================================
       🛡️  VERIQOO CP INSTAGRAM AD DETECTOR REST API
===================================================================
• Server running on http://${HOST}:${PORT}
• Health Check   : http://localhost:${PORT}/health
• Sample Ads     : http://localhost:${PORT}/api/samples
• Verify Endpoint: POST http://localhost:${PORT}/api/verify
• Accepts payload: { "url": "https://instagram.com/...", "context": "optional" }
===================================================================
`);
});

process.on("SIGINT", () => {
  console.log("\n👋 Shutting down CP API server...");
  server.close(() => process.exit(0));
});
