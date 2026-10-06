import type {
  VerificationResult,
  RiskLevel,
  SourceType,
  SourceValue,
  TrustSignal,
  MatrixFieldResult,
  MetaAdEvidence,
  AdClaimAnalysis,
} from "./types.ts";

export interface ReportSourceInfo {
  instagram_url: string;
  website_url: string | null;
}

export interface ReportProductInfo {
  name: string | null;
  brand: string | null;
  category: string | null;
  price: string | null;
  mrp: string | null;
}

export interface ReportSellerInfo {
  username: string | null;
  name: string | null;
  website: string | null;
  contact: string | null;
  address: string | null;
}

export interface ReportRiskSummary {
  level: RiskLevel;
  confidence: number;
  safety_score?: number;
  clickbait_score?: number;
  clickbait_level?: string;
}

export interface ReportEvidenceSummary {
  instagram: {
    available: boolean;
    caption: string | null;
    timestamp: string | null;
    external_links: string[];
    evidence_count: number;
  };
  meta_ad: {
    available: boolean;
    status: string;
    library_id: string | null;
    advertiser: string | null;
  };
  website: {
    available: boolean;
    domain: string | null;
    company_name: string | null;
    policies_found: string[];
  };
  product_image: {
    available: boolean;
    image_count: number;
    analyzed: boolean;
  };
  ocr: {
    available: boolean;
    status: string;
    confidence: number;
    text_snippet: string | null;
  };
}

export interface VerificationReportData {
  report_id: string;
  generated_at: string;
  source: ReportSourceInfo;
  product: ReportProductInfo;
  seller: ReportSellerInfo;
  risk: ReportRiskSummary;
  evidence: ReportEvidenceSummary;
  meta_ad_details?: MetaAdEvidence | null;
  ad_claim_analysis?: AdClaimAnalysis | null;
  source_overview: {
    instagram: "AVAILABLE" | "UNAVAILABLE";
    meta_ad: "AVAILABLE" | "UNAVAILABLE";
    website: "AVAILABLE" | "UNAVAILABLE";
    product_image: "AVAILABLE" | "UNAVAILABLE";
    ocr: "AVAILABLE" | "UNAVAILABLE";
  };
  executive_finding: string;
  consistency_matrix: Record<string, MatrixFieldResult>;
  trust_signals: TrustSignal[];
  risk_signals: TrustSignal[];
  missing_information: string[];
  traceable_conclusions: Array<{ conclusion: string; evidence: SourceValue[] }>;
  recommendation: string;
  disclaimer: string;
}

export interface GeneratedReport {
  report_id: string;
  file_path: string;
  html: string;
  data: VerificationReportData;
}
