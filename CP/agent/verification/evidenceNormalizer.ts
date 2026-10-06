import type {
  InstagramEvidence,
  ProductInfo,
  SellerInfo,
  WebsiteEvidence,
  MediaEvidence,
  MetaAdEvidence,
  NormalizedEvidence,
  SourceValue,
} from "./types.ts";

/**
 * Normalizes multi-source evidence into a structured comparison model.
 */
export function normalizeEvidence(
  evidence: InstagramEvidence,
  product: ProductInfo,
  seller: SellerInfo,
  website: WebsiteEvidence | null,
  media: MediaEvidence | null,
  metaAd?: MetaAdEvidence | null,
): NormalizedEvidence {
  const normalized: NormalizedEvidence = {
    product_name: [],
    brand: [],
    seller: [],
    price: [],
    manufacturer: [],
    website: [],
    contact: [],
    claims: [],
    license_certification: [],
    product_category: [],
  };

  // 1. Product Name
  if (product.name) {
    normalized.product_name.push({ source: "instagram", value: product.name, method: "caption_extraction" });
  }
  if (website?.product.name) {
    normalized.product_name.push({ source: "website", value: website.product.name, method: "metadata_parsing" });
  }
  if (media?.packaging?.product.name) {
    normalized.product_name.push({ source: "product_image", value: media.packaging.product.name, method: "OCR" });
  }
  if (metaAd?.linkTitle) {
    normalized.product_name.push({ source: "meta_ad", value: metaAd.linkTitle, method: "ad_creative_title" });
  }

  // 2. Brand
  if (product.brand) {
    normalized.brand.push({ source: "instagram", value: product.brand, method: "caption_extraction" });
  }
  if (website?.product.brand || website?.company.name) {
    normalized.brand.push({
      source: "website",
      value: (website.product.brand || website.company.name)!,
      method: "website_metadata",
    });
  }
  if (media?.packaging?.product.brand) {
    normalized.brand.push({ source: "product_image", value: media.packaging.product.brand, method: "OCR" });
  }
  if (seller.name && seller.name !== product.brand) {
    normalized.brand.push({ source: "seller", value: seller.name, method: "profile_metadata" });
  }
  if (metaAd?.advertiserName) {
    normalized.brand.push({ source: "meta_ad", value: metaAd.advertiserName, method: "meta_page_name" });
  }

  // 3. Seller / Business Entity
  if (seller.username) {
    normalized.seller.push({ source: "instagram", value: `@${seller.username}`, method: "account_handle" });
  }
  if (seller.name) {
    normalized.seller.push({ source: "seller", value: seller.name, method: "display_name" });
  }
  if (website?.company.name) {
    normalized.seller.push({ source: "website", value: website.company.name, method: "company_details" });
  }
  if (media?.packaging?.manufacturer.name) {
    normalized.seller.push({ source: "product_image", value: media.packaging.manufacturer.name, method: "OCR" });
  }
  if (metaAd?.advertiserName) {
    normalized.seller.push({ source: "meta_ad", value: metaAd.advertiserName, method: "meta_ad_advertiser" });
  }

  // 4. Price / MRP
  if (product.price) {
    normalized.price.push({ source: "instagram", value: product.price, method: "caption_extraction" });
  }
  if (website?.product.price) {
    normalized.price.push({ source: "website", value: website.product.price, method: "store_catalog" });
  }
  if (media?.packaging?.product.mrp || media?.packaging?.product.price) {
    normalized.price.push({
      source: "product_image",
      value: (media.packaging.product.mrp || media.packaging.product.price)!,
      method: "OCR",
    });
  }

  // 5. Manufacturer
  if (media?.packaging?.manufacturer.name) {
    normalized.manufacturer.push({
      source: "product_image",
      value: media.packaging.manufacturer.name,
      method: "OCR",
    });
  }
  if (website?.company.name) {
    normalized.manufacturer.push({
      source: "website",
      value: website.company.name,
      method: "company_footer",
    });
  }

  // 6. Website / Domains
  for (const link of evidence.external_links) {
    normalized.website.push({ source: "instagram", value: link, method: "caption_links" });
  }
  if (website?.domain) {
    normalized.website.push({ source: "website", value: website.domain, method: "domain_inspection" });
  }
  if (media?.packaging?.websites) {
    for (const web of media.packaging.websites) {
      normalized.website.push({ source: "product_image", value: web, method: "OCR" });
    }
  }
  if (metaAd?.destinationUrl) {
    normalized.website.push({ source: "meta_ad", value: metaAd.destinationUrl, method: "ad_destination_url" });
  }

  // 7. Contact Info
  if (seller.contact) {
    normalized.contact.push({ source: "instagram", value: seller.contact, method: "caption_extraction" });
  }
  if (website?.company.email) {
    normalized.contact.push({ source: "website", value: website.company.email, method: "support_email" });
  }
  if (website?.company.phone) {
    normalized.contact.push({ source: "website", value: website.company.phone, method: "support_phone" });
  }
  if (media?.packaging?.contact_information) {
    for (const c of media.packaging.contact_information) {
      normalized.contact.push({ source: "product_image", value: c, method: "OCR" });
    }
  }

  // 8. Claims
  for (const c of evidence.claims) {
    normalized.claims.push({ source: "instagram", value: c.claim, method: "caption_claim" });
  }
  if (website?.policies.refund || website?.policies.return) {
    normalized.claims.push({ source: "website", value: "Offers Refund/Return Policy", method: "policy_check" });
  }
  if (media?.packaging?.claims) {
    for (const c of media.packaging.claims) {
      normalized.claims.push({ source: "product_image", value: c, method: "OCR" });
    }
  }
  if (metaAd?.adText) {
    normalized.claims.push({ source: "meta_ad", value: metaAd.adText, method: "ad_creative_body" });
  }

  // 9. License & Regulatory
  if (media?.packaging?.regulatory.license_numbers) {
    for (const lic of media.packaging.regulatory.license_numbers) {
      normalized.license_certification.push({ source: "product_image", value: lic, method: "OCR" });
    }
  }
  if (media?.packaging?.regulatory.certifications) {
    for (const cert of media.packaging.regulatory.certifications) {
      normalized.license_certification.push({ source: "product_image", value: cert, method: "OCR" });
    }
  }

  // 10. Product Category
  if (product.category) {
    normalized.product_category.push({ source: "instagram", value: product.category, method: "caption_category" });
  }

  return normalized;
}
