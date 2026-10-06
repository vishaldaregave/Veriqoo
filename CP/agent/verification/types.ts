export interface InstagramSource {
  platform: "instagram";
  url: string;
  canonical_url?: string;
  shortcode?: string;
}

export interface InstagramAccount {
  username: string | null;
  display_name: string | null;
}

export interface InstagramPost {
  type: "reel" | "post" | "video" | "unknown" | null;
  caption: string | null;
  timestamp: string | null;
}

export interface ProductInfo {
  name: string | null;
  brand: string | null;
  price: string | null;
  category: string | null;
}

export interface SellerInfo {
  name: string | null;
  username: string | null;
  website: string | null;
  contact: string | null;
  verification_status?: "VERIFIED" | "PARTIALLY VERIFIED" | "UNVERIFIED";
}

export interface Claim {
  claim: string;
  source: string;
}

export interface MediaItem {
  type: "image" | "video";
  url: string;
  source: "instagram";
}

export interface InstagramEvidence {
  source: InstagramSource;
  account: InstagramAccount;
  post: InstagramPost;
  product: ProductInfo;
  seller: SellerInfo;
  claims: Claim[];
  media: MediaItem[];
  video_analysis?: "not_available" | "processed" | null;
  external_links: string[];
  evidence: string[];
  missing_information: string[];
  errors: string[];
  raw_metadata?: Record<string, unknown>;
}

export interface CompanyInfo {
  name: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
}

export interface WebsiteProductInfo {
  name: string | null;
  brand: string | null;
  price: string | null;
  description: string | null;
}

export interface WebsitePolicies {
  refund: boolean;
  return: boolean;
  shipping: boolean;
  privacy: boolean;
  terms: boolean;
}

export interface WebsiteEvidence {
  url: string;
  domain: string;
  status: "accessible" | "inaccessible" | "blocked" | "not_found";
  company: CompanyInfo;
  product: WebsiteProductInfo;
  policies: WebsitePolicies;
  evidence: string[];
  missing_information: string[];
  errors: string[];
}

export interface ExtractedFact {
  fact: string;
  source: string;
  method: string;
}

export interface PackagingProduct {
  name: string | null;
  brand: string | null;
  category: string | null;
  price: string | null;
  mrp: string | null;
}

export interface PackagingManufacturer {
  name: string | null;
  address: string | null;
  contact: string | null;
}

export interface PackagingRegulatory {
  license_numbers: string[];
  certifications: string[];
}

export interface PackagingDates {
  manufactured: string | null;
  expiry: string | null;
  best_before: string | null;
}

export interface PackagingInfo {
  product: PackagingProduct;
  manufacturer: PackagingManufacturer;
  regulatory: PackagingRegulatory;
  dates: PackagingDates;
  claims: string[];
  websites: string[];
  contact_information: string[];
  facts: ExtractedFact[];
}

export interface OcrResult {
  text: string;
  confidence: number;
  status: "success" | "partial" | "failed";
}

export interface MediaEvidence {
  media: MediaItem[];
  ocr: OcrResult | null;
  packaging: PackagingInfo | null;
  video_analysis: "not_available" | "processed" | null;
  status: "analyzed" | "not_available" | "failed";
  evidence: string[];
  errors: string[];
}

export interface MetaAdEvidence {
  status: "found" | "not_found" | "unavailable";
  libraryId?: string;
  advertiserName?: string;
  advertiserPageId?: string;
  publisherPlatforms?: string[];
  deliveryStart?: string;
  deliveryEnd?: string;
  adText?: string;
  linkTitle?: string;
  linkDescription?: string;
  adSnapshotUrl?: string;
  destinationUrl?: string;
  evidenceSource?: string;
  error?: string;
}

export type AdPressureType =
  | "extreme_discount"
  | "urgency"
  | "scarcity"
  | "authenticity_claim"
  | "authority_certification"
  | "performance_guarantee"
  | "social_proof"
  | "clickbait_hook"
  | "price_anchoring";

export interface AdPressureSignal {
  type: AdPressureType;
  text: string;
  source: "meta_ad" | "instagram_caption" | "instagram";
  meaning: string;
}

export interface AdClaimAnalysis {
  clickbait_score?: number;
  clickbait_level?: "LOW" | "MODERATE" | "HIGH" | "AGGRESSIVE";
  clickbait_flags?: string[];
  claims_detected: string[];
  ad_pressure_signals: AdPressureSignal[];
  price_claims: string[];
  authenticity_claims: string[];
  urgency_claims: string[];
  scarcity_claims: string[];
  authority_claims: string[];
  performance_claims: string[];
  social_proof_claims: string[];
  price_anchoring_claims: string[];
  pressure_signals: AdPressureSignal[];
}

export type SourceType = "instagram" | "website" | "product_image" | "seller" | "meta_ad";

export interface SourceValue {
  source: SourceType;
  value: string;
  method?: string;
  confidence?: number;
}

export interface NormalizedEvidence {
  product_name: SourceValue[];
  brand: SourceValue[];
  seller: SourceValue[];
  price: SourceValue[];
  manufacturer: SourceValue[];
  website: SourceValue[];
  contact: SourceValue[];
  claims: SourceValue[];
  license_certification: SourceValue[];
  product_category: SourceValue[];
}

export type ConsistencyRating = "MATCH" | "PARTIAL" | "MISMATCH" | "UNKNOWN";
export type PriceConsistencyRating = "MATCH" | "DIFFERENT" | "UNKNOWN";
export type ClaimsConsistencyRating = "CONSISTENT" | "INCONSISTENT" | "UNKNOWN";

export interface TrustSignal {
  signal: string;
  severity: "positive" | "high" | "medium" | "low";
  sources: SourceType[];
  meaning?: string;
}

export interface MatrixFieldResult {
  field: string;
  valuesBySource: Record<string, string | null>;
  result: ConsistencyRating;
  explanation: string;
}

export interface EvidenceCheckStatus {
  instagram: boolean;
  meta_ad?: boolean;
  website: boolean;
  product_image: boolean;
  ocr: boolean;
}

export interface TrustMatrix {
  fields: Record<string, MatrixFieldResult>;
  available_sources: SourceType[];
  evidence_check: EvidenceCheckStatus;
  trust_signals: TrustSignal[];
  risk_signals: TrustSignal[];
  missing_information: string[];
  traceable_conclusions: Array<{ conclusion: string; evidence: SourceValue[] }>;
  summary_explanation: string;
}

export interface ImageCrossCheckResult {
  image_vs_instagram: {
    brand: ConsistencyRating;
    product: ConsistencyRating;
    price: PriceConsistencyRating;
    claims: ClaimsConsistencyRating;
  };
  image_vs_website: {
    brand: ConsistencyRating;
    product: ConsistencyRating;
    price: PriceConsistencyRating;
    manufacturer: ConsistencyRating;
    contact: ConsistencyRating;
  };
  details: string[];
}

export interface ConsistencyResult {
  seller_consistency: ConsistencyRating;
  product_consistency: ConsistencyRating;
  brand_consistency: ConsistencyRating;
  price_consistency: PriceConsistencyRating;
  details: string[];
}

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";

export interface RiskAnalysisResult {
  risk_level: RiskLevel;
  confidence: number; // 0 to 100
  safety_score?: number; // 0 to 100
  clickbait_score?: number; // 0 to 100
  clickbait_level?: "LOW" | "MODERATE" | "HIGH" | "AGGRESSIVE";
  positive_signals: string[];
  risk_signals: string[];
  missing_information: string[];
  consistency_checks: string[];
  recommendation: string;
  explanation?: string;
  evidence_check?: EvidenceCheckStatus;
  trust_matrix?: TrustMatrix;
}

export interface VerificationResult {
  evidence: InstagramEvidence;
  meta_ad_evidence?: MetaAdEvidence | null;
  ad_claim_analysis?: AdClaimAnalysis | null;
  website_evidence?: WebsiteEvidence | null;
  media_evidence?: MediaEvidence | null;
  image_cross_check?: ImageCrossCheckResult | null;
  consistency?: ConsistencyResult | null;
  trust_matrix?: TrustMatrix | null;
  product: ProductInfo;
  seller: SellerInfo;
  risk: RiskAnalysisResult;
  status: "EVIDENCE_COLLECTED" | "INSUFFICIENT_EVIDENCE";
  failure_reason?: string;
}
