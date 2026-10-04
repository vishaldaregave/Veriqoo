# Legal Metrology Corpus & Retrieval Architecture

This document details the legal corpus model, database schema, hierarchy resolution, and RAG retrieval architecture implemented in Veriqoo.

---

## 1. Regulatory Framework

Veriqoo automates compliance checks against the following statutory framework of India:
1. **The Legal Metrology Act, 2009** (Act No. 1 of 2010).
2. **The Legal Metrology (Packaged Commodities) Rules, 2011** (GSR 427(E) dated 23rd June 2011).
3. **Subsequent Amendments**:
   - Packaged Commodities (Amendment) Rules, 2017 (e-commerce declarations, unit sale price).
   - Packaged Commodities (Amendment) Rules, 2021 (unit sale price standardization, date of manufacture/pack).
   - Packaged Commodities (Amendment) Rules, 2022 & 2023 (electronic products QR code declarations, garment labelling).

---

## 2. Mandatory Package Declarations (Rule 6)

Every package intended for retail sale must bear the following non-negotiable declarations under Rule 6:

| Rule Reference | Requirement Description | Validation Method |
|---|---|---|
| **Rule 6(1)(a)** | Name and complete address of the manufacturer / packer / importer | OCR Name/Entity extraction + Address verification |
| **Rule 6(1)(b)** | Common or generic name of the commodity contained | Commodity classification match |
| **Rule 6(1)(c)** | Net quantity in standard units of weight, measure, or number | Regex & OCR unit verification (First & Second Schedules) |
| **Rule 6(1)(d)** | Month and year of manufacture / packing / import | Date format parser & temporal boundary check |
| **Rule 6(1)(e)** | Maximum Retail Price (MRP) inclusive of all taxes | Currency symbol (`₹` / `Rs.`) + `incl. of all taxes` phrasing |
| **Rule 6(1)(f)** | Consumer care details (name, address, telephone, email of grievance officer) | Contact parser (email regex, phone number, physical address) |
| **Rule 6(1)(g)** | Country of origin (for imported goods) | Country entity extraction & ISO country code validation |
| **Rule 6(1)(h)** | Unit Sale Price (USP) per gram, kg, ml, litre, or piece | Price-per-unit mathematical sanity check |

---

## 3. Database Schema & Provision Hierarchy

The legal corpus is modeled relationally in PostgreSQL (Supabase) across the following core tables:

### 3.1 `legal_documents`
Represents root statutory instruments (e.g., "Legal Metrology (Packaged Commodities) Rules, 2011").
- `id`: Primary Key (UUID)
- `title`: Formal title of the enactment
- `short_title`: Common abbreviation
- `promulgation_date`: Date of gazette publication
- `effective_date`: Date enforcement commenced

### 3.2 `legal_provisions`
Structured provisions maintaining strict parent-child hierarchy:
- `id`: Primary Key (UUID / Integer)
- `document_id`: Reference to `legal_documents`
- `parent_id`: Recursive foreign key pointing to enclosing parent provision
- `sequence`: Integer sequence ordering provisions
- `hierarchy_path`: Materialized path (e.g., `rule_6/subrule_1/clause_a`)
- `provision_type`: `CHAPTER`, `SECTION`, `RULE`, `SUB_RULE`, `CLAUSE`, `SCHEDULE`, `TABLE`
- `title`: Short title of the rule or clause
- `content`: Verbatim statutory text
- `effective_from`: Start date of applicability
- `effective_to`: Date superseded by subsequent amendment (or `NULL` if currently in force)

### 3.3 `legal_rules` (Search & Embedding Projection)
Pre-computed search projection optimized for semantic vector retrieval and direct lookup:
- `id`: Unique rule identifier
- `rule_reference`: Canonical citation string (e.g., `Rule 6(1)(a)`)
- `title`: Human-readable summary
- `content`: Plaintext provision body
- `commodity_types`: Array of applicable commodity categories
- `embedding`: Vector (768 dimensions, `text-embedding-004`)

---

## 4. Applicability Engine

Not every rule applies to every package. For instance:
- **Wholesale packages** are governed by Chapter III, exempt from certain retail declarations.
- **Packages containing less than 10g or 10ml** (except tobacco/drugs) have modified declaration rules under Rule 26.
- **E-commerce marketplaces** require digital display of all mandatory declarations under Rule 6(10).

The applicability engine (`backend/app/services/applicability/`):
1. Evaluates package context (commodity type, net quantity, dimensions, distribution channel).
2. Gates out non-applicable rules using deterministic boolean operators.
3. Produces a tailored subset of `applicable_rules` to be verified for the specific product.

---

## 5. Hybrid Retrieval Pipeline (Legal RAG)

When inspecting a package, the RAG retrieval pipeline executes:
1. **Direct Lookup**: Exact citation resolution from product category and mandatory rule templates.
2. **Semantic Search**: Generates embedding for package OCR keywords and runs pgvector cosine similarity matching:
   $$\text{similarity} = 1 - (\mathbf{u} \cdot \mathbf{v})$$
3. **Graph Expansion**: Recursively pulls referenced schedules (e.g., Schedule II for permissible unit symbols, Schedule III for specified quantities).
4. **Temporal Filter**: Drops provisions where `effective_to` precedes the product packaging date.
5. **Deduplication**: Merges candidate rules, prioritizing specific clauses over generic rule headers.
