# Phase U7 — India Compliance Heatmap Intelligence

## 1. Overview & Purpose
The India Compliance Heatmap Intelligence layer provides privacy-preserving, aggregated compliance and violation intelligence derived from completed Legal Metrology package inspections across India.

It powers macro-level analytical map visualizations (State and District level) for consumers, civil society, and regulatory authorities without exposing raw images, individual inspection records, exact GPS coordinates, or personally identifiable information (PII).

---

## 2. Statistical Precaution: Observed Evidence vs. Population Prevalence
> [!IMPORTANT]
> **Inspection Heatmap $\neq$ Population Prevalence.**
> The metrics produced by this system represent **observed inspection compliance intelligence** within the sampled/inspected corpus.
> The backend explicitly returns a statutory disclaimer and strictly formats metrics as observed rates:
> - **Observed Issue Rate**: Proportion of inspected units that failed legal requirements.
> - **Verified Pass Rate**: Proportion of conclusively evaluated units that passed all applicable declarations.
> 
> The system does NOT claim that *"X% of all products in Maharashtra are illegal"*, which would require statistically stratified population sampling.

---

## 3. Geographic Granularity & Trust Model

### Granularity Levels
1. **STATE**: Coarse aggregation grouped by 2-letter Indian State/UT code (e.g., `MH`, `DL`, `KA`, `TN`).
2. **DISTRICT**: Coarse sub-regional aggregation grouped by district identifier/name within a state.

### Coordinates and Exact Location Policy
- **Exact Coordinates (Latitude/Longitude)** are **NEVER** persisted in public schemas or returned in heatmap API responses.
- **Physical Addresses** and retailer details are **NEVER** exposed in public heatmap responses.

### Location Normalization & Confidence
Location context is modeled via `NormalizedLocationContext`:
- `country_code`: Standard `IN`
- `state_code`: Canonical 2-letter code (validated against `INDIA_STATES` registry)
- `state_name`: Official State / Union Territory name
- `district_code` / `district_name`: Coarse district identifier
- `source`: `DEVICE`, `USER_SELECTED`, `BACKEND_DERIVED`, `AUTHORITY`, `UNKNOWN`
- `confidence`: `HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`

If an inspection lacks verifiable geographic context, it is flagged as `unassigned_location` and excluded from cell-level aggregation rather than assigned arbitrarily.

---

## 4. Privacy & Suppression Threshold
To prevent k-anonymity re-identification and individual inspection probing:
- **Default Suppression Threshold**: `minimum_inspections_for_public_cell = 5`.
- Any State or District cell with fewer than 5 unique completed inspections has its counts, scores, and rates **suppressed** (`is_suppressed = true`, count fields set to `null`).
- The suppression threshold is **enforced unconditionally** on public requests and cannot be overridden by client query parameters.

---

## 5. Aggregation Semantics & Formulas

### Counting Unit
- **Unique Inspection ID (`inspection_id`)**: An inspection containing multiple images, OCR candidate tokens, or requirement results counts as exactly **ONE** inspection.
- Only inspections in `COMPLETED` lifecycle status with generated `InspectionReport` are included. `COLLECTING`, `READY`, `RUNNING`, and `FAILED` states are excluded.

### Core Formulas
$$\text{issue\_rate} = \frac{\text{FAIL Inspections}}{\text{Total Completed Inspections}}$$

$$\text{verified\_pass\_rate} = \frac{\text{PASS Inspections}}{\text{PASS Inspections} + \text{FAIL Inspections}} \quad (\text{if } \text{PASS} + \text{FAIL} > 0 \text{ else } \text{None})$$

$$\text{average\_compliance\_score} = \frac{\sum \text{U1 Inspection Scores}}{\text{Number of Scored Inspections}}$$

- `REVIEW_REQUIRED` and `NOT_VISIBLE` represent evidence limitations and are **never** counted as compliant in the pass rate denominator.
- `NOT_APPLICABLE` declarations are excluded from the statutory evaluation score.

---

## 6. Integration with U1, U5, and U6
- **U1 Score**: Aggregates the existing canonical percentage score ($0.0 - 100.0$) without modifying scoring logic.
- **U5 Risk Distribution**: Aggregates categorical risk signals:
  - `HIGH_RISK_NON_COMPLIANCE`
  - `POTENTIAL_COMPLIANCE_ISSUE`
  - `INSUFFICIENT_EVIDENCE`
  - `PRODUCT_IDENTITY_UNCERTAIN`
  - `NO_MAJOR_ISSUES_DETECTED`
- **U6 Top Issue Categories**: Ranks most frequent statutory declaration violations (e.g. Rule 6(1)(e) MRP, Rule 6(1)(a) Manufacturer/Packer, Rule 6(1)(d) Net Quantity).

---

## 7. API Specification

### Endpoint: `GET /api/v1/analytics/compliance-heatmap`
- **Query Parameters**:
  - `level` (string, optional): `STATE` (default) or `DISTRICT`
  - `time_window` (string, optional): `7d`, `30d` (default), `90d`, `all`
  - `from_date` (string, optional): ISO-8601 UTC timestamp
  - `to_date` (string, optional): ISO-8601 UTC timestamp
  - `state_code` (string, optional): 2-letter state filter (e.g. `MH`)
- **Response Shape**: `ComplianceHeatmapResponse`
  - `level`: `STATE` | `DISTRICT`
  - `time_window`: Requested or resolved window
  - `from_time`, `to_time`: Actual UTC bounds used
  - `generated_at`: UTC timestamp of generation
  - `min_threshold`: Integer (e.g. 5)
  - `disclaimer`: Statutory disclaimer string
  - `summary`: `HeatmapSummaryResponse`
  - `cells`: List of `HeatmapCellResponse`
