import { createWorker } from "tesseract.js";
import { resolve } from "node:path";
import { existsSync } from "node:fs";
import type { OcrResult } from "./types.ts";

/**
 * Performs OCR text extraction on an image buffer or URL using Tesseract.js.
 * Includes bounded timeout protection and explicit workerPath resolution.
 */
export async function performOCR(imageInput: Buffer | string): Promise<OcrResult> {
  if (!imageInput) {
    return { text: "", confidence: 0, status: "failed" };
  }

  const OCR_TIMEOUT_MS = 7000;
  let worker: Awaited<ReturnType<typeof createWorker>> | null = null;
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  const ocrExecution = (async (): Promise<OcrResult> => {
    try {
      // Resolve workerPath explicitly to prevent Eve runtime bundling path mismatches
      const nodeModulesWorker = resolve(
        process.cwd(),
        "node_modules/tesseract.js/src/worker-script/node/index.js",
      );
      const workerExists = existsSync(nodeModulesWorker);
      console.info(`[OCR DEBUG] worker_path=${nodeModulesWorker}`);
      console.info(`[OCR DEBUG] worker_exists=${workerExists}`);

      const workerOptions = workerExists
        ? { workerPath: nodeModulesWorker }
        : {};

      worker = await createWorker("eng", 1, workerOptions);
      const ret = await worker.recognize(imageInput);

      const rawText = ret.data.text.trim();
      const confidence = Math.round(ret.data.confidence);

      await worker.terminate();
      worker = null;

      if (!rawText || rawText.length === 0) {
        return { text: "", confidence: 0, status: "failed" };
      }

      const status: "success" | "partial" = confidence >= 60 ? "success" : "partial";
      return {
        text: rawText,
        confidence,
        status,
      };
    } catch (err) {
      if (worker) {
        try {
          await worker.terminate();
        } catch {
          // ignore
        }
        worker = null;
      }
      const msg = err instanceof Error ? err.message : String(err);
      console.warn(`[OCR] Recognition failed or was skipped: ${msg}`);
      return { text: "", confidence: 0, status: "failed" };
    }
  })();

  const timeoutPromise = new Promise<OcrResult>((resolvePromise) => {
    timeoutId = setTimeout(() => {
      console.warn(`[OCR] Timed out after ${OCR_TIMEOUT_MS}ms, continuing verification pipeline`);
      if (worker) {
        try {
          worker.terminate();
        } catch {
          // ignore
        }
        worker = null;
      }
      resolvePromise({ text: "", confidence: 0, status: "failed" });
    }, OCR_TIMEOUT_MS);
    timeoutId?.unref?.();
  });

  try {
    const result = await Promise.race([ocrExecution, timeoutPromise]);
    if (timeoutId) clearTimeout(timeoutId);
    return result;
  } catch (err) {
    if (timeoutId) clearTimeout(timeoutId);
    console.warn(`[OCR] Unexpected error:`, err);
    return { text: "", confidence: 0, status: "failed" };
  }
}
