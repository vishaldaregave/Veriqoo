import type { MetaAdEvidence, InstagramEvidence, ProductInfo, SellerInfo } from "./types.ts";

/**
 * Searches the Meta Ad Library API for active or historical advertising records
 * associated with the seller, page, brand, or product.
 *
 * Implements bounded timeout (max 8s) and graceful fallback if token is missing
 * or the service is unreachable.
 */
export async function collectMetaAdEvidence(
  evidence: InstagramEvidence,
  product?: ProductInfo,
  seller?: SellerInfo,
): Promise<MetaAdEvidence> {
  const token = process.env.META_AD_LIBRARY_ACCESS_TOKEN;
  const country = process.env.META_AD_LIBRARY_COUNTRY || "IN";

  if (!token || !token.trim()) {
    return {
      status: "unavailable",
      error: "No Meta Ad Library access token configured",
      evidenceSource: "Meta Ad Library",
    };
  }

  // Determine candidate search terms (seller name/handle first, then brand/product)
  const candidateTerms: string[] = [];
  if (seller?.name && seller.name.length > 2) candidateTerms.push(seller.name);
  if (seller?.username && seller.username.length > 2) candidateTerms.push(seller.username);
  if (evidence.account.username && evidence.account.username.length > 2 && !candidateTerms.includes(evidence.account.username)) {
    candidateTerms.push(evidence.account.username);
  }
  if (product?.brand && product.brand.length > 2 && !candidateTerms.includes(product.brand)) {
    candidateTerms.push(product.brand);
  }
  if (product?.name && product.name.length > 3 && !candidateTerms.includes(product.name)) {
    candidateTerms.push(product.name);
  }

  if (candidateTerms.length === 0) {
    return {
      status: "not_found",
      evidenceSource: "Meta Ad Library",
    };
  }

  const TIMEOUT_MS = 8000;
  let lastApiError: string | null = null;
  let hadSuccessfulQuery = false;

  for (const term of candidateTerms) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

      const url = new URL("https://graph.facebook.com/v20.0/ads_archive");
      url.searchParams.set("access_token", token);
      url.searchParams.set("ad_reached_countries", `["${country}"]`);
      url.searchParams.set("ad_type", "ALL");
      url.searchParams.set("search_terms", term);
      url.searchParams.set("limit", "3");
      url.searchParams.set(
        "fields",
        "id,ad_creation_time,ad_delivery_start_time,ad_delivery_stop_time,ad_creative_bodies,ad_creative_link_captions,ad_creative_link_descriptions,ad_creative_link_titles,ad_snapshot_url,page_id,page_name,publisher_platforms",
      );

      const res = await fetch(url.toString(), {
        signal: controller.signal,
        headers: {
          "Accept": "application/json",
        },
      });

      clearTimeout(timeoutId);

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        const errMsg = (errJson as { error?: { message?: string } })?.error?.message || `HTTP ${res.status}`;
        lastApiError = errMsg;
        console.warn(`[MetaAdEvidence] Query for "${term}" returned ${res.status}: ${errMsg}`);
        continue;
      }

      hadSuccessfulQuery = true;
      const data = (await res.json()) as {
        data?: Array<{
          id?: string;
          page_id?: string;
          page_name?: string;
          publisher_platforms?: string[];
          ad_delivery_start_time?: string;
          ad_delivery_stop_time?: string;
          ad_creative_bodies?: string[];
          ad_creative_link_titles?: string[];
          ad_creative_link_descriptions?: string[];
          ad_creative_link_captions?: string[];
          ad_snapshot_url?: string;
        }>;
      };

      if (data.data && data.data.length > 0) {
        const topAd = data.data[0];
        const platforms = topAd.publisher_platforms || ["instagram"];
        const deliveryStart = topAd.ad_delivery_start_time ? topAd.ad_delivery_start_time.split("T")[0] : undefined;
        const deliveryEnd = topAd.ad_delivery_stop_time ? topAd.ad_delivery_stop_time.split("T")[0] : "Active";
        const adText = topAd.ad_creative_bodies?.[0] || undefined;
        const linkTitle = topAd.ad_creative_link_titles?.[0] || undefined;
        const linkDescription = topAd.ad_creative_link_descriptions?.[0] || undefined;
        const destinationUrl = topAd.ad_creative_link_captions?.[0] || undefined;

        return {
          status: "found",
          libraryId: topAd.id,
          advertiserName: topAd.page_name,
          advertiserPageId: topAd.page_id,
          publisherPlatforms: platforms,
          deliveryStart,
          deliveryEnd,
          adText,
          linkTitle,
          linkDescription,
          adSnapshotUrl: topAd.ad_snapshot_url,
          destinationUrl,
          evidenceSource: "Meta Ad Library",
        };
      }
    } catch (err: unknown) {
      const isAbort = err instanceof Error && err.name === "AbortError";
      if (isAbort) {
        lastApiError = "Request timed out";
        console.warn(`[MetaAdEvidence] Request for "${term}" timed out after ${TIMEOUT_MS}ms`);
      } else {
        const msg = err instanceof Error ? err.message : String(err);
        lastApiError = msg;
        console.warn(`[MetaAdEvidence] Request for "${term}" failed: ${msg}`);
      }
    }
  }

  if (!hadSuccessfulQuery && lastApiError) {
    return {
      status: "unavailable",
      error: lastApiError,
      evidenceSource: "Meta Ad Library",
    };
  }

  return {
    status: "not_found",
    evidenceSource: "Meta Ad Library",
  };
}
