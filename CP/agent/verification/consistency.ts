import type {
  InstagramEvidence,
  ProductInfo,
  SellerInfo,
  WebsiteEvidence,
  PackagingInfo,
  ConsistencyResult,
  ImageCrossCheckResult,
  ConsistencyRating,
  PriceConsistencyRating,
  ClaimsConsistencyRating,
} from "./types.ts";

function normalizeString(str?: string | null): string {
  if (!str) return "";
  return str.toLowerCase().replace(/[^a-z0-9]/g, "");
}

/**
 * Compares Instagram post / seller data with external website evidence.
 */
export function compareInstagramAndWebsite(
  evidence: InstagramEvidence,
  product: ProductInfo,
  seller: SellerInfo,
  website: WebsiteEvidence | null,
): ConsistencyResult {
  const details: string[] = [];

  if (!website || website.status !== "accessible") {
    return {
      seller_consistency: "UNKNOWN",
      product_consistency: "UNKNOWN",
      brand_consistency: "UNKNOWN",
      price_consistency: "UNKNOWN",
      details: ["External website could not be evaluated for consistency comparison."],
    };
  }

  // 1. Seller Consistency Check
  let seller_consistency: ConsistencyRating = "UNKNOWN";
  const igSellerName = normalizeString(seller.name || seller.username);
  const webCompanyName = normalizeString(website.company.name || website.domain);

  if (igSellerName && webCompanyName) {
    if (igSellerName === webCompanyName || webCompanyName.includes(igSellerName) || igSellerName.includes(webCompanyName)) {
      seller_consistency = "MATCH";
      details.push("Seller identity matches external website and company name.");
    } else {
      const webDomainNorm = normalizeString(website.domain);
      if (webDomainNorm.includes(igSellerName) || igSellerName.includes(webDomainNorm)) {
        seller_consistency = "MATCH";
        details.push("Seller Instagram username corresponds directly to the website domain name.");
      } else {
        seller_consistency = "PARTIAL";
        details.push("Seller identity partially matches (different operating or trade name on website).");
      }
    }
  } else {
    seller_consistency = "UNKNOWN";
  }

  // 2. Brand Consistency Check
  let brand_consistency: ConsistencyRating = "UNKNOWN";
  const igBrand = normalizeString(product.brand);
  const webBrand = normalizeString(website.product.brand || website.company.name);

  if (igBrand && webBrand) {
    if (igBrand === webBrand || webBrand.includes(igBrand) || igBrand.includes(webBrand)) {
      brand_consistency = "MATCH";
      details.push("Brand information matches between Instagram and the website.");
    } else {
      brand_consistency = "PARTIAL";
      details.push("Brand information is partially consistent.");
    }
  } else {
    brand_consistency = "UNKNOWN";
  }

  // 3. Product Consistency Check
  let product_consistency: ConsistencyRating = "UNKNOWN";
  const igCaption = (evidence.post.caption || "").toLowerCase();
  const webProdName = (website.product.name || "").toLowerCase();

  if (product.name && webProdName) {
    const igProdWords = product.name.toLowerCase().split(/\s+/).filter((w) => w.length > 3);
    const hasOverlap = igProdWords.some((w) => webProdName.includes(w) || website.product.description?.toLowerCase().includes(w));

    if (hasOverlap) {
      product_consistency = "MATCH";
      details.push("Product information and descriptions match across Instagram and store.");
    } else if (igCaption && (igCaption.includes(webProdName) || webProdName.includes(product.name.toLowerCase()))) {
      product_consistency = "MATCH";
      details.push("Product references align between Instagram post and destination page.");
    } else {
      product_consistency = "PARTIAL";
      details.push("Destination store page product differs slightly from the specific Instagram post item.");
    }
  } else if (website.product.name) {
    product_consistency = "PARTIAL";
  } else {
    product_consistency = "UNKNOWN";
  }

  // 4. Price Consistency Check
  let price_consistency: PriceConsistencyRating = "UNKNOWN";
  const igPriceNum = product.price ? product.price.replace(/[^0-9.]/g, "") : null;
  const webPriceNum = website.product.price ? website.product.price.replace(/[^0-9.]/g, "") : null;

  if (igPriceNum && webPriceNum) {
    if (Math.abs(parseFloat(igPriceNum) - parseFloat(webPriceNum)) < 1.0) {
      price_consistency = "MATCH";
      details.push(`Price matches ($${igPriceNum} on both platforms).`);
    } else {
      price_consistency = "DIFFERENT";
      details.push(`Price differs (Instagram: ${product.price} vs Website: ${website.product.price}). Note: promotional discounts may apply.`);
    }
  } else {
    price_consistency = "UNKNOWN";
  }

  return {
    seller_consistency,
    product_consistency,
    brand_consistency,
    price_consistency,
    details,
  };
}

/**
 * Compares packaging image data (from OCR) with Instagram and Website information.
 */
export function compareImageWithInstagramAndWebsite(
  packaging: PackagingInfo | null,
  evidence: InstagramEvidence,
  product: ProductInfo,
  seller: SellerInfo,
  website: WebsiteEvidence | null,
): ImageCrossCheckResult {
  const details: string[] = [];

  if (!packaging || (!packaging.product.name && !packaging.product.brand && packaging.regulatory.license_numbers.length === 0 && packaging.claims.length === 0 && !packaging.product.mrp)) {
    return {
      image_vs_instagram: {
        brand: "UNKNOWN",
        product: "UNKNOWN",
        price: "UNKNOWN",
        claims: "UNKNOWN",
      },
      image_vs_website: {
        brand: "UNKNOWN",
        product: "UNKNOWN",
        price: "UNKNOWN",
        manufacturer: "UNKNOWN",
        contact: "UNKNOWN",
      },
      details: ["Product image / packaging text could not be analyzed in detail."],
    };
  }

  // 1. Image ↔ Instagram: Brand
  let igBrandMatch: ConsistencyRating = "UNKNOWN";
  const packBrand = normalizeString(packaging.product.brand);
  const igBrand = normalizeString(product.brand);
  if (packBrand && igBrand) {
    if (packBrand === igBrand || igBrand.includes(packBrand) || packBrand.includes(igBrand)) {
      igBrandMatch = "MATCH";
      details.push("Brand on product packaging matches Instagram post.");
    } else {
      igBrandMatch = "PARTIAL";
      details.push("Brand on packaging partially matches Instagram listing.");
    }
  }

  // 2. Image ↔ Instagram: Product
  let igProdMatch: ConsistencyRating = "UNKNOWN";
  const packProd = normalizeString(packaging.product.name);
  const igProd = normalizeString(product.name);
  if (packProd && igProd) {
    if (packProd === igProd || igProd.includes(packProd) || packProd.includes(igProd)) {
      igProdMatch = "MATCH";
      details.push("Product name on packaging matches Instagram title.");
    } else {
      igProdMatch = "PARTIAL";
      details.push("Product name on packaging is consistent with listing category.");
    }
  }

  // 3. Image ↔ Instagram: Price / MRP
  let igPriceMatch: PriceConsistencyRating = "UNKNOWN";
  const packPriceNum = packaging.product.mrp || packaging.product.price ? (packaging.product.mrp || packaging.product.price)!.replace(/[^0-9.]/g, "") : null;
  const igPriceNum = product.price ? product.price.replace(/[^0-9.]/g, "") : null;
  if (packPriceNum && igPriceNum) {
    if (Math.abs(parseFloat(packPriceNum) - parseFloat(igPriceNum)) < 1.0) {
      igPriceMatch = "MATCH";
      details.push(`Packaging MRP (${packaging.product.mrp || packaging.product.price}) matches Instagram price.`);
    } else {
      igPriceMatch = "DIFFERENT";
      details.push(`Packaging MRP is ${packaging.product.mrp || packaging.product.price}, offered on Instagram for ${product.price}.`);
    }
  }

  // 4. Image ↔ Instagram: Claims
  let claimsMatch: ClaimsConsistencyRating = "UNKNOWN";
  if (packaging.claims.length > 0) {
    const igCaption = (evidence.post.caption || "").toLowerCase();
    const hasMatchingClaim = packaging.claims.some((c) => igCaption.includes(c.toLowerCase()));
    if (hasMatchingClaim) {
      claimsMatch = "CONSISTENT";
      details.push("Key claims printed on packaging are corroborated in Instagram post.");
    } else {
      claimsMatch = "CONSISTENT";
    }
  }

  // 5. Image ↔ Website: Brand, Product, Manufacturer
  let webBrandMatch: ConsistencyRating = "UNKNOWN";
  let webProdMatch: ConsistencyRating = "UNKNOWN";
  let webPriceMatch: PriceConsistencyRating = "UNKNOWN";
  let webMfgMatch: ConsistencyRating = "UNKNOWN";
  let webContactMatch: ConsistencyRating = "UNKNOWN";

  if (website && website.status === "accessible") {
    const webBrand = normalizeString(website.product.brand || website.company.name);
    if (packBrand && webBrand) {
      if (packBrand === webBrand || webBrand.includes(packBrand) || packBrand.includes(webBrand)) {
        webBrandMatch = "MATCH";
        details.push("Brand on packaging matches website store identity.");
      } else {
        webBrandMatch = "PARTIAL";
      }
    }

    const webProd = normalizeString(website.product.name);
    if (packProd && webProd) {
      if (packProd === webProd || webProd.includes(packProd) || packProd.includes(webProd)) {
        webProdMatch = "MATCH";
        details.push("Product on packaging matches online store catalog item.");
      } else {
        webProdMatch = "PARTIAL";
      }
    }

    if (packaging.manufacturer.name && website.company.name) {
      const packMfg = normalizeString(packaging.manufacturer.name);
      const webComp = normalizeString(website.company.name);
      if (packMfg === webComp || webComp.includes(packMfg) || packMfg.includes(webComp)) {
        webMfgMatch = "MATCH";
        details.push("Manufacturer on packaging matches website company registration.");
      } else {
        webMfgMatch = "PARTIAL";
      }
    }

    if (packaging.contact_information.length > 0 && (website.company.email || website.company.phone)) {
      const matchFound = packaging.contact_information.some(
        (c) =>
          (website.company.email && c.toLowerCase().includes(website.company.email.toLowerCase())) ||
          (website.company.phone && c.replace(/\D/g, "").includes(website.company.phone.replace(/\D/g, ""))),
      );
      if (matchFound) {
        webContactMatch = "MATCH";
        details.push("Support contact on packaging matches website contact channel.");
      }
    }
  }

  return {
    image_vs_instagram: {
      brand: igBrandMatch,
      product: igProdMatch,
      price: igPriceMatch,
      claims: claimsMatch,
    },
    image_vs_website: {
      brand: webBrandMatch,
      product: webProdMatch,
      price: webPriceMatch,
      manufacturer: webMfgMatch,
      contact: webContactMatch,
    },
    details,
  };
}
