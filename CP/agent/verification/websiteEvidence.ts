import type {
  WebsiteEvidence,
  CompanyInfo,
  WebsiteProductInfo,
  WebsitePolicies,
} from "./types.ts";

/**
 * Strips HTML tags and decodes basic entities.
 */
function cleanText(html: string): string {
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, " ")
    .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Extracts meta tags and OpenGraph data from website HTML.
 */
function extractMetaProperties(html: string): Record<string, string> {
  const meta: Record<string, string> = {};
  const metaRegex = /<meta\s+([^>]*?)>/gi;
  let match;

  while ((match = metaRegex.exec(html)) !== null) {
    const tag = match[1];
    const propertyMatch = tag.match(/(?:property|name)=["']([^"']+)["']/i);
    const contentMatch = tag.match(/content=["']([^"']*?)["']/i);

    if (propertyMatch && contentMatch) {
      meta[propertyMatch[1].toLowerCase()] = contentMatch[1].trim();
    }
  }

  const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
  if (titleMatch) {
    meta["title"] = titleMatch[1].trim();
  }

  return meta;
}

/**
 * Collects evidence from an external website URL.
 */
export async function collectWebsiteEvidence(url: string | null | undefined): Promise<WebsiteEvidence> {
  if (!url || typeof url !== "string" || !url.startsWith("http")) {
    return {
      url: url || "",
      domain: "",
      status: "not_found",
      company: { name: null, email: null, phone: null, address: null },
      product: { name: null, brand: null, price: null, description: null },
      policies: { refund: false, return: false, shipping: false, privacy: false, terms: false },
      evidence: [],
      missing_information: ["No external store or website URL was provided in the Instagram post."],
      errors: [],
    };
  }

  let domain = "";
  try {
    domain = new URL(url).hostname;
  } catch {
    domain = url;
  }

  const company: CompanyInfo = { name: null, email: null, phone: null, address: null };
  const product: WebsiteProductInfo = { name: null, brand: null, price: null, description: null };
  const policies: WebsitePolicies = {
    refund: false,
    return: false,
    shipping: false,
    privacy: false,
    terms: false,
  };
  const evidence: string[] = [];
  const missing_information: string[] = [];
  const errors: string[] = [];

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 7000);

    const res = await fetch(url, {
      signal: controller.signal,
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
      },
      redirect: "follow",
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      const statusText = res.status === 403 || res.status === 401 ? "blocked" : "inaccessible";
      errors.push(`Website returned HTTP status ${res.status}`);
      return {
        url,
        domain,
        status: statusText,
        company,
        product,
        policies,
        evidence,
        missing_information: [`Website at ${domain} returned HTTP ${res.status}`],
        errors,
      };
    }

    const html = await res.text();
    const meta = extractMetaProperties(html);
    const bodyText = cleanText(html);

    evidence.push(`Successfully accessed website at ${domain}`);

    // 1. Company Name Identification
    if (meta["og:site_name"]) {
      company.name = meta["og:site_name"];
    } else if (meta["title"]) {
      const parts = meta["title"].split(/[-–|:•]/);
      company.name = parts[parts.length - 1].trim() || parts[0].trim();
    } else {
      const copyrightMatch = bodyText.match(/(?:©|copyright|\(c\))\s*(?:\d{4})?\s*([A-Za-z0-9\s.,&'-]{3,35})/i);
      if (copyrightMatch) {
        company.name = copyrightMatch[1].trim();
      }
    }
    if (company.name) {
      evidence.push(`Identified company / website name: ${company.name}`);
    }

    // 2. Company Contact (Email & Phone)
    const emailRegex = /\b[A-Za-z0-9._%+-]+@(?!example\.com|w3\.org|s\.w\.org|domain\.com|schema\.org)[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/gi;
    const emailMatches = html.match(emailRegex);
    if (emailMatches && emailMatches.length > 0) {
      company.email = emailMatches[0].toLowerCase();
      evidence.push(`Found customer contact email: ${company.email}`);
    }

    const phoneRegex = /(?:call|contact|phone|tel|whatsapp)?\s*[:\-]?\s*(\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4})\b/i;
    const phoneMatch = bodyText.match(phoneRegex);
    if (phoneMatch && phoneMatch[1].replace(/\D/g, "").length >= 8) {
      company.phone = phoneMatch[1].trim();
      evidence.push(`Found business contact phone: ${company.phone}`);
    }

    // 3. Product Extraction from Website
    if (meta["og:title"] || meta["title"]) {
      product.name = meta["og:title"] || meta["title"];
    }
    if (meta["og:description"] || meta["description"]) {
      product.description = meta["og:description"] || meta["description"];
    }
    if (meta["og:price:amount"]) {
      const currency = meta["og:price:currency"] || "$";
      product.price = `${currency} ${meta["og:price:amount"]}`;
      evidence.push(`Extracted product price: ${product.price}`);
    } else {
      const priceMatch = bodyText.match(/(?:[$€£₹]|Rs\.?|USD|INR|EUR)\s*(\d+(?:[.,]\d{1,2})?)/i);
      if (priceMatch) {
        product.price = priceMatch[0].trim();
      }
    }

    // 4. Policy Detection (Refund, Return, Shipping, Privacy, Terms)
    const lowerHtml = html.toLowerCase();

    if (lowerHtml.includes("refund policy") || lowerHtml.includes("/refund") || lowerHtml.includes("money-back")) {
      policies.refund = true;
      evidence.push("Detected Refund Policy on website.");
    }
    if (lowerHtml.includes("return policy") || lowerHtml.includes("/return") || lowerHtml.includes("30-day return") || lowerHtml.includes("7-day return")) {
      policies.return = true;
      evidence.push("Detected Return Policy on website.");
    }
    if (lowerHtml.includes("shipping policy") || lowerHtml.includes("/shipping") || lowerHtml.includes("delivery information")) {
      policies.shipping = true;
      evidence.push("Detected Shipping & Delivery terms.");
    }
    if (lowerHtml.includes("privacy policy") || lowerHtml.includes("/privacy")) {
      policies.privacy = true;
      evidence.push("Detected Privacy Policy.");
    }
    if (lowerHtml.includes("terms of service") || lowerHtml.includes("terms and conditions") || lowerHtml.includes("/terms")) {
      policies.terms = true;
      evidence.push("Detected Terms of Service.");
    }

    // Missing information check
    if (!company.email && !company.phone) {
      missing_information.push("No direct business email or customer support telephone listed.");
    }
    if (!policies.refund && !policies.return) {
      missing_information.push("No clear return or refund policy found on website.");
    }
    if (!policies.privacy || !policies.terms) {
      missing_information.push("Missing standard legal terms or privacy policy.");
    }

    return {
      url,
      domain,
      status: "accessible",
      company,
      product,
      policies,
      evidence,
      missing_information,
      errors,
    };
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    errors.push(`Failed to reach external website (${domain}): ${msg}`);
    return {
      url,
      domain,
      status: "inaccessible",
      company,
      product,
      policies,
      evidence,
      missing_information: [`Could not access external domain ${domain} (${msg})`],
      errors,
    };
  }
}
