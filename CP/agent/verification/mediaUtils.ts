/**
 * Media downloader utility.
 * Downloads accessible media into memory buffers with timeout and size guards.
 */
export async function downloadMedia(
  url: string,
  options: { maxSizeBytes?: number; timeoutMs?: number } = {},
): Promise<Buffer | null> {
  if (!url || typeof url !== "string" || !url.startsWith("http")) {
    return null;
  }

  const maxSizeBytes = options.maxSizeBytes ?? 5 * 1024 * 1024; // 5MB limit
  const timeoutMs = options.timeoutMs ?? 7000;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    const res = await fetch(url, {
      signal: controller.signal,
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
      },
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      console.warn(`[MEDIA] Download failed with HTTP ${res.status}`);
      return null;
    }

    const contentLength = res.headers.get("content-length");
    if (contentLength && parseInt(contentLength, 10) > maxSizeBytes) {
      console.warn(`[MEDIA] Image size (${contentLength} bytes) exceeds maximum limit (${maxSizeBytes} bytes)`);
      return null;
    }

    const arrayBuffer = await res.arrayBuffer();
    if (arrayBuffer.byteLength > maxSizeBytes) {
      console.warn(`[MEDIA] Downloaded buffer exceeds max size`);
      return null;
    }

    return Buffer.from(arrayBuffer);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.warn(`[MEDIA] Failed to download media image: ${msg}`);
    return null;
  }
}
