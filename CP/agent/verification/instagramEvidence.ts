import type {
  InstagramEvidence,
  InstagramSource,
  InstagramAccount,
  InstagramPost,
  ProductInfo,
  SellerInfo,
  Claim,
  MediaItem,
} from "./types.ts";

/**
 * Validates if the hostname belongs to Instagram (e.g. instagram.com, www.instagram.com, instagr.am, subdomains).
 */
export function isInstagramHost(hostname: string): boolean {
  const host = hostname.toLowerCase();
  return (
    host === "instagram.com" ||
    host.endsWith(".instagram.com") ||
    host === "instagr.am" ||
    host.endsWith(".instagr.am")
  );
}

/**
 * Strips surrounding punctuation from candidate URL tokens.
 */
function cleanCandidateUrl(raw: string): string {
  return raw.replace(/^[<("'[{]+/, "").replace(/[.,!?:;)>\]'"}]+$/, "");
}

/**
 * Extracts the first valid Instagram URL from raw text.
 */
export function extractInstagramUrl(text: string): string | null {
  if (!text || typeof text !== "string") return null;

  const urlPattern = /(?:https?:\/\/|www\.|(?:[a-z0-9_-]+\.)?instagram\.com\/|instagr\.am\/)[^\s<>"'{}|\\^`]+/gi;
  const matches = text.match(urlPattern);
  if (!matches) return null;

  for (const rawMatch of matches) {
    const cleaned = cleanCandidateUrl(rawMatch);
    if (!cleaned) continue;

    try {
      const urlToParse =
        cleaned.startsWith("http://") || cleaned.startsWith("https://")
          ? cleaned
          : `https://${cleaned}`;
      const parsed = new URL(urlToParse);
      if (
        (parsed.protocol === "http:" || parsed.protocol === "https:") &&
        isInstagramHost(parsed.hostname)
      ) {
        return urlToParse;
      }
    } catch {
      // Ignore invalid URLs
    }
  }

  return null;
}

/**
 * Extracts the canonical Instagram URL and shortcode from any Instagram URL.
 */
export function parseInstagramUrl(rawUrl: string): {
  canonicalUrl: string;
  type: "reel" | "post" | "video" | "unknown";
  shortcode: string | null;
} {
  try {
    const urlToParse =
      rawUrl.startsWith("http://") || rawUrl.startsWith("https://")
        ? rawUrl
        : `https://${rawUrl}`;
    const parsed = new URL(urlToParse);
    const pathname = parsed.pathname;

    let type: "reel" | "post" | "video" | "unknown" = "unknown";
    if (pathname.includes("/reel/") || pathname.includes("/reels/")) {
      type = "reel";
    } else if (pathname.includes("/p/")) {
      type = "post";
    } else if (pathname.includes("/tv/")) {
      type = "video";
    }

    const segments = pathname.split("/").filter(Boolean);
    let shortcode: string | null = null;
    const typeIndex = segments.findIndex((s) => ["reel", "reels", "p", "tv"].includes(s.toLowerCase()));
    if (typeIndex !== -1 && segments[typeIndex + 1]) {
      shortcode = segments[typeIndex + 1];
    }

    const cleanPath = shortcode && typeIndex !== -1
      ? `/${segments[typeIndex]}/${shortcode}/`
      : pathname;

    const canonicalUrl = `https://www.instagram.com${cleanPath}`;

    return { canonicalUrl, type, shortcode };
  } catch {
    return { canonicalUrl: rawUrl, type: "unknown", shortcode: null };
  }
}

/**
 * Decodes HTML entities (including decimal, hex, and unicode currencies like Rupee ₹).
 */
function decodeHtmlEntities(str: string): string {
  if (!str) return "";
  return str
    .replace(/\\u0026/g, "&")
    .replace(/\\n/g, "\n")
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/g, "'")
    .replace(/&#x2F;/g, "/")
    .replace(/&#x20b9;/gi, "₹")
    .replace(/&#(\d+);/g, (_, dec) => {
      try {
        return String.fromCodePoint(parseInt(dec, 10));
      } catch {
        return "";
      }
    })
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => {
      try {
        return String.fromCodePoint(parseInt(hex, 16));
      } catch {
        return "";
      }
    });
}

/**
 * Extracts meta tag contents from raw HTML text.
 */
function extractMetaTags(html: string): Record<string, string> {
  const meta: Record<string, string> = {};
  const metaRegex = /<meta\s+([^>]*?)>/gi;
  let match;

  while ((match = metaRegex.exec(html)) !== null) {
    const tag = match[1];
    const propertyMatch = tag.match(/(?:property|name)=["']([^"']+)["']/i);
    const contentMatch = tag.match(/content=["']([^"']*?)["']/i);

    if (propertyMatch && contentMatch) {
      const key = propertyMatch[1].toLowerCase();
      meta[key] = decodeHtmlEntities(contentMatch[1]);
    }
  }

  // Also check <title>
  const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
  if (titleMatch) {
    meta["title"] = decodeHtmlEntities(titleMatch[1]);
  }

  return meta;
}

/**
 * Parses author username, display name, and caption from OpenGraph title and description.
 */
function parseAuthorAndCaption(
  title?: string,
  description?: string,
): { username: string | null; displayName: string | null; caption: string | null } {
  let username: string | null = null;
  let displayName: string | null = null;
  let caption: string | null = null;

  if (title) {
    const userMatch = title.match(/^(.*?)(?:\s*\(@([a-zA-Z0-9._]+)\))?\s+on\s+Instagram/i);
    if (userMatch) {
      if (userMatch[2]) {
        username = userMatch[2];
        displayName = userMatch[1].trim() || null;
      } else if (userMatch[1].startsWith("@")) {
        username = userMatch[1].slice(1).trim();
        displayName = username;
      } else {
        displayName = userMatch[1].trim() || null;
        // In "Brand on Instagram", the brand name can serve as creator identity
        username = userMatch[1].trim().toLowerCase().replace(/\s+/g, "");
      }
    }

    const quoteMatch = title.match(/:\s*["'“]([\s\S]+?)["'”]\s*$/);
    if (quoteMatch) {
      caption = quoteMatch[1].trim();
    }
  }

  if (description) {
    if (!username) {
      const descUserMatch =
        description.match(/(?:^|\s|-)\s*([a-zA-Z0-9._]+)\s+on\s+[A-Za-z]+\s+\d+/i) ||
        description.match(/@([a-zA-Z0-9._]+)/);
      if (descUserMatch) {
        username = descUserMatch[1];
      }
    }

    const descQuoteMatch = description.match(/:\s*["'“]([\s\S]+?)["'”]\s*[.]?\s*$/);
    if (descQuoteMatch && !caption) {
      caption = descQuoteMatch[1].trim();
    } else if (
      !caption &&
      !description.toLowerCase().includes("see instagram photos and videos") &&
      !description.toLowerCase().includes("create an account or log in")
    ) {
      caption = description.trim();
    }
  }

  return { username, displayName, caption };
}

/**
 * Extracts external URLs embedded in caption text.
 */
function extractLinksFromText(text: string): string[] {
  if (!text) return [];
  const urlRegex = /(?:https?:\/\/|www\.)[^\s<>"'{}|\\^`]+/gi;
  const matches = text.match(urlRegex) || [];
  return Array.from(
    new Set(
      matches
        .map((url) => cleanCandidateUrl(url))
        .filter(Boolean)
        .map((url) => (url.startsWith("http") ? url : `https://${url}`)),
    ),
  );
}

/**
 * Robust multi-source Instagram evidence collector.
 * Extracts evidence across:
 * 1. OpenGraph & Twitter tags
 * 2. JSON-LD scripts
 * 3. Embedded JSON payloads
 * 4. Embed / oEmbed fallback endpoints
 * 5. Inbound context clues
 */
export async function collectInstagramEvidence(
  rawUrl: string,
  contextText?: string,
): Promise<InstagramEvidence> {
  const { canonicalUrl, type, shortcode } = parseInstagramUrl(rawUrl);

  const source: InstagramSource = {
    platform: "instagram",
    url: rawUrl,
    canonical_url: canonicalUrl,
    shortcode: shortcode || undefined,
  };

  const account: InstagramAccount = { username: null, display_name: null };
  const post: InstagramPost = { type, caption: null, timestamp: null };
  const product: ProductInfo = { name: null, brand: null, price: null, category: null };
  const seller: SellerInfo = { name: null, username: null, website: null, contact: null };
  const claims: Claim[] = [];
  const external_links: string[] = [];
  const evidence: string[] = [];
  const missing_information: string[] = [];
  const errors: string[] = [];

  const media: MediaItem[] = [];
  let video_analysis: "not_available" | "processed" | null = null;
  if (type === "reel" || type === "video") {
    video_analysis = "not_available";
  }

  let isRestrictedByMeta = false;

  // 1. Primary Attempt: Fetch page with crawler headers
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);

    const response = await fetch(canonicalUrl, {
      signal: controller.signal,
      headers: {
        "User-Agent":
          "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php) WhatsApp/2.23.23.77",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
      },
    });

    clearTimeout(timeoutId);

    if (response.ok) {
      const html = await response.text();
      const meta = extractMetaTags(html);

      const ogTitle = meta["og:title"] || meta["twitter:title"] || meta["title"];
      const ogDesc = meta["og:description"] || meta["twitter:description"] || meta["description"];
      const ogImage = meta["og:image"] || meta["twitter:image"];

      if (ogImage && !ogImage.includes("static.cdninstagram.com") && !media.some((m) => m.url === ogImage)) {
        media.push({ type: "image", url: ogImage, source: "instagram" });
        evidence.push(`Found product media image URL in Instagram metadata`);
      }

      if (ogTitle || ogDesc) {
        const parsed = parseAuthorAndCaption(ogTitle, ogDesc);
        if (parsed.username) {
          account.username = parsed.username;
          seller.username = parsed.username;
          evidence.push(`Identified creator username: @${parsed.username}`);
        }
        if (parsed.displayName) {
          account.display_name = parsed.displayName;
          seller.name = parsed.displayName;
        }
        if (parsed.caption) {
          post.caption = parsed.caption;
          evidence.push(`Extracted post text / caption (${parsed.caption.length} characters)`);
        }
      }

      // Fallback: If caption was not extracted, query with Twitterbot which often receives full captions
      if (!post.caption) {
        try {
          const twController = new AbortController();
          const twTimeout = setTimeout(() => twController.abort(), 6000);
          const twRes = await fetch(canonicalUrl, {
            signal: twController.signal,
            headers: {
              "User-Agent": "Twitterbot/1.0",
              "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
              "Accept-Language": "en-US,en;q=0.9",
            },
          });
          clearTimeout(twTimeout);
          if (twRes.ok) {
            const twHtml = await twRes.text();
            const twMeta = extractMetaTags(twHtml);
            const twOgTitle = twMeta["og:title"] || twMeta["twitter:title"] || twMeta["title"];
            const twOgDesc = twMeta["og:description"] || twMeta["twitter:description"] || twMeta["description"];
            const twParsed = parseAuthorAndCaption(twOgTitle, twOgDesc);
            if (twParsed.username && !account.username) {
              account.username = twParsed.username;
              seller.username = twParsed.username;
              evidence.push(`Identified creator username: @${twParsed.username}`);
            }
            if (twParsed.displayName && !account.display_name) {
              account.display_name = twParsed.displayName;
              seller.name = twParsed.displayName;
            }
            if (twParsed.caption && !post.caption) {
              post.caption = twParsed.caption;
              evidence.push(`Extracted post text / caption via social preview (${twParsed.caption.length} characters)`);
            }
          }
        } catch {
          // Fallback fetch error non-blocking
        }
      }

      // Check JSON-LD in HTML
      const jsonLdMatch = html.match(/<script type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/i);
      if (jsonLdMatch) {
        try {
          const ldData = JSON.parse(jsonLdMatch[1]);
          if (ldData.caption && !post.caption) {
            post.caption = decodeHtmlEntities(ldData.caption);
            evidence.push("Extracted caption from JSON-LD metadata");
          }
          if (ldData.author?.name && !account.username) {
            account.username = ldData.author.name;
            seller.username = ldData.author.name;
          }
          if (ldData.image && !media.some((m) => m.url === ldData.image)) {
            media.push({ type: "image", url: ldData.image, source: "instagram" });
          }
        } catch {
          // ignore json parse error
        }
      }

      // Check Embedded Relay/Polaris JSON snippets
      if (!post.caption) {
        const captionJson = html.match(/"caption":\s*\{\s*"text":\s*"([^"]+)"/i)
          || html.match(/"edge_media_to_caption":\s*\{\s*"edges":\s*\[\s*\{\s*"node":\s*\{\s*"text":\s*"([^"]+)"/i);
        if (captionJson && captionJson[1]) {
          post.caption = decodeHtmlEntities(captionJson[1]);
          evidence.push("Extracted caption from embedded JSON payload");
        }
      }

      if (!account.username) {
        const ownerJson = html.match(/"owner":\s*\{\s*"id":\s*"[^"]*",\s*"username":\s*"([^"]+)"/i)
          || html.match(/"username":\s*"([a-zA-Z0-9._]+)"/i);
        if (ownerJson && ownerJson[1] && !["instagram", "meta", "none"].includes(ownerJson[1].toLowerCase())) {
          account.username = ownerJson[1];
          seller.username = ownerJson[1];
          evidence.push(`Identified username from page state: @${ownerJson[1]}`);
        }
      }

      if (html.includes("Login • Instagram") || (!post.caption && !account.username)) {
        isRestrictedByMeta = true;
      }
    } else {
      errors.push(`Instagram returned HTTP status ${response.status}`);
      isRestrictedByMeta = true;
    }
  } catch (err: unknown) {
    const errorMessage = err instanceof Error ? err.message : String(err);
    errors.push(`Failed to fetch public Instagram page: ${errorMessage}`);
    isRestrictedByMeta = true;
  }

  // 2. Secondary Attempt: Public Embed / oEmbed endpoints if caption/username missing
  if ((!post.caption || !account.username || media.length === 0) && shortcode) {
    const embedUrls = [
      `https://www.instagram.com/p/${shortcode}/embed/captioned/`,
      `https://api.instagram.com/oembed/?url=https://www.instagram.com/p/${shortcode}/`,
    ];

    for (const eu of embedUrls) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4000);

        const res = await fetch(eu, {
          signal: controller.signal,
          headers: {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/json,*/*",
          },
        });
        clearTimeout(timeoutId);

        if (res.ok) {
          const body = await res.text();
          if (eu.includes("oembed") && body.startsWith("{")) {
            try {
              const data = JSON.parse(body);
              if (data.author_name && !account.username) {
                account.username = data.author_name;
                seller.username = data.author_name;
                evidence.push(`Obtained author from oEmbed: @${data.author_name}`);
              }
              if (data.title && !post.caption) {
                post.caption = data.title;
                evidence.push("Obtained caption from oEmbed");
              }
              if (data.thumbnail_url && !media.some((m) => m.url === data.thumbnail_url)) {
                media.push({ type: "image", url: data.thumbnail_url, source: "instagram" });
              }
            } catch {
              // ignore
            }
          } else {
            // Embed HTML parsing
            const embedUser = body.match(/class="[^"]*CaptionUsername[^"]*"[^>]*>([^<]+)<\/a>/i)
              || body.match(/instagram\.com\/([a-zA-Z0-9._]+)\/\?utm_source/i);
            if (embedUser && !account.username) {
              account.username = embedUser[1].trim();
              seller.username = embedUser[1].trim();
              evidence.push(`Identified creator username from embed: @${embedUser[1]}`);
            }

            const embedCaption = body.match(/class="[^"]*CaptionComments[^"]*"[^>]*>([\s\S]*?)<\/div>/i)
              || body.match(/class="Caption"[^>]*>([\s\S]*?)<\/div>/i);
            if (embedCaption && !post.caption) {
              post.caption = decodeHtmlEntities(embedCaption[1].replace(/<[^>]+>/g, " ").trim());
              evidence.push("Extracted caption from Instagram embed");
            }
          }
        }
      } catch {
        // non-blocking fallback
      }
    }
  }

  // 3. Tertiary Fallback: Parse user-provided WhatsApp context if Meta restricts public page
  if (contextText && typeof contextText === "string") {
    const extractedLinks = extractLinksFromText(contextText);
    for (const link of extractedLinks) {
      if (!link.includes("instagram.com") && !external_links.includes(link)) {
        external_links.push(link);
        evidence.push(`Found store link in message context: ${link}`);
      }
    }

    // Extract @seller mentions from context if not found yet
    if (!account.username) {
      const mentionMatch = contextText.match(/@([a-zA-Z0-9._]+)/);
      if (mentionMatch) {
        account.username = mentionMatch[1];
        seller.username = mentionMatch[1];
        evidence.push(`Identified seller handle from user message: @${mentionMatch[1]}`);
      }
    }

    // If caption is still empty, use user's descriptive text
    if (!post.caption && contextText.length > 10) {
      const cleanedPrompt = contextText.replace(/https?:\/\/[^\s]+/gi, "").trim();
      if (cleanedPrompt.length > 5) {
        post.caption = cleanedPrompt;
        evidence.push(`Using provided item context: "${cleanedPrompt.slice(0, 80)}"`);
      }
    }
  }

  // Extract external links from caption if available
  if (post.caption) {
    const linksInCaption = extractLinksFromText(post.caption);
    for (const u of linksInCaption) {
      if (!external_links.includes(u) && !u.includes("instagram.com")) {
        external_links.push(u);
        evidence.push(`Found external link in caption: ${u}`);
      }
    }
  }

  // Populate missing information & status
  if (isRestrictedByMeta && !post.caption && !account.username) {
    missing_information.push("Instagram post details restricted by Meta login wall (public metadata limited)");
  }
  if (!account.username) missing_information.push("Account username could not be verified directly");
  if (!post.caption) missing_information.push("Post caption could not be retrieved from Meta");
  if (external_links.length === 0) missing_information.push("No external store or domain link provided");
  if (media.length === 0) missing_information.push("Product image URL was not accessible from public metadata");

  return {
    source,
    account,
    post,
    product,
    seller,
    claims,
    media,
    video_analysis,
    external_links,
    evidence,
    missing_information,
    errors,
  };
}
