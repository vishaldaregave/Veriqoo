import type {
  InstagramEvidence,
  ProductInfo,
  SellerInfo,
  Claim,
} from "./types.ts";

/**
 * Extracts product details, seller info, and specific marketing/trust claims
 * from the collected Instagram evidence.
 */
export function extractProductAndSeller(evidence: InstagramEvidence): {
  product: ProductInfo;
  seller: SellerInfo;
  claims: Claim[];
} {
  const caption = evidence.post.caption || "";
  const username = evidence.account.username;
  const displayName = evidence.account.display_name;

  const product: ProductInfo = {
    name: null,
    brand: null,
    price: null,
    category: null,
  };

  const seller: SellerInfo = {
    name: displayName || username || null,
    username: username || null,
    website: evidence.external_links[0] || null,
    contact: null,
    verification_status: "UNVERIFIED",
  };

  const claims: Claim[] = [];

  if (!caption) {
    return { product, seller, claims };
  }

  // 1. Price extraction ($, ₹, Rs., USD, EUR, etc.)
  const priceRegex = /(?:[$€£₹]|Rs\.?|USD|INR|EUR)\s*(\d+(?:[.,]\d{1,2})?)|(\d+(?:[.,]\d{1,2})?)\s*(?:USD|INR|EUR|rupees|dollars)/i;
  const priceMatch = caption.match(priceRegex);
  if (priceMatch) {
    product.price = priceMatch[0].trim();
    claims.push({
      claim: `Price advertised as ${product.price}`,
      source: "Instagram caption",
    });
  }

  // 2. Promotional & discount claims
  const discountRegex = /\b(\d{1,2}%\s*(?:off|discount|sale)|flat\s*\d{1,2}%|buy\s*\d+\s*get\s*\d+)\b/gi;
  let discountMatch;
  while ((discountMatch = discountRegex.exec(caption)) !== null) {
    claims.push({
      claim: `Promotional offer: "${discountMatch[0].trim()}"`,
      source: "Instagram caption",
    });
  }

  // 3. Authenticity & trust claims
  const authenticityKeywords = [
    /100%\s*(?:genuine|authentic|original(?:\s+quality)?|pure|cotton|leather)/i,
    /(?:guaranteed|warranty|money[\s-]back\s*guarantee|certified)/i,
    /(?:official\s*store|authorized\s*dealer)/i,
    /(?:first\s*copy|master\s*copy|7a\s*quality|replica)/i,
  ];

  for (const pattern of authenticityKeywords) {
    const match = caption.match(pattern);
    if (match) {
      claims.push({
        claim: `Trust/Authenticity claim: "${match[0].trim()}"`,
        source: "Instagram caption",
      });
    }
  }

  // 4. Ordering & Contact mechanism claims
  const orderRegex = /(?:DM\s*(?:to\s*order|for\s*price|us)|link\s*in\s*bio|cash\s*on\s*delivery|cod\s*available|free\s*shipping)/gi;
  let orderMatch;
  while ((orderMatch = orderRegex.exec(caption)) !== null) {
    claims.push({
      claim: `Fulfillment/Ordering: "${orderMatch[0].trim()}"`,
      source: "Instagram caption",
    });
  }

  // 5. Contact phone numbers or emails
  const phoneRegex = /(?:whatsapp|contact|call|order|phone)?\s*[:\-]?\s*(\+?\d{1,3}[-.\s]?\d{9,12})\b/i;
  const phoneMatch = caption.match(phoneRegex);
  if (phoneMatch) {
    seller.contact = phoneMatch[1].trim();
    claims.push({
      claim: `Contact number: ${seller.contact}`,
      source: "Instagram caption",
    });
  }

  const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/;
  const emailMatch = caption.match(emailRegex);
  if (emailMatch) {
    seller.contact = seller.contact ? `${seller.contact}, ${emailMatch[0]}` : emailMatch[0];
  }

  // 6. Basic Product Name / Category Guess from first sentence or hashtags
  const firstLine = caption.split(/[\n\r.]+/)[0]?.trim();
  if (firstLine && firstLine.length > 3 && firstLine.length < 80) {
    product.name = firstLine;
  }

  // Brand deduction from account username or display name if available
  if (username) {
    product.brand = displayName || username;
  }

  // Seller verification status estimation
  if (seller.website && (seller.contact || username)) {
    seller.verification_status = "PARTIALLY VERIFIED";
  } else if (username) {
    seller.verification_status = "UNVERIFIED";
  }

  return { product, seller, claims };
}
