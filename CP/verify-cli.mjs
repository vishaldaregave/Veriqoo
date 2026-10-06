#!/usr/bin/env node
import * as readline from "node:readline";
import { stdin as input, stdout as output } from "node:process";
import { exec } from "node:child_process";
import {
  verifyInstagramProduct,
  formatVerificationResult,
  generateVerificationReport,
  extractInstagramUrl,
  parseInstagramUrl,
} from "./agent/verification/index.ts";

const PROMPT_STR = "🔗 Enter Instagram Link (or 'exit' to stop): ";

function openFileInBrowser(filePath) {
  const platform = process.platform;
  const cmd =
    platform === "win32"
      ? `start "" "${filePath}"`
      : platform === "darwin"
        ? `open "${filePath}"`
        : `xdg-open "${filePath}"`;

  exec(cmd, (err) => {
    if (err) {
      // Non-critical, ignore browser open errors
    }
  });
}

async function processVerification(rawInput, isVerbose = false, autoOpen = false) {
  const trimmed = rawInput.trim();
  if (!trimmed) return;

  const detectedUrl = extractInstagramUrl(trimmed) || trimmed.split(/\s+/)[0];
  const contextText = trimmed.replace(detectedUrl, "").trim();
  const parsed = parseInstagramUrl(detectedUrl);

  const isInsta =
    detectedUrl.toLowerCase().includes("instagram.com") ||
    detectedUrl.toLowerCase().includes("instagr.am");

  if (!isInsta) {
    console.log("\n⚠️  NO INSTAGRAM LINK DETECTED IN INPUT");
    console.log("   Received: " + trimmed);
    console.log("   Expected: https://www.instagram.com/reel/... or https://www.instagram.com/p/...\n");
    return;
  }

  console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  console.log("🔍 PROCESSING VERIFICATION REQUEST");
  console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  console.log(`🎯 URL        : ${detectedUrl}`);
  console.log(`📌 Post Type  : ${(parsed.type || "unknown").toUpperCase()}`);
  if (parsed.shortcode) {
    console.log(`🔑 Shortcode  : ${parsed.shortcode}`);
  }
  if (contextText) {
    console.log(`📝 Extra Info : "${contextText}"`);
  }
  console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");

  const originalInfo = console.info;
  const originalWarn = console.warn;
  if (!isVerbose) {
    console.info = () => {};
    console.warn = () => {};
  }

  const startTime = Date.now();
  process.stdout.write("⏳ [1/4] Inspecting Instagram listing & creator profile...\n");

  try {
    const combinedContext = [detectedUrl, contextText].filter(Boolean).join("\n");
    const result = await verifyInstagramProduct(detectedUrl, combinedContext);

    process.stdout.write("⏳ [2/4] Auditing clickbait triggers, discounts & claims...\n");
    process.stdout.write("⏳ [3/4] Cross-checking external store & policies...\n");
    process.stdout.write("⏳ [4/4] Calculating deterministic Safety Score & Trust Matrix...\n\n");

    console.info = originalInfo;
    console.warn = originalWarn;

    const formattedMessage = formatVerificationResult(result);
    console.log(formattedMessage);

    const report = generateVerificationReport(result);
    const duration = ((Date.now() - startTime) / 1000).toFixed(2);

    console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    console.log("📄 DETAILED VERIFICATION DOSSIER GENERATED");
    console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    console.log(`• Report ID   : ${report.report_id}`);
    console.log(`• Dossier Path: ${report.file_path}`);
    console.log(`• Time Taken  : ${duration}s`);
    console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");

    if (autoOpen && report.file_path) {
      console.log("🌐 Opening HTML Dossier in default browser...\n");
      openFileInBrowser(report.file_path);
    }
  } catch (err) {
    console.info = originalInfo;
    console.warn = originalWarn;
    console.error("\n❌ Verification error:", err instanceof Error ? err.message : err);
    console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
  }
}

async function main() {
  const args = process.argv.slice(2);
  const isVerbose = args.includes("--verbose") || args.includes("-v");
  const autoOpen = args.includes("--open");
  const filteredArgs = args.filter(
    (a) => a !== "--verbose" && a !== "-v" && a !== "--open",
  );

  console.log(`
===================================================================
       🛡️  INSTAGRAM AD & CLICKBAIT VERIFIER (LIVE CONSOLE)
===================================================================
• Paste any Instagram post, ad, or reel link to verify claims.
• Engine stays running in terminal — keep entering links continuously.
• You can paste caption text or store URL alongside the Instagram link.
• Type 'exit', 'quit', 'stop', or press Ctrl+C at any time to stop.
• Type 'clear' to clear console screen.
• Type 'help' for quick usage instructions.
===================================================================
`);

  // If a link was passed directly via CLI arguments, process it first
  if (filteredArgs.length > 0) {
    const initialInput = filteredArgs.join(" ");
    await processVerification(initialInput, isVerbose, autoOpen);
  }

  const isTTY = Boolean(process.stdin.isTTY);
  const rl = readline.createInterface({
    input,
    output,
    prompt: PROMPT_STR,
    terminal: isTTY,
  });

  // Handle Ctrl+C cleanly
  rl.on("SIGINT", () => {
    console.log("\n\n👋 Stopped by user. Goodbye!\n");
    rl.close();
    process.exit(0);
  });

  if (isTTY && !rl.closed) {
    rl.prompt();
  }

  try {
    for await (const rawLine of rl) {
      const trimmed = rawLine.trim();

      if (!trimmed) {
        if (isTTY && !rl.closed) rl.prompt();
        continue;
      }

      const lower = trimmed.toLowerCase();
      if (["exit", "quit", "stop", "q", ":q"].includes(lower)) {
        console.log("\n👋 Exiting verification console. Goodbye!\n");
        rl.close();
        break;
      }

      if (["clear", "cls"].includes(lower)) {
        console.clear();
        if (isTTY && !rl.closed) rl.prompt();
        continue;
      }

      if (lower === "help") {
        console.log(`
📖 CONSOLE USAGE:
  - Paste any Instagram URL: https://www.instagram.com/reel/C.../
  - Optional Context: <url> 90% discount, external store https://store.com
  - Commands: 'exit' to quit, 'clear' to wipe screen, 'help' for this text.
`);
        if (isTTY && !rl.closed) rl.prompt();
        continue;
      }

      await processVerification(trimmed, isVerbose, autoOpen);

      if (isTTY && !rl.closed) {
        rl.prompt();
      }
    }
  } catch (err) {
    if (err && (err.name === "AbortError" || err.code === "ERR_USE_AFTER_CLOSE")) {
      console.log("\n👋 Session ended.");
    } else {
      console.error("Session error:", err);
    }
  } finally {
    if (!rl.closed) {
      rl.close();
    }
  }
}

main().catch((err) => {
  console.error("Fatal Error:", err);
  process.exit(1);
});
