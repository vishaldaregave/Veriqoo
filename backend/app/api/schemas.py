"""Pydantic API schemas and response models for Phase 8A FastAPI layer."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Service health response."""
    status: str = Field(default="ok", description="Health check status")
    service: str = Field(default="LegalMetrologyAI Backend", description="Service name")
    api_version: str = Field(default="1.0.0", description="API version")


class CreateInspectionRequest(BaseModel):
    """Optional payload when creating a new inspection session."""
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata for the inspection session")
    inspection_date: str | None = Field(default=None, description="Optional date of physical inspection (YYYY-MM-DD)")


class InspectionImageResponse(BaseModel):
    """Lightweight representation of an image reference in an inspection."""
    image_id: str
    sequence: int
    added_at: str
    source_hash: str
    normalized_hash: str
    storage_path: str | None = None


class ImageUploadResponse(BaseModel):
    """Detailed metadata returned upon successful image ingestion into an inspection."""
    image_id: str
    sequence: int
    source_hash: str
    normalized_hash: str
    source_format: str
    normalized_format: str
    original_width: int
    original_height: int
    normalized_width: int
    normalized_height: int
    file_size_bytes: int
    source_file_size_bytes: int
    color_mode: str
    was_resized: bool
    was_orientation_corrected: bool
    storage_path: str | None = None


class InspectionResponse(BaseModel):
    """Complete inspection container state including image references."""
    inspection_id: str
    created_at: str
    status: str
    image_count: int
    images: list[InspectionImageResponse] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    has_report: bool = False
    owner_id: str | None = Field(default=None, description="Authenticated owner identity (UUID)")


class InspectionListResponse(BaseModel):
    """Paginated list response for user inspection history."""
    items: list[InspectionResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total count of matching inspections")
    limit: int = Field(..., description="Pagination limit")
    offset: int = Field(..., description="Pagination offset")


class RunInspectionRequest(BaseModel):
    """Parameters passed when triggering the end-to-end inspection pipeline."""
    inspection_facts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of factual declarations observed on commodity (e.g. {'fact_key': 'is_prepackaged', 'value': True})",
    )
    applicability_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Pre-evaluated or explicit applicability overrides",
    )
    target_requirements: list[str] = Field(
        default_factory=list,
        description="Target legal requirement IDs to verify against evidence (e.g. ['R-6-1-a', 'R-6-1-b'])",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Run-specific metadata",
    )


class RunInspectionResponse(BaseModel):
    """Immediate response returned when scheduling background inspection execution."""
    inspection_id: str = Field(..., description="Unique inspection identifier")
    status: str = Field(..., description="Current inspection execution status (RUNNING, COMPLETED, FAILED)")
    message: str = Field(default="Inspection execution started.", description="Human-readable status message")


class CountsResponse(BaseModel):
    """Summary counts of pipeline verification results."""
    image_count: int = 0
    evidence_count: int = 0
    applicable_requirement_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    not_visible_count: int = 0
    not_applicable_count: int = 0
    review_required_count: int = 0


class VerificationResultResponse(BaseModel):
    """Individual legal requirement verification outcome."""
    verification_id: str | None = None
    requirement_id: str
    applicability_decision_id: str | None = None
    status: str
    reason: str
    confidence: float | None = None
    review_required: bool = False
    evidence_ids: list[str] = Field(default_factory=list)
    source_observation_ids: list[str] = Field(default_factory=list)
    image_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class NormalizedBoxResponse(BaseModel):
    """Relative normalized bounding box coordinates clamped to [0.0, 1.0]."""
    x_min: float = Field(default=0.0, description="Normalized minimum X coordinate (0.0 to 1.0)")
    y_min: float = Field(default=0.0, description="Normalized minimum Y coordinate (0.0 to 1.0)")
    x_max: float = Field(default=0.0, description="Normalized maximum X coordinate (0.0 to 1.0)")
    y_max: float = Field(default=0.0, description="Normalized maximum Y coordinate (0.0 to 1.0)")


class EvidenceAnnotationResponse(BaseModel):
    """Structured visual evidence annotation highlighting compliance findings on an inspection image."""
    annotation_id: str = Field(..., description="Deterministic annotation unique identifier")
    image_id: str = Field(..., description="Target image identifier containing the evidence")
    requirement_id: str = Field(..., description="Legal requirement identifier evaluated")
    evidence_id: str = Field(..., description="Evidence candidate identifier linked to annotation")
    status: str = Field(..., description="Verification status (FAIL, REVIEW_REQUIRED)")
    annotation_type: str = Field(..., description="Visual highlight type (ERROR_HIGHLIGHT, REVIEW_HIGHLIGHT)")
    polygon: list[list[float]] = Field(default_factory=list, description="4-point polygon quadrilateral coordinates")
    bounding_box: dict[str, float] = Field(default_factory=dict, description="Pixel bounding box in normalized image space")
    normalized_box: NormalizedBoxResponse = Field(default_factory=NormalizedBoxResponse, description="Relative bounding box [0.0, 1.0]")
    label: str = Field(..., description="Human-readable statutory declaration label")
    reason: str = Field(..., description="Established verification reason / statutory defect explanation")
    confidence: float | None = Field(default=None, description="OCR / parsing confidence score")
    is_locatable: bool = Field(default=True, description="Whether visual evidence has spatial coordinates")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional annotation metadata")


class InspectionReportResponse(BaseModel):
    """Authoritative output of the unified inspection orchestrator."""
    inspection_id: str
    overall_status: str
    language: str = Field(default="en", description="Negotiated ISO 639-1 language code (en, hi, mr)")
    summary: str
    counts: CountsResponse
    verification_results: list[VerificationResultResponse] = Field(default_factory=list)
    evidence_annotations: list[EvidenceAnnotationResponse] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateShareRequest(BaseModel):
    """Payload to request creation of a shareable QR inspection report reference."""
    expires_in_seconds: int | None = Field(
        default=None,
        description="Optional duration in seconds until the share token expires",
        ge=60,
        le=2592000,  # Max 30 days
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional client metadata associated with the share record",
    )


class QRPayloadResponse(BaseModel):
    """QR code metadata payload for Flutter display or scanning."""
    url: str = Field(..., description="Full public HTTPS URL resolving the shared report")
    token_id: str = Field(..., description="Opaque share identifier (NOT the raw token)")
    format: str = Field(default="url", description="Payload format descriptor")
    version: int = Field(default=1, description="Payload schema version")


class CreateShareResponse(BaseModel):
    """Response returned upon successful creation of a report share."""
    share_id: str = Field(..., description="Unique persistent identifier for the share reference")
    inspection_id: str = Field(..., description="Referenced inspection identifier")
    qr: QRPayloadResponse = Field(..., description="Structured QR code payload")
    created_at: str = Field(..., description="Creation timestamp in ISO-8601 format")
    expires_at: str | None = Field(default=None, description="Expiration timestamp if configured")
    status: str = Field(default="ACTIVE", description="Initial share status (ACTIVE)")


class RevokeShareResponse(BaseModel):
    """Response returned upon successful revocation of a report share."""
    share_id: str = Field(..., description="Revoked share identifier")
    inspection_id: str = Field(..., description="Referenced inspection identifier")
    status: str = Field(default="REVOKED", description="Updated share status (REVOKED)")
    revoked_at: str = Field(..., description="Revocation timestamp in ISO-8601 format")


class PublicInspectionReportResponse(BaseModel):
    """Safe, sanitized public projection of an inspection report for QR scanning and public viewing."""
    report_id: str = Field(..., description="Public report identifier")
    inspection_id: str = Field(..., description="Associated inspection identifier")
    overall_status: str = Field(..., description="Overall compliance status (PASS, FAIL, REVIEW_REQUIRED)")
    language: str = Field(default="en", description="Negotiated language code (en, hi, mr)")
    summary: str = Field(..., description="Localized compliance assessment summary")
    counts: CountsResponse = Field(..., description="Summary counts of verified legal requirements")
    verification_results: list[VerificationResultResponse] = Field(
        default_factory=list,
        description="Statutory requirement verification outcomes with localized reasons",
    )
    evidence_annotations: list[EvidenceAnnotationResponse] = Field(
        default_factory=list,
        description="Visual evidence highlight annotations (preserving coordinates, omitting private storage paths)",
    )
    created_at: str = Field(..., description="Report creation timestamp in ISO-8601 format")
    share_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Public share metadata (e.g. share status, expiration)",
    )


class FieldProvenanceResponse(BaseModel):
    """Provenance origin of an extracted product declaration field."""
    evidence_id: str | None = None
    observation_id: str | None = None
    image_id: str | None = None
    confidence: float | None = None


class ExtractedProductFieldResponse(BaseModel):
    """Single extracted declaration field with provenance and conflict indicators."""
    value: Any = None
    unit: str | None = None
    provenance: list[FieldProvenanceResponse] = Field(default_factory=list)
    is_conflicting: bool = False
    conflicting_values: list[str] = Field(default_factory=list)


class ProductIdentityResponse(BaseModel):
    """Structured product and commodity identity inferred from inspection evidence."""
    brand: ExtractedProductFieldResponse | None = None
    generic_name: ExtractedProductFieldResponse | None = None
    commodity: ExtractedProductFieldResponse | None = None
    net_quantity: ExtractedProductFieldResponse | None = None
    package_type: ExtractedProductFieldResponse | None = None
    manufacturer_name: ExtractedProductFieldResponse | None = None
    manufacturer_address: ExtractedProductFieldResponse | None = None
    country_of_origin: ExtractedProductFieldResponse | None = None
    batch_number: ExtractedProductFieldResponse | None = None
    barcode: ExtractedProductFieldResponse | None = None
    declared_mrp: ExtractedProductFieldResponse | None = None
    user_entered_selling_price: float | None = None
    manufacturing_date: ExtractedProductFieldResponse | None = None
    expiry_date: ExtractedProductFieldResponse | None = None
    consumer_care: ExtractedProductFieldResponse | None = None


class ScanQualityResponse(BaseModel):
    """Deterministic quality signals of the input package capture."""
    is_acceptable: bool = True
    quality_score: float = 1.0
    issues: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ConsumerComplianceSummaryResponse(BaseModel):
    """Summary counts and outcome for consumer scan intelligence."""
    overall_status: str
    pass_count: int = 0
    fail_count: int = 0
    review_required_count: int = 0
    not_visible_count: int = 0
    not_applicable_count: int = 0
    total_evaluated: int = 0


class ConsumerScanIntelligenceResponse(BaseModel):
    """Structured consumer intelligence for 'Scan Before You Buy' workflow."""
    schema_version: str = Field(default="1.0.0", description="Intelligence schema version")
    inspection_id: str = Field(..., description="Referenced inspection identifier")
    scan_context: str = Field(default="CONSUMER", description="Scan context / actor role (CONSUMER, INSPECTOR)")
    product_identity: ProductIdentityResponse = Field(..., description="Inferred structured product identity")
    identity_confidence: str = Field(..., description="Product identity confidence level (HIGH, MEDIUM, LOW, UNKNOWN)")
    scan_quality: ScanQualityResponse = Field(..., description="Scan and photo quality evaluation")
    compliance_summary: ConsumerComplianceSummaryResponse = Field(..., description="Canonical compliance summary")
    risk_signal: str = Field(..., description="Deterministic consumer risk classification")
    risk_signal_label: str = Field(..., description="Localized risk signal display string")
    consumer_actions: list[str] = Field(default_factory=list, description="Machine enum action suggestions")
    consumer_action_labels: list[str] = Field(default_factory=list, description="Localized action guidance strings")
    missing_information: list[str] = Field(default_factory=list, description="List of unobserved mandatory declarations")
    generated_at: str = Field(..., description="Generation timestamp in ISO-8601 format")
    metadata: dict[str, Any] = Field(default_factory=dict)


# =====================================================================
# Phase U6: Consumer Compliance Result & Explanation Response Schemas
# =====================================================================

class LegalReferenceResponse(BaseModel):
    """Statutory legal reference metadata."""
    requirement_id: str = Field(..., description="Canonical requirement identifier")
    rule_number: str | None = Field(default=None, description="Official Rule citation (e.g. Rule 6(1)(e))")
    statutory_label: str | None = Field(default=None, description="Official declaration label")
    section_reference: str | None = Field(default=None, description="Statutory Act or Rules name")


class ConsumerScoreResponse(BaseModel):
    """Consumer projection of the compliance score."""
    score: float | None = Field(default=None, description="Percentage compliance score (0.0 to 100.0) or None")
    percentage: str | None = Field(default=None, description="Formatted percentage string")
    rating: str = Field(..., description="Machine rating code (e.g. FULLY_COMPLIANT, NON_COMPLIANT)")
    rating_label: str = Field(..., description="Localized rating display label")
    evaluated_requirements: int = Field(default=0, description="Total evaluated requirements")
    pass_count: int = Field(default=0)
    fail_count: int = Field(default=0)
    review_count: int = Field(default=0)
    not_visible_count: int = Field(default=0)
    not_applicable_count: int = Field(default=0)


class ConsumerFindingResponse(BaseModel):
    """Structured consumer explanation of a verified requirement finding."""
    finding_id: str = Field(..., description="Unique finding identifier")
    requirement_id: str = Field(..., description="Canonical requirement identifier")
    status: str = Field(..., description="Canonical status (PASS, FAIL, REVIEW_REQUIRED, NOT_VISIBLE)")
    consumer_title: str = Field(..., description="Consumer-friendly statutory title")
    consumer_explanation: str = Field(..., description="Clear explanation of verification outcome")
    evidence_ids: list[str] = Field(default_factory=list, description="Associated evidence IDs")
    annotation_ids: list[str] = Field(default_factory=list, description="Matching visual annotation IDs")
    legal_reference: LegalReferenceResponse | None = Field(default=None, description="Statutory citation details")
    corrective_action: str | None = Field(default=None, description="Consumer guidance suggestion")
    severity: str = Field(default="INFO", description="Finding severity (HIGH, MEDIUM, LOW, INFO)")
    severity_label: str = Field(default="Info", description="Localized severity label")


class ConsumerReportReferenceResponse(BaseModel):
    """Safe reference to underlying inspection report."""
    inspection_id: str = Field(..., description="Inspection identifier")
    image_count: int = Field(default=0)
    evidence_count: int = Field(default=0)
    applicable_requirement_count: int = Field(default=0)
    has_report: bool = Field(default=True)
    created_at: str = Field(default="")


class ConsumerComplianceResultResponse(BaseModel):
    """Authoritative consumer-facing compliance result and explanation."""
    schema_version: str = Field(default="1.0.0", description="Schema version")
    inspection_id: str = Field(..., description="Referenced inspection identifier")
    overall_result: str = Field(..., description="Consumer overall result category")
    canonical_status: str = Field(..., description="Canonical legal metrology inspection status")
    result_label: str = Field(..., description="Localized overall result label")
    summary: str = Field(..., description="Consumer summary statement")
    what_this_means: str = Field(..., description="Persona-tailored explanation")
    score: ConsumerScoreResponse = Field(..., description="Compliance score and rating")
    risk_signal: str = Field(..., description="U5 risk signal code")
    risk_signal_label: str = Field(..., description="Localized risk signal label")
    key_findings: list[ConsumerFindingResponse] = Field(default_factory=list, description="Requirement findings")
    recommended_actions: list[str] = Field(default_factory=list, description="Machine action enum codes")
    recommended_action_labels: list[str] = Field(default_factory=list, description="Localized action labels")
    limitations: list[str] = Field(default_factory=list, description="Machine limitation keys")
    limitation_labels: list[str] = Field(default_factory=list, description="Localized limitation descriptions")
    report_reference: ConsumerReportReferenceResponse = Field(..., description="Safe report reference")
    generated_at: str = Field(..., description="Generation timestamp in ISO-8601 format")
    metadata: dict[str, Any] = Field(default_factory=dict)


# =====================================================================
# Phase U7: India Compliance Heatmap Intelligence Response Schemas
# =====================================================================

class HeatmapRiskDistributionResponse(BaseModel):
    """Aggregated distribution of consumer risk signals across region."""
    high_risk_count: int = 0
    potential_issue_count: int = 0
    insufficient_evidence_count: int = 0
    identity_uncertain_count: int = 0
    no_major_issues_count: int = 0


class HeatmapIssueCategoryResponse(BaseModel):
    """Occurrence of a statutory violation category within a region."""
    category_id: str = Field(..., description="Canonical requirement identifier or category code")
    category_name: str = Field(..., description="Human-readable statutory declaration name")
    fail_count: int = Field(default=0, description="Number of failed inspection findings")
    review_count: int = Field(default=0, description="Number of review required findings")


class HeatmapCellResponse(BaseModel):
    """Aggregate compliance cell representing a State or District."""
    region_code: str = Field(..., description="Unique region code (e.g. MH, DL, MH_PUN)")
    region_name: str = Field(..., description="Canonical region display name (e.g. Maharashtra, Delhi)")
    level: str = Field(..., description="Geographic granularity (STATE, DISTRICT)")
    state_code: str = Field(..., description="Parent 2-letter state code")
    district_code: str | None = Field(default=None, description="District code if applicable")
    is_suppressed: bool = Field(default=False, description="Whether data is suppressed due to privacy threshold")
    inspection_count: int | None = Field(default=None, description="Total unique completed inspections (null if suppressed)")
    pass_count: int | None = Field(default=None, description="Inspections with PASS status (null if suppressed)")
    fail_count: int | None = Field(default=None, description="Inspections with FAIL status (null if suppressed)")
    review_required_count: int | None = Field(default=None, description="Inspections with REVIEW_REQUIRED status (null if suppressed)")
    not_visible_count: int | None = Field(default=None, description="Sum of not visible declarations (null if suppressed)")
    not_applicable_count: int | None = Field(default=None, description="Sum of not applicable declarations (null if suppressed)")
    issue_rate: float | None = Field(default=None, description="Observed inspection issue rate: FAIL / total_inspections")
    verified_pass_rate: float | None = Field(default=None, description="Observed verified pass rate: PASS / (PASS + FAIL)")
    average_compliance_score: float | None = Field(default=None, description="Average U1 score across applicable inspections")
    risk_distribution: HeatmapRiskDistributionResponse | None = Field(default=None, description="Breakdown of U5 risk signals")
    top_issue_categories: list[HeatmapIssueCategoryResponse] = Field(default_factory=list, description="Top statutory non-compliance categories")


class HeatmapSummaryResponse(BaseModel):
    """High-level national / filtered inspection statistics."""
    total_inspections: int = 0
    total_pass: int = 0
    total_fail: int = 0
    total_review_required: int = 0
    overall_issue_rate: float | None = None
    overall_verified_pass_rate: float | None = None
    average_compliance_score: float | None = None
    active_regions_count: int = 0
    suppressed_regions_count: int = 0
    unassigned_location_count: int = 0


class ComplianceHeatmapResponse(BaseModel):
    """Authoritative API response for India Compliance Heatmap Intelligence."""
    level: str = Field(..., description="Geographic level (STATE, DISTRICT)")
    time_window: str = Field(..., description="Time window requested (7d, 30d, 90d, all, custom)")
    from_time: str = Field(..., description="UTC start timestamp in ISO-8601 format")
    to_time: str = Field(..., description="UTC end timestamp in ISO-8601 format")
    generated_at: str = Field(..., description="Generation timestamp in ISO-8601 format")
    min_threshold: int = Field(default=5, description="Privacy suppression threshold applied")
    disclaimer: str = Field(..., description="Mandatory statistical and legal disclaimer")
    summary: HeatmapSummaryResponse = Field(..., description="Aggregate summary metrics")
    cells: list[HeatmapCellResponse] = Field(default_factory=list, description="Regional aggregated intelligence cells")


# =====================================================================
# Phase U8: Voice AI Response and Request Schemas
# =====================================================================

class VoiceTextQueryRequest(BaseModel):
    """Payload for text-based voice assistant query."""
    text: str = Field(..., description="User voice utterance transcript or text prompt")
    language: str | None = Field(default="en", description="Target ISO 639-1 language code (en, hi, mr)")
    inspection_id: str | None = Field(default=None, description="Optional target inspection session identifier")
    voice_session_id: str | None = Field(default=None, description="Optional conversational voice session identifier")
    synthesize_speech: bool = Field(default=False, description="Whether to synthesize speech audio via TTS")


class VoiceQueryResponse(BaseModel):
    """Authoritative API response for Voice AI assistant interactions."""
    voice_session_id: str = Field(..., description="Unique conversational voice session identifier")
    transcript: str = Field(..., description="Normalized user utterance transcript")
    language: str = Field(..., description="Negotiated response language (en, hi, mr)")
    intent: str = Field(..., description="Classified utterance intent (e.g. EXPLAIN_RESULT, EXPLAIN_SCORE)")
    response_text: str = Field(..., description="Conversational explanation generated by Veriqoo Voice AI")
    speech_audio_base64: str | None = Field(default=None, description="Base64-encoded synthesized speech audio (WAV)")
    audio_content_type: str | None = Field(default=None, description="MIME content type of speech audio")
    canonical_status: str | None = Field(default=None, description="Canonical inspection status if attached")
    inspection_id: str | None = Field(default=None, description="Referenced inspection identifier if attached")
    score: float | None = Field(default=None, description="Verified compliance score if applicable")
    risk_signal: str | None = Field(default=None, description="Consumer risk classification signal if applicable")
    references: list[str] = Field(default_factory=list, description="Statutory Legal Metrology rule citations")
    warnings: list[str] = Field(default_factory=list, description="Diagnostic warnings or limitation notes")
    provider_metadata: dict[str, Any] = Field(default_factory=dict, description="Safe provider telemetry metadata")
    generated_at: str = Field(..., description="Generation timestamp in ISO-8601 format")


# =====================================================================
# Phase U9: Authority Intelligence & Risk Prioritization Schemas
# =====================================================================

class AuthorityRiskSignalResponse(BaseModel):
    """Structured, explainable risk indicator for authority review."""
    code: str = Field(..., description="Risk signal code (e.g. REPEATED_FAILURES, HIGH_FAILURE_BURDEN)")
    severity: str = Field(..., description="Severity level (CRITICAL, HIGH, MEDIUM, LOW, INFO)")
    explanation: str = Field(..., description="Deterministic factual explanation")
    source: str = Field(..., description="Source module (U1_SCORE, U5_INTELLIGENCE, U6_FINDINGS, U7_HEATMAP, REPEAT_ANALYSIS)")
    evidence_ids: list[str] = Field(default_factory=list, description="Referenced evidence IDs")
    requirement_ids: list[str] = Field(default_factory=list, description="Referenced requirement IDs")


class AuthorityLocationResponse(BaseModel):
    """Coarse administrative location."""
    state_code: str | None = Field(default=None, description="2-letter Indian state code")
    district_code: str | None = Field(default=None, description="Standard district code")
    state_name: str | None = Field(default=None, description="State display name")
    district_name: str | None = Field(default=None, description="District display name")


class AuthorityPriorityItemResponse(BaseModel):
    """Prioritized inspection record for regulatory authority enforcement queue."""
    inspection_id: str = Field(..., description="Unique inspection identifier")
    priority: str = Field(..., description="Priority level (CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL)")
    priority_score: int = Field(..., description="Deterministic bounded priority score (0 to 100)")
    reasons: list[str] = Field(default_factory=list, description="Structured factual reasons for assigned priority")
    canonical_status: str = Field(..., description="Canonical inspection status (PASS, FAIL, REVIEW_REQUIRED, INCOMPLETE)")
    risk_signal: str = Field(..., description="Consumer scan intelligence risk signal")
    compliance_score: float | None = Field(default=None, description="Verified U1 compliance score (0.0 to 100.0)")
    rating: str | None = Field(default=None, description="U1 rating code")
    failed_requirement_count: int = Field(default=0, description="Total non-compliant statutory requirements")
    review_required_count: int = Field(default=0, description="Total requirements needing manual review")
    not_visible_count: int = Field(default=0, description="Total declarations not visible in captured views")
    risk_signals: list[AuthorityRiskSignalResponse] = Field(default_factory=list, description="Associated risk signals")
    product_summary: dict[str, Any] = Field(default_factory=dict, description="Extracted product identity fields")
    identity_confidence: str = Field(default="UNKNOWN", description="Confidence in product identity (HIGH, MEDIUM, LOW, UNKNOWN)")
    location: AuthorityLocationResponse | None = Field(default=None, description="Coarse inspection location")
    created_at: str = Field(default="", description="Session creation timestamp in ISO-8601 format")


class AuthorityPriorityQueueResponse(BaseModel):
    """Authoritative priority queue response for case management decision support."""
    total_count: int = Field(..., description="Total count of matching inspections")
    items: list[AuthorityPriorityItemResponse] = Field(default_factory=list, description="Prioritized inspections")


class TopViolationCategoryResponse(BaseModel):
    """Occurrence of statutory violation category."""
    category: str = Field(..., description="Category name or identifier")
    failure_count: int = Field(..., description="Observed non-compliance count")


class ManufacturerIntelligenceResponse(BaseModel):
    """Aggregated compliance profile for an identified manufacturer."""
    manufacturer_name: str = Field(..., description="Standardized manufacturer / packer name")
    inspection_count: int = Field(..., description="Total observed inspection samples")
    pass_count: int = Field(..., description="Total compliant inspections")
    fail_count: int = Field(..., description="Total non-compliant inspections")
    review_count: int = Field(..., description="Total inspections requiring review")
    observed_issue_rate: float = Field(..., description="Observed failure frequency: fail_count / inspection_count")
    repeat_issue_count: int = Field(..., description="Number of recurring failure samples")
    top_violation_categories: list[TopViolationCategoryResponse] = Field(default_factory=list, description="Most frequent violation categories")
    identity_confidence: str = Field(default="HIGH", description="Identity confidence level")
    trend: str = Field(default="INSUFFICIENT_DATA", description="Observed historical frequency trend (INCREASING, DECREASING, STABLE, INSUFFICIENT_DATA)")
    last_inspected_at: str | None = Field(default=None, description="Timestamp of most recent inspection")
    disclaimer: str = Field(..., description="Mandatory regulatory sample disclaimer")


class ManufacturerIntelligenceListResponse(BaseModel):
    """List response for manufacturer compliance profiles."""
    total_count: int = Field(..., description="Total tracked manufacturers")
    items: list[ManufacturerIntelligenceResponse] = Field(default_factory=list, description="Manufacturer summaries")


class ProductIntelligenceResponse(BaseModel):
    """Aggregated compliance profile for an identified product or commodity."""
    product_key: str = Field(..., description="Deterministic grouping key")
    brand: str | None = Field(default=None, description="Brand name if identified")
    generic_name: str | None = Field(default=None, description="Generic product name")
    commodity: str | None = Field(default=None, description="Legal Metrology commodity category")
    barcode: str | None = Field(default=None, description="Barcode or GTIN identifier")
    inspection_count: int = Field(default=0, description="Total observed inspection samples")
    pass_count: int = Field(default=0, description="Total compliant inspections")
    fail_count: int = Field(default=0, description="Total non-compliant inspections")
    review_count: int = Field(default=0, description="Total inspections requiring review")
    observed_issue_rate: float = Field(default=0.0, description="Observed failure frequency")
    top_violation_categories: list[TopViolationCategoryResponse] = Field(default_factory=list, description="Most frequent violation categories")
    identity_confidence: str = Field(default="HIGH", description="Identity confidence level")
    trend: str = Field(default="INSUFFICIENT_DATA", description="Observed frequency trend")
    last_inspected_at: str | None = Field(default=None, description="Timestamp of most recent inspection")


class ProductIntelligenceListResponse(BaseModel):
    """List response for product compliance profiles."""
    total_count: int = Field(..., description="Total tracked products")
    items: list[ProductIntelligenceResponse] = Field(default_factory=list, description="Product summaries")


class TopViolatedRequirementResponse(BaseModel):
    """Aggregated requirement violation frequency."""
    requirement: str = Field(..., description="Requirement title or rule citation")
    failure_count: int = Field(..., description="Total non-compliance occurrences")


class AuthorityOverviewResponse(BaseModel):
    """High-level summary metrics for authority intelligence overview dashboard."""
    total_completed_inspections: int = Field(..., description="Total unique completed inspections evaluated")
    critical_priority_count: int = Field(..., description="Inspections with CRITICAL priority")
    high_priority_count: int = Field(..., description="Inspections with HIGH priority")
    medium_priority_count: int = Field(..., description="Inspections with MEDIUM priority")
    low_priority_count: int = Field(..., description="Inspections with LOW or INFORMATIONAL priority")
    overall_observed_issue_rate: float = Field(..., description="System-wide non-compliance rate")
    active_manufacturers_tracked: int = Field(..., description="Total distinct manufacturers identified with high confidence")
    top_violated_requirements: list[TopViolatedRequirementResponse] = Field(default_factory=list, description="Most frequently violated legal requirements")
    generated_at: str = Field(..., description="Generation timestamp in ISO-8601 format")


# =====================================================================
# Phase U10: Consumer -> Authority Action Bridge Schemas
# =====================================================================

class CreateConsumerReportRequest(BaseModel):
    """Request body for submitting a consumer inspection report to authorities."""
    consumer_description: str | None = Field(
        default=None,
        description="Optional user-provided context or observed issue description",
        max_length=2000,
    )
    preferred_language: str | None = Field(
        default="en",
        description="Preferred language for localized explanations (en, hi, mr)",
    )
    lang: str | None = Field(
        default=None,
        description="Alternative alias for preferred_language",
    )


class ReportFindingPackageResponse(BaseModel):
    """Evidence-backed finding package within an authority consumer report."""
    finding_id: str = Field(..., description="Unique finding identifier")
    requirement_id: str = Field(..., description="Canonical requirement identifier")
    canonical_status: str = Field(..., description="Canonical status (FAIL, REVIEW_REQUIRED, NOT_VISIBLE)")
    consumer_title: str = Field(..., description="Human-readable statutory title")
    consumer_explanation: str = Field(..., description="Explanation of verification outcome")
    severity: str = Field(..., description="Severity level (HIGH, MEDIUM, LOW, INFO)")
    rule_number: str | None = Field(default=None, description="Legal rule citation")
    statutory_label: str | None = Field(default=None, description="Official statutory label")
    section_reference: str | None = Field(default=None, description="Statutory Act or Rules name")
    evidence_ids: list[str] = Field(default_factory=list, description="Associated evidence candidate IDs")
    observation_ids: list[str] = Field(default_factory=list, description="Associated OCR observation IDs")
    annotation_ids: list[str] = Field(default_factory=list, description="Associated visual annotation IDs")
    image_ids: list[str] = Field(default_factory=list, description="Referenced package image IDs")
    annotations: list[dict[str, Any]] = Field(default_factory=list, description="Visual error highlight geometries")


class ConsumerReportResponse(BaseModel):
    """Authoritative response for consumer-submitted authority report."""
    report_id: str = Field(..., description="Unique consumer report identifier")
    inspection_id: str = Field(..., description="Associated inspection identifier")
    submitted_by: str = Field(..., description="User ID of reporting consumer")
    status: str = Field(..., description="Report status (SUBMITTED, RECEIVED, UNDER_REVIEW, RESOLVED)")
    canonical_overall_status: str = Field(..., description="Canonical inspection status (FAIL, REVIEW_REQUIRED)")
    consumer_overall_result: str = Field(..., description="Consumer result category")
    consumer_description: str | None = Field(default=None, description="User-provided context description")
    product_summary: dict[str, Any] = Field(default_factory=dict, description="Extracted product identity fields")
    identity_confidence: str = Field(default="UNKNOWN", description="Product identity confidence")
    scan_quality: dict[str, Any] = Field(default_factory=dict, description="Scan quality diagnostics")
    findings: list[ReportFindingPackageResponse] = Field(default_factory=list, description="Evidence-backed non-compliance findings")
    priority_score: int = Field(default=0, description="U9 deterministic priority score (0 to 100)")
    priority_band: str = Field(default="MEDIUM", description="U9 priority band (CRITICAL, HIGH, MEDIUM, LOW)")
    priority_reasons: list[str] = Field(default_factory=list, description="Factual priority reasons")
    risk_signals: list[dict[str, Any]] = Field(default_factory=list, description="Categorical risk signals")
    location: dict[str, Any] | None = Field(default=None, description="Coarse inspection location")
    inspection_created_at: str = Field(default="", description="Original inspection creation timestamp")
    created_at: str = Field(..., description="Report submission timestamp in ISO-8601 format")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConsumerReportListResponse(BaseModel):
    """List of consumer-submitted reports."""
    total: int = Field(..., description="Total count of reports")
    reports: list[ConsumerReportResponse] = Field(default_factory=list, description="Consumer reports")


class AuthorityCaseInputResponse(BaseModel):
    """Bridge data contract for T3 Authority Case Management ingestion."""
    source_report_id: str = Field(..., description="Consumer report identifier")
    inspection_id: str = Field(..., description="Source inspection identifier")
    consumer_user_id: str = Field(..., description="Submitting consumer user identifier")
    case_type: str = Field(default="CONSUMER_GRIEVANCE", description="Authority case category")
    priority: str = Field(..., description="Authority priority band")
    priority_score: int = Field(..., description="Deterministic priority score")
    canonical_status: str = Field(..., description="Canonical inspection status")
    product_identity: dict[str, Any] = Field(default_factory=dict)
    manufacturer_name: str | None = Field(default=None)
    commodity: str | None = Field(default=None)
    brand: str | None = Field(default=None)
    barcode: str | None = Field(default=None)
    findings_count: int = Field(default=0)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    consumer_notes: str | None = Field(default=None)
    location: dict[str, Any] | None = Field(default=None)
    risk_signals: list[dict[str, Any]] = Field(default_factory=list)
    submitted_at: str = Field(..., description="Submission timestamp in ISO-8601 format")


# =====================================================================
# Offline Inspection & Sync Schemas (Phase U24)
# =====================================================================

class SyncOperationRequest(BaseModel):
    """Atomic mutation operation submitted by offline client."""
    operation_id: str = Field(..., description="Unique UUID for this sync operation")
    inspection_id: str = Field(..., description="Target inspection identifier")
    entity_type: str = Field(..., description="Entity category (INSPECTION, IMAGE, OCR_OBSERVATION, EVIDENCE, FACT, APPLICABILITY, REQUIREMENT_RESULT, REPORT)")
    entity_id: str = Field(..., description="Target entity identifier")
    operation_type: str = Field(default="CREATE", description="Operation mutation verb (CREATE, UPSERT)")
    content_hash: str = Field(..., description="SHA-256 digest of canonical JSON payload")
    created_at: str = Field(..., description="Client creation ISO timestamp")
    sequence: int = Field(default=1, description="Ordering sequence")
    dependency_ids: list[str] = Field(default_factory=list, description="Operation IDs this operation depends on")
    payload: dict[str, Any] = Field(default_factory=dict, description="Entity payload data")


class SyncBatchRequest(BaseModel):
    """Batch of offline operations submitted for synchronization."""
    inspection_id: str = Field(..., description="Target inspection session identifier")
    batch_id: str | None = Field(default=None, description="Optional client-generated batch identifier")
    client_metadata: dict[str, Any] = Field(default_factory=dict, description="Client telemetry metadata")
    operations: list[SyncOperationRequest] = Field(..., description="List of sync operations (1 to 100)")


class SyncAcknowledgementResponse(BaseModel):
    """Per-operation server receipt and status acknowledgement."""
    operation_id: str = Field(..., description="Operation identifier")
    entity_id: str = Field(..., description="Target entity identifier")
    status: str = Field(..., description="Receipt status (ACKNOWLEDGED, ALREADY_APPLIED, REJECTED, RETRYABLE_FAILURE)")
    server_timestamp: str = Field(..., description="Server timestamp of acknowledgement in ISO format")
    server_version: str | None = Field(default="1.0.0", description="Server API version")
    error_code: str | None = Field(default=None, description="Machine-readable error code if rejected or pending")
    error_message: str | None = Field(default=None, description="Diagnostic error message")


class SyncBatchResponse(BaseModel):
    """Response containing acknowledgements for all submitted operations in a batch."""
    inspection_id: str = Field(..., description="Target inspection identifier")
    batch_id: str | None = Field(default=None, description="Batch identifier")
    results: list[SyncAcknowledgementResponse] = Field(default_factory=list, description="Per-operation acknowledgement receipts")


class SyncManifestResponse(BaseModel):
    """Authoritative synchronization manifest describing the current inspection state."""
    inspection_id: str = Field(..., description="Inspection identifier")
    lifecycle_status: str = Field(..., description="Domain inspection lifecycle status (COLLECTING, READY, RUNNING, COMPLETED, FAILED)")
    sync_status: str = Field(..., description="Overall sync status (DRAFT_LOCAL, SYNC_PENDING, SYNCING, SYNCED, SYNC_FAILED, REVALIDATION_REQUIRED, REVALIDATED)")
    entity_acknowledgements: list[SyncAcknowledgementResponse] = Field(default_factory=list, description="All acknowledged entity receipts")
    image_hashes: dict[str, str] = Field(default_factory=dict, description="Map of image_id to normalized/source hash")
    legal_snapshot_id: str | None = Field(default=None, description="Active or declared legal snapshot identity")
    evaluation_metadata: dict[str, Any] | None = Field(default=None, description="Evaluation provenance metadata")
    last_synced_at: str | None = Field(default=None, description="Latest server synchronization timestamp")


# =====================================================================
# Phase U24-F: Server Revalidation Response Schemas
# =====================================================================

class RevalidationComparisonResponse(BaseModel):
    """Structured diff and diagnostic comparison between offline and server evaluations."""
    offline_overall_status: str | None = Field(default=None, description="Original offline compliance status")
    server_overall_status: str = Field(..., description="Authoritative server revalidated compliance status")
    overall_status_changed: bool = Field(default=False, description="Whether the overall verdict changed")
    offline_legal_snapshot_id: str | None = Field(default=None, description="Snapshot ID used by offline device")
    server_legal_snapshot_id: str = Field(..., description="Snapshot ID used by server revalidation")
    legal_snapshot_changed: bool = Field(default=False, description="Whether snapshot migrated to newer version")
    snapshot_validation_status: str = Field(default="MATCHED", description="Snapshot validation classification (MATCHED, STALE, UNKNOWN)")
    offline_requirement_count: int = Field(default=0, description="Number of requirements evaluated offline")
    server_requirement_count: int = Field(default=0, description="Authoritative count of statutory requirements")
    missing_offline_requirements: list[str] = Field(default_factory=list, description="Statutory requirements omitted by mobile client")
    extra_offline_requirements: list[str] = Field(default_factory=list, description="Unrecognized requirements submitted by mobile client")
    requirement_status_diffs: list[dict[str, Any]] = Field(default_factory=list, description="Per-requirement status differences")
    applicability_changed: bool = Field(default=False, description="Whether applicability rules changed")
    summary_notes: list[str] = Field(default_factory=list, description="Diagnostic summary notes explaining differences")


class ServerRevalidationResponse(BaseModel):
    """Authoritative API response for server revalidation of offline inspections."""
    inspection_id: str = Field(..., description="Inspection identifier")
    overall_status: str = Field(..., description="Authoritative overall compliance status (PASS, FAIL, REVIEW_REQUIRED)")
    verification_results: list[dict[str, Any]] = Field(default_factory=list, description="Deterministic requirement verification results")
    summary: str = Field(..., description="Authoritative compliance summary text")
    counts: dict[str, int] = Field(default_factory=dict, description="Breakdown counts of requirement statuses")
    applicable_requirements: list[str] = Field(default_factory=list, description="Complete authoritative applicable requirement IDs")
    server_legal_snapshot_id: str = Field(..., description="Active server legal snapshot identifier")
    offline_legal_snapshot_id: str | None = Field(default=None, description="Original offline legal snapshot identifier")
    evaluation_metadata: dict[str, Any] = Field(default_factory=dict, description="Server evaluation provenance metadata")
    comparison: RevalidationComparisonResponse = Field(..., description="Structured comparison with offline evaluation")
    evidence_annotations: list[dict[str, Any]] = Field(default_factory=list, description="Evidence bounding box highlight overlays")
    revalidated_at: str = Field(..., description="Server revalidation timestamp in ISO-8601 format")
    content_hash: str | None = Field(default=None, description="Deterministic SHA-256 result payload digest")


# =====================================================================
# Phase U25: Evidence Trust / Chain of Custody Schemas
# =====================================================================

class EvidenceRecordResponse(BaseModel):
    """Canonical cryptographic evidence identity record."""
    evidence_id: str = Field(..., description="Unique canonical evidence identifier")
    inspection_id: str = Field(..., description="Associated inspection identifier")
    image_id: str | None = Field(default=None, description="Image storage key if applicable")
    source_id: str | None = Field(default=None, description="Source entity ID if applicable")
    content_hash: str = Field(..., description="Deterministic SHA-256 digest of exact original bytes")
    hash_algorithm: str = Field(default="SHA-256", description="Cryptographic hash algorithm")
    byte_size: int = Field(..., description="Exact raw byte size of original evidence")
    media_type: str = Field(default="image/jpeg", description="MIME content type")
    original_filename: str | None = Field(default=None, description="Original filename if captured")
    storage_reference: str | None = Field(default=None, description="Durable object storage URI or path")
    captured_at: str | None = Field(default=None, description="Device capture timestamp in ISO format")
    received_at: str = Field(..., description="Server receipt timestamp in ISO format")
    created_at: str = Field(..., description="Record creation timestamp in ISO format")
    submitted_by: str | None = Field(default=None, description="Authenticated submitter user ID or client identifier")
    source_type: str = Field(default="UPLOAD", description="Evidence ingestion source (UPLOAD, SYNC, CAMERA, CONSUMER)")
    integrity_status: str = Field(default="VERIFIED", description="Evidence integrity state (VERIFIED, UNVERIFIED, MISSING, HASH_MISMATCH, CORRUPTED, REVIEW_REQUIRED)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Immutable evidence provenance metadata")


class EvidenceChainEventResponse(BaseModel):
    """Append-oriented tamper-evident event in the evidence provenance chain."""
    event_id: str = Field(..., description="Unique event identifier")
    evidence_id: str = Field(..., description="Associated evidence identifier")
    inspection_id: str = Field(..., description="Associated inspection identifier")
    event_type: str = Field(..., description="Event lifecycle type")
    actor_type: str = Field(..., description="Actor category (SYSTEM, USER, INSPECTOR, OCR_ENGINE, REVALIDATION)")
    actor_id: str | None = Field(default=None, description="Actor subject identity if authenticated")
    timestamp: str = Field(..., description="Immutable event timestamp in ISO format")
    previous_event_hash: str | None = Field(default=None, description="SHA-256 digest of previous chain event (null for genesis)")
    event_hash: str = Field(..., description="Deterministic SHA-256 hash of this event record")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Structured canonical metadata")
    operation_id: str | None = Field(default=None, description="Originating idempotent operation identifier")


class EvidenceIntegrityResponse(BaseModel):
    """Structured cryptographic integrity verification receipt."""
    evidence_id: str = Field(..., description="Evidence identifier")
    inspection_id: str = Field(..., description="Inspection identifier")
    integrity_status: str = Field(..., description="Verified integrity state (VERIFIED, UNVERIFIED, MISSING, HASH_MISMATCH, CORRUPTED, REVIEW_REQUIRED)")
    content_hash: str = Field(..., description="Recorded original content SHA-256 hash")
    content_hash_valid: bool = Field(..., description="Whether stored or retrieved bytes match the recorded content hash")
    chain_valid: bool = Field(..., description="Whether all chain events form an unbroken tamper-evident cryptographic sequence")
    event_count: int = Field(..., description="Total provenance events in chain")
    first_event_at: str | None = Field(default=None, description="Timestamp of genesis event")
    last_event_at: str | None = Field(default=None, description="Timestamp of most recent event")
    broken_event_id: str | None = Field(default=None, description="Identifier of first broken/tampered event if any")
    error_codes: list[str] = Field(default_factory=list, description="Diagnostic error codes if verification failed")
    verified_at: str = Field(..., description="Timestamp of verification execution")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional verification telemetry and diagnostics")


class InspectionEvidenceSummaryResponse(BaseModel):
    """Comprehensive evidence summary and chain verification for an inspection."""
    inspection_id: str = Field(..., description="Inspection identifier")
    evidence_count: int = Field(..., description="Total evidence records associated with this inspection")
    verified_evidence_count: int = Field(..., description="Number of evidence records with VERIFIED integrity status")
    unverified_evidence_count: int = Field(..., description="Number of evidence records unverified or pending")
    integrity_warning_count: int = Field(..., description="Number of evidence records with hash mismatch or corruption warnings")
    chain_verification_status: str = Field(..., description="Overall chain verification verdict (VERIFIED, WARNING, BROKEN, EMPTY)")
    items: list[EvidenceRecordResponse] = Field(default_factory=list, description="List of canonical evidence records")






