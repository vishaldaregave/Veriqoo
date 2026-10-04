# Phase U9 — Authority Intelligence & Risk Prioritization Architecture

## Overview & Purpose

Phase U9 introduces the **Authority Intelligence and Risk Prioritization** backend service for Veriqoo. Its primary objective is to empower enforcement officers and Legal Metrology authorities to triage, rank, and prioritize inspections deterministically based on observed non-compliance burden, risk signals, entity repeat frequencies, and geographic trends.

> **CRITICAL LEGAL NOTICE:**  
> Authority intelligence is decision support based strictly on Veriqoo observed inspection sample records. It does not independently determine legal compliance, issue statutory notices, impose penalties, blacklist manufacturers, or constitute an official enforcement action. All regulatory and legal determinations remain under human officer jurisdiction.

---

## Architectural Principles & Boundaries

1. **Non-Invasive Intelligence Layer**:  
   U9 sits strictly downstream of canonical inspection verification. It consumes canonical reports (`InspectionReport`), U1 Compliance Scores, U5 Consumer Scan Intelligence, U6 Consumer Compliance Results, and U7 Heatmap Aggregates. It never overrides or modifies canonical verification facts.
2. **Deterministic & Explainable**:  
   Priority scores (0–100 integer range) and priority bands (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFORMATIONAL`) are computed via deterministic mathematical heuristics. No non-deterministic AI calculations or unexplainable weights are used.
3. **No Automatic Enforcement**:  
   U9 never executes enforcement actions, penalty computations, or manufacturer suspensions.
4. **T3 Case-Management Separation**:  
   T3 owns case management, assignment workflows, notifications, and administrative dashboards. U9 exposes clean typed data contracts and REST endpoints that T3 consumes for triage.
5. **Zero Data Leakage & Strict Privacy**:  
   Authority endpoints require valid Supabase JWT authentication. Private consumer contact information, exact GPS coordinates, raw OCR text dumps, private storage keys, and share tokens are strictly omitted.

---

## Priority Scoring Model

The deterministic prioritizer calculates an integer score $S \in [0, 100]$:

$$S = \min\left(100, \max\left(0, B_{\text{status}} + B_{\text{burden}} + B_{\text{risk}} + P_{\text{score}} + R_{\text{repeat}} + G_{\text{geo}}\right)\right)$$

### 1. Base Status Contribution ($B_{\text{status}}$)
- `FAIL`: $+50$ points
- `REVIEW_REQUIRED`: $+25$ points
- `PASS`: $+0$ points

### 2. Finding Burden ($B_{\text{burden}}$)
- $+10$ points per `FAIL` requirement (capped at $+30$)
- $+5$ points per `REVIEW_REQUIRED` requirement (capped at $+15$)

### 3. U5 Consumer Risk Signal ($B_{\text{risk}}$)
- `HIGH_RISK_NON_COMPLIANCE`: $+10$ points
- `POTENTIAL_COMPLIANCE_ISSUE`: $+5$ points

### 4. Low Compliance Score Penalty ($P_{\text{score}}$)
- $U1 < 50.0$: $+10$ points
- $50.0 \le U1 < 75.0$: $+5$ points

### 5. Repeat Failure Cluster ($R_{\text{repeat}}$)
- $+5$ points per prior failure sample for the same manufacturer/product (capped at $+15$)
- *Note:* Repeat signals only apply when product identity confidence is `HIGH` or `MEDIUM`.

### 6. Regional Elevated Non-Compliance ($G_{\text{geo}}$)
- $+5$ points if the inspection is located in an administrative region with an observed failure rate $> 40\%$.

### Priority Bands
- **`CRITICAL`**: Score $80 - 100$
- **`HIGH`**: Score $60 - 79$
- **`MEDIUM`**: Score $35 - 59$
- **`LOW`**: Score $10 - 34$
- **`INFORMATIONAL`**: Score $0 - 9$

---

## Identity Confidence & Entity Intelligence

To prevent false grouping:
- **`HIGH` / `MEDIUM` Confidence**: Eligible for manufacturer and product compliance profiles and repeat failure clustering.
- **`LOW` / `UNKNOWN` Confidence**: Explicitly excluded from manufacturer aggregation; flagged with `PRODUCT_IDENTITY_UNCERTAIN` risk signal.

### Trend Calculation
Historical frequency trends compare the current 30-day window ($T_{\text{cur}}$) against the prior 30-day window ($T_{\text{prior}}$):
- **`INCREASING`**: Issue rate increased by $> 15\%$.
- **`DECREASING`**: Issue rate decreased by $> 15\%$.
- **`STABLE`**: Issue rate within $\pm 15\%$.
- **`INSUFFICIENT_DATA`**: Total sample size $< 3$ inspections.

---

## API Endpoints

All endpoints are prefixed with `/api/v1/authority/intelligence` and require a valid Bearer JWT.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/priorities` | Paginated priority queue with filtering (`min_priority`, `status`, `state_code`, `district_code`). |
| `GET` | `/inspections/{inspection_id}` | Detailed authority intelligence and risk explanation for a specific inspection. |
| `GET` | `/manufacturers` | Aggregated manufacturer compliance profiles with top violation categories and trends. |
| `GET` | `/products` | Aggregated commodity and brand compliance profiles. |
| `GET` | `/overview` | High-level summary metrics (priority counts, overall issue rate, top violated rules). |

---

## T3 Integration Contract

T3 Case-Management can consume the typed schemas directly:
- `AuthorityPriorityItemResponse`: For sorting officer assignment queues.
- `AuthorityRiskSignalResponse`: For badge indicators in enforcement dashboards.
- `ManufacturerIntelligenceResponse`: For manufacturer history views.
- `AuthorityOverviewResponse`: For national/regional command centers.
