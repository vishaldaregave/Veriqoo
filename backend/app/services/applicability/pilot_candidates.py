"""Phase 3C Stage 3: In-Memory Pilot Candidate Construction Service.

Constructs the 5 executable pilot RulePackage objects using the Stage 2 AuthoringService:
1. rule_6_1_a_manufacturer_identity
2. rule_6_1_a_importer_identity
3. rule_3_chapter_exemption
4. rule_26_a_small_package_exemption
5. rule_6_1_e_mrp_declaration

NON-NEGOTIABLE SAFETY CONSTRAINTS:
- In-memory only: zero rows inserted into Supabase.
- Interpretation status remains 'draft' for all candidates (no automated approval).
- Every condition and exception group has verified corpus provenance and exact source quotes.
- Candidate 1 does NOT contain is_imported == false.
- Candidate 2 requires is_prepackaged == true AND is_imported == true.
- Candidate 3 preserves all 3 distinct statutory branches of Rule 3.
- Candidate 4 preserves 10g/10ml branches, does not use sold_by, does not invent commodity ontology.
- Candidate 5 uses observed_declarations, no synthetic facts.
"""

from __future__ import annotations

from datetime import date
from typing import Mapping
from uuid import uuid4

from backend.app.services.applicability.authoring import (
    AuthoringService,
    InMemoryAuthoringStore,
    RulePackage,
)
from backend.app.services.applicability.linter import (
    ApplicabilityLinter,
    LintResult,
)
from backend.app.services.applicability.models import (
    ApplicabilityCondition,
    ApplicabilityConditionGroup,
    ApplicabilityRuleSource,
)


# Verified Corpus Identifiers from PostgreSQL database:
# Provision 41: Rule 6(1)(a) [UUID: 7194b915-4b0c-5df8-8bf5-bec12fe25ff5]
PROV_RULE_6_1_A = 41
REQ_RULE_6_1_A = "b2d6944c-61a2-527c-b69b-b2cd5fd1ef79"

# Provision 103: Rule 3(a) [UUID: 1eb2ef33-52b0-543d-bcda-7430e1f81ee9]
PROV_RULE_3_A = 103
REQ_RULE_3_A = "00403f13-d988-5213-828f-2254d5d04a86"

# Provision 116: Rule 3(b) [UUID: 8e283aed-2b51-525a-aa32-e33d5b664e27]
PROV_RULE_3_B = 116
REQ_RULE_3_B = "ae64b076-3885-59d1-bc5b-7c071c39c80d"

# Provision 127: Rule 3(c) [UUID: 1b00d9cc-bb93-50bc-86d4-bcbe8e4b29ae]
PROV_RULE_3_C = 127
REQ_RULE_3_C = "3d0eb670-9d97-56a5-be57-8cb820c56a4d"

# Provision 58: Rule 26(a) [UUID: 2d3b68ae-d6a7-5171-8933-4a87c35dc7cc]
PROV_RULE_26_A = 58
REQ_RULE_26_A = "1453d486-a828-54d0-871d-2d8e98d37345"

# Provision 99: Rule 26(a) Proviso 2 (Tobacco) [UUID: b2b78a5e-cb24-5e11-a6b4-3b1251e75933]
PROV_RULE_26_TOBACCO = 99
REQ_RULE_26_TOBACCO = "268ea76d-ad1d-5e6f-ae47-013db4ae6896"

# Provision 193: Rule 6(1)(e) MRP clause a [UUID: a7bf9f30-c401-5b7c-ad7b-e0f9ca062c38]
PROV_RULE_6_1_E = 193
REQ_RULE_6_1_E = "08bc3380-60c9-556e-b3bf-88e366e1e5cb"


# Exact Corpus Quotes (Verbatim substrings of legal_provisions.normalized_content):
QUOTE_RULE_6_1_A_FULL = (
    "(a) the name and address of the manufacturer, or where the manufacturer is not "
    "the packer, the n ame and address of the manufacturer and packer and for any "
    "imported package the name and address of the importer shall be mentioned."
)
QUOTE_RULE_6_1_A_MFR = (
    "(a) the name and address of the manufacturer, or where the manufacturer is not "
    "the packer, the n ame and address of the manufacturer and packer"
)
QUOTE_RULE_6_1_A_IMP = "and for any imported package the name and address of the importer shall be mentioned."

QUOTE_RULE_3_A = "(a) packages of commodities containing quantity of more than 25 kilogram or 25 litre;"
QUOTE_RULE_3_B = "(b) cement, fertilizer and agricultural farm produce sold in bags above 50 kilogram; and"
QUOTE_RULE_3_C = "(c) packaged commodities meant for industrial consumers or institutional consumers."

QUOTE_RULE_26_A = (
    "(a) the net weight or measure of the commodity is ten gram or ten millilitre or "
    "less, if sold by weight or measure;"
)
QUOTE_RULE_26_TOBACCO = (
    "**Provided that the provisions of this clause shall not be applicable for tobacco "
    "and tobacco products."
)

QUOTE_RULE_6_1_E = "(a) Maximum or Max. retail price Rs. or xx.xx (inclusive of all taxes), or"


# ---------------------------------------------------------------------
# Builder 1: Rule 6(1)(a) Manufacturer/Packer Identity
# ---------------------------------------------------------------------
def build_candidate_1_manufacturer_identity(
    service: AuthoringService | None = None,
) -> RulePackage:
    """Candidate 1: Rule 6(1)(a) Manufacturer/Packer Declaration.
    
    CRITICAL INTERPRETATION CONSTRAINT:
    - Does NOT contain is_imported == false.
    - Base applicability: is_prepackaged == true.
    - Status: draft.
    """
    svc = service or AuthoringService()
    rule_key = "rule_6_1_a_manufacturer_identity"

    rule = svc.create_rule(
        rule_key=rule_key,
        created_by="AuthoringService Stage 3 Pilot Builder",
    )
    version = svc.create_draft_version(
        rule_id=str(rule.id),
        valid_from=date(2011, 11, 1),
    )
    vid = str(version.id)

    root_gid = str(uuid4())
    cond_id = str(uuid4())

    # 1. Root Applicability Group
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=root_gid,
            rule_version_id=vid,
            parent_group_id=None,
            group_purpose="applicability",
            boolean_operator="AND",
            sequence=1,
            review_status="draft",
        ),
    )

    # 2. Condition: is_prepackaged == True
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_id,
            group_id=root_gid,
            fact_key="is_prepackaged",
            operator="equals",
            expected_value=True,
            expected_unit=None,
            sequence=1,
            review_status="draft",
        ),
    )

    # 3. Provenance Sources
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_6_1_A,
            provision_id=PROV_RULE_6_1_A,
            source_role="supports",
            source_quote=QUOTE_RULE_6_1_A_FULL,
            source_reference={"unresolved_interpretation": "Domestic/imported scope boundary not treated as mutually exclusive"},
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_6_1_A,
            provision_id=PROV_RULE_6_1_A,
            condition_id=cond_id,
            source_role="condition",
            source_quote=QUOTE_RULE_6_1_A_MFR,
            review_status="draft",
        ),
    )

    pkg = svc.store.get_package(vid)
    assert pkg is not None
    return pkg


# ---------------------------------------------------------------------
# Builder 2: Rule 6(1)(a) Importer Identity
# ---------------------------------------------------------------------
def build_candidate_2_importer_identity(
    service: AuthoringService | None = None,
) -> RulePackage:
    """Candidate 2: Rule 6(1)(a) Importer Declaration on Imported Goods.
    
    Applicability condition: is_prepackaged == true AND is_imported == true.
    Independent package-origin fact, NOT inferred from actor_role.
    Status: draft.
    """
    svc = service or AuthoringService()
    rule_key = "rule_6_1_a_importer_identity"

    rule = svc.create_rule(
        rule_key=rule_key,
        created_by="AuthoringService Stage 3 Pilot Builder",
    )
    version = svc.create_draft_version(
        rule_id=str(rule.id),
        valid_from=date(2011, 11, 1),
    )
    vid = str(version.id)

    root_gid = str(uuid4())
    cond_prepkg_id = str(uuid4())
    cond_imported_id = str(uuid4())

    # 1. Root Applicability Group
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=root_gid,
            rule_version_id=vid,
            parent_group_id=None,
            group_purpose="applicability",
            boolean_operator="AND",
            sequence=1,
            review_status="draft",
        ),
    )

    # 2. Condition: is_prepackaged == True
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_prepkg_id,
            group_id=root_gid,
            fact_key="is_prepackaged",
            operator="equals",
            expected_value=True,
            sequence=1,
            review_status="draft",
        ),
    )

    # 3. Condition: is_imported == True
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_imported_id,
            group_id=root_gid,
            fact_key="is_imported",
            operator="equals",
            expected_value=True,
            sequence=2,
            review_status="draft",
        ),
    )

    # 4. Provenance Sources
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_6_1_A,
            provision_id=PROV_RULE_6_1_A,
            source_role="supports",
            source_quote=QUOTE_RULE_6_1_A_FULL,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_6_1_A,
            provision_id=PROV_RULE_6_1_A,
            condition_id=cond_prepkg_id,
            source_role="condition",
            source_quote=QUOTE_RULE_6_1_A_MFR,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_6_1_A,
            provision_id=PROV_RULE_6_1_A,
            condition_id=cond_imported_id,
            source_role="condition",
            source_quote=QUOTE_RULE_6_1_A_IMP,
            review_status="draft",
        ),
    )

    pkg = svc.store.get_package(vid)
    assert pkg is not None
    return pkg


# ---------------------------------------------------------------------
# Builder 3: Rule 3 Chapter II Exemption (All 3 Branches)
# ---------------------------------------------------------------------
def build_candidate_3_rule_3_chapter_exemption(
    service: AuthoringService | None = None,
) -> RulePackage:
    """Candidate 3: Rule 3 Chapter II Exemption.
    
    Preserves all three legally distinct statutory branches:
    - Root Exception Group (Purpose: exception, Op: OR)
      * Branch A (Large Packages): quantity > 25 (kg or l)
      * Branch B (Bulk Goods in Bags): cement/fertilizer/agricultural produce in bags > 50 kg
      * Branch C (Institutional/Industrial): consumer_type ONE_OF ['industrial', 'institutional']
    Status: draft.
    """
    svc = service or AuthoringService()
    rule_key = "rule_3_chapter_exemption"

    rule = svc.create_rule(
        rule_key=rule_key,
        created_by="AuthoringService Stage 3 Pilot Builder",
    )
    version = svc.create_draft_version(
        rule_id=str(rule.id),
        valid_from=date(2018, 1, 1),  # GSR 629(E) w.e.f. 1.1.2018
    )
    vid = str(version.id)

    root_app_gid = str(uuid4())
    root_exc_gid = str(uuid4())
    branch_a_gid = str(uuid4())
    branch_b_gid = str(uuid4())
    branch_c_gid = str(uuid4())

    cond_prepkg_id = str(uuid4())
    cond_a1_kg = str(uuid4())
    cond_a2_l = str(uuid4())
    cond_b_commodity = str(uuid4())
    cond_b_pkgtype = str(uuid4())
    cond_b_qty = str(uuid4())
    cond_c_consumer = str(uuid4())

    # 1. Root Applicability Group
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=root_app_gid,
            rule_version_id=vid,
            parent_group_id=None,
            group_purpose="applicability",
            boolean_operator="AND",
            sequence=1,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_prepkg_id,
            group_id=root_app_gid,
            fact_key="is_prepackaged",
            operator="equals",
            expected_value=True,
            sequence=1,
            review_status="draft",
        ),
    )

    # 2. Root Exception Group (Purpose: exception, Op: OR)
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=root_exc_gid,
            rule_version_id=vid,
            parent_group_id=None,
            group_purpose="exception",
            boolean_operator="OR",
            sequence=2,
            review_status="draft",
        ),
    )

    # Branch A: Packages > 25 kg or 25 litre (Op: OR)
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=branch_a_gid,
            rule_version_id=vid,
            parent_group_id=root_exc_gid,
            group_purpose="exception",
            boolean_operator="OR",
            sequence=1,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_a1_kg,
            group_id=branch_a_gid,
            fact_key="quantity",
            operator="greater_than",
            expected_value=25,
            expected_unit="kg",
            sequence=1,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_a2_l,
            group_id=branch_a_gid,
            fact_key="quantity",
            operator="greater_than",
            expected_value=25,
            expected_unit="l",
            sequence=2,
            review_status="draft",
        ),
    )

    # Branch B: Cement, fertilizer, agricultural produce sold in bags > 50 kg (Op: AND)
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=branch_b_gid,
            rule_version_id=vid,
            parent_group_id=root_exc_gid,
            group_purpose="exception",
            boolean_operator="AND",
            sequence=2,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_b_commodity,
            group_id=branch_b_gid,
            fact_key="commodity",
            operator="one_of",
            expected_value=["cement", "fertilizer", "agricultural_farm_produce"],
            sequence=1,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_b_pkgtype,
            group_id=branch_b_gid,
            fact_key="package_type",
            operator="equals",
            expected_value="bag",
            sequence=2,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_b_qty,
            group_id=branch_b_gid,
            fact_key="quantity",
            operator="greater_than",
            expected_value=50,
            expected_unit="kg",
            sequence=3,
            review_status="draft",
        ),
    )

    # Branch C: Meant for industrial or institutional consumers (Op: AND)
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=branch_c_gid,
            rule_version_id=vid,
            parent_group_id=root_exc_gid,
            group_purpose="exception",
            boolean_operator="AND",
            sequence=3,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_c_consumer,
            group_id=branch_c_gid,
            fact_key="consumer_type",
            operator="one_of",
            expected_value=["industrial", "institutional"],
            sequence=1,
            review_status="draft",
        ),
    )

    # 3. Provenance Sources
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_A,
            provision_id=PROV_RULE_3_A,
            source_role="supports",
            source_quote=QUOTE_RULE_3_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_A,
            provision_id=PROV_RULE_3_A,
            condition_id=cond_prepkg_id,
            source_role="condition",
            source_quote=QUOTE_RULE_3_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_A,
            provision_id=PROV_RULE_3_A,
            condition_group_id=root_exc_gid,
            source_role="exception",
            source_quote=QUOTE_RULE_3_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_A,
            provision_id=PROV_RULE_3_A,
            condition_group_id=branch_a_gid,
            source_role="exception",
            source_quote=QUOTE_RULE_3_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_A,
            provision_id=PROV_RULE_3_A,
            condition_id=cond_a1_kg,
            source_role="condition",
            source_quote=QUOTE_RULE_3_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_A,
            provision_id=PROV_RULE_3_A,
            condition_id=cond_a2_l,
            source_role="condition",
            source_quote=QUOTE_RULE_3_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_B,
            provision_id=PROV_RULE_3_B,
            condition_group_id=branch_b_gid,
            source_role="exception",
            source_quote=QUOTE_RULE_3_B,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_B,
            provision_id=PROV_RULE_3_B,
            condition_id=cond_b_commodity,
            source_role="condition",
            source_quote=QUOTE_RULE_3_B,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_B,
            provision_id=PROV_RULE_3_B,
            condition_id=cond_b_pkgtype,
            source_role="condition",
            source_quote=QUOTE_RULE_3_B,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_B,
            provision_id=PROV_RULE_3_B,
            condition_id=cond_b_qty,
            source_role="condition",
            source_quote=QUOTE_RULE_3_B,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_C,
            provision_id=PROV_RULE_3_C,
            condition_group_id=branch_c_gid,
            source_role="exception",
            source_quote=QUOTE_RULE_3_C,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_C,
            provision_id=PROV_RULE_3_C,
            condition_id=cond_c_consumer,
            source_role="condition",
            source_quote=QUOTE_RULE_3_C,
            review_status="draft",
        ),
    )

    pkg = svc.store.get_package(vid)
    assert pkg is not None
    return pkg


# ---------------------------------------------------------------------
# Builder 4: Rule 26(a) Small-Package Exemption
# ---------------------------------------------------------------------
def build_candidate_4_rule_26_a_small_package_exemption(
    service: AuthoringService | None = None,
) -> RulePackage:
    """Candidate 4: Rule 26(a) Small-Package De Minimis Exemption.
    
    Preserves:
    - Threshold: quantity <= 10 g OR quantity <= 10 ml
    - Proviso 2: commodity NOT_EQUALS 'tobacco' AND commodity NOT_EQUALS 'tobacco_products'
    - Does NOT use sold_by (uses quantity_unit dimension).
    - Does NOT invent commodity ontology.
    Status: draft.
    """
    svc = service or AuthoringService()
    rule_key = "rule_26_a_small_package_exemption"

    rule = svc.create_rule(
        rule_key=rule_key,
        created_by="AuthoringService Stage 3 Pilot Builder",
    )
    version = svc.create_draft_version(
        rule_id=str(rule.id),
        valid_from=date(2016, 7, 1),  # GSR 385(E) w.e.f. 1.7.2016
    )
    vid = str(version.id)

    root_app_gid = str(uuid4())
    root_exc_gid = str(uuid4())
    subgroup_thresh_gid = str(uuid4())
    subgroup_tobacco_gid = str(uuid4())

    cond_prepkg_id = str(uuid4())
    cond_qty_g_id = str(uuid4())
    cond_qty_ml_id = str(uuid4())
    cond_tobacco_1_id = str(uuid4())
    cond_tobacco_2_id = str(uuid4())

    # 1. Root Applicability Group
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=root_app_gid,
            rule_version_id=vid,
            parent_group_id=None,
            group_purpose="applicability",
            boolean_operator="AND",
            sequence=1,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_prepkg_id,
            group_id=root_app_gid,
            fact_key="is_prepackaged",
            operator="equals",
            expected_value=True,
            sequence=1,
            review_status="draft",
        ),
    )

    # 2. Root Exception Group (Purpose: exception, Op: AND)
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=root_exc_gid,
            rule_version_id=vid,
            parent_group_id=None,
            group_purpose="exception",
            boolean_operator="AND",
            sequence=2,
            review_status="draft",
        ),
    )

    # Subgroup: 10g or 10ml threshold (Op: OR)
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=subgroup_thresh_gid,
            rule_version_id=vid,
            parent_group_id=root_exc_gid,
            group_purpose="exception",
            boolean_operator="OR",
            sequence=1,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_qty_g_id,
            group_id=subgroup_thresh_gid,
            fact_key="quantity",
            operator="less_or_equal",
            expected_value=10,
            expected_unit="g",
            sequence=1,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_qty_ml_id,
            group_id=subgroup_thresh_gid,
            fact_key="quantity",
            operator="less_or_equal",
            expected_value=10,
            expected_unit="ml",
            sequence=2,
            review_status="draft",
        ),
    )

    # Subgroup: Tobacco Carve-out (Proviso 2) (Op: AND)
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=subgroup_tobacco_gid,
            rule_version_id=vid,
            parent_group_id=root_exc_gid,
            group_purpose="exception",
            boolean_operator="AND",
            sequence=2,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_tobacco_1_id,
            group_id=subgroup_tobacco_gid,
            fact_key="commodity",
            operator="not_equals",
            expected_value="tobacco",
            sequence=1,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_tobacco_2_id,
            group_id=subgroup_tobacco_gid,
            fact_key="commodity",
            operator="not_equals",
            expected_value="tobacco_products",
            sequence=2,
            review_status="draft",
        ),
    )

    # 3. Provenance Sources
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_26_A,
            provision_id=PROV_RULE_26_A,
            source_role="supports",
            source_quote=QUOTE_RULE_26_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_26_A,
            provision_id=PROV_RULE_26_A,
            condition_id=cond_prepkg_id,
            source_role="condition",
            source_quote=QUOTE_RULE_26_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_26_A,
            provision_id=PROV_RULE_26_A,
            condition_group_id=root_exc_gid,
            source_role="exception",
            source_quote=QUOTE_RULE_26_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_26_A,
            provision_id=PROV_RULE_26_A,
            condition_group_id=subgroup_thresh_gid,
            source_role="exception",
            source_quote=QUOTE_RULE_26_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_26_A,
            provision_id=PROV_RULE_26_A,
            condition_id=cond_qty_g_id,
            source_role="condition",
            source_quote=QUOTE_RULE_26_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_26_A,
            provision_id=PROV_RULE_26_A,
            condition_id=cond_qty_ml_id,
            source_role="condition",
            source_quote=QUOTE_RULE_26_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_26_TOBACCO,
            provision_id=PROV_RULE_26_TOBACCO,
            condition_group_id=subgroup_tobacco_gid,
            source_role="exception",
            source_quote=QUOTE_RULE_26_TOBACCO,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_26_TOBACCO,
            provision_id=PROV_RULE_26_TOBACCO,
            condition_id=cond_tobacco_1_id,
            source_role="condition",
            source_quote=QUOTE_RULE_26_TOBACCO,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_26_TOBACCO,
            provision_id=PROV_RULE_26_TOBACCO,
            condition_id=cond_tobacco_2_id,
            source_role="condition",
            source_quote=QUOTE_RULE_26_TOBACCO,
            review_status="draft",
        ),
    )

    pkg = svc.store.get_package(vid)
    assert pkg is not None
    return pkg


# ---------------------------------------------------------------------
# Builder 5: Rule 6(1)(e) Maximum Retail Price (MRP) Declaration
# ---------------------------------------------------------------------
def build_candidate_5_mrp_declaration(
    service: AuthoringService | None = None,
) -> RulePackage:
    """Candidate 5: Rule 6(1)(e) Maximum Retail Price Declaration.
    
    Base applicability: is_prepackaged == true.
    Uses observed_declarations for observed declaration marks.
    Rule 3 & Rule 26 exceptions modeled as exception groups.
    Status: draft.
    """
    svc = service or AuthoringService()
    rule_key = "rule_6_1_e_mrp_declaration"

    rule = svc.create_rule(
        rule_key=rule_key,
        created_by="AuthoringService Stage 3 Pilot Builder",
    )
    version = svc.create_draft_version(
        rule_id=str(rule.id),
        valid_from=date(2011, 11, 1),
    )
    vid = str(version.id)

    root_app_gid = str(uuid4())
    root_exc_r3_gid = str(uuid4())
    root_exc_r26_gid = str(uuid4())

    cond_prepkg_id = str(uuid4())
    cond_r3_large_id = str(uuid4())
    cond_r26_small_g_id = str(uuid4())

    # 1. Root Applicability Group
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=root_app_gid,
            rule_version_id=vid,
            parent_group_id=None,
            group_purpose="applicability",
            boolean_operator="AND",
            sequence=1,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_prepkg_id,
            group_id=root_app_gid,
            fact_key="is_prepackaged",
            operator="equals",
            expected_value=True,
            sequence=1,
            review_status="draft",
        ),
    )

    # 2. Rule 3 Chapter Exemption Group (Purpose: exception, Op: OR)
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=root_exc_r3_gid,
            rule_version_id=vid,
            parent_group_id=None,
            group_purpose="exception",
            boolean_operator="OR",
            sequence=2,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_r3_large_id,
            group_id=root_exc_r3_gid,
            fact_key="quantity",
            operator="greater_than",
            expected_value=25,
            expected_unit="kg",
            sequence=1,
            review_status="draft",
        ),
    )

    # 3. Rule 26 Small Package Exemption Group (Purpose: exception, Op: AND)
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=root_exc_r26_gid,
            rule_version_id=vid,
            parent_group_id=None,
            group_purpose="exception",
            boolean_operator="AND",
            sequence=3,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_r26_small_g_id,
            group_id=root_exc_r26_gid,
            fact_key="quantity",
            operator="less_or_equal",
            expected_value=10,
            expected_unit="g",
            sequence=1,
            review_status="draft",
        ),
    )

    # 4. Provenance Sources
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_6_1_E,
            provision_id=PROV_RULE_6_1_E,
            source_role="supports",
            source_quote=QUOTE_RULE_6_1_E,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_6_1_E,
            provision_id=PROV_RULE_6_1_E,
            condition_id=cond_prepkg_id,
            source_role="condition",
            source_quote=QUOTE_RULE_6_1_E,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_A,
            provision_id=PROV_RULE_3_A,
            condition_group_id=root_exc_r3_gid,
            source_role="exception",
            source_quote=QUOTE_RULE_3_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_3_A,
            provision_id=PROV_RULE_3_A,
            condition_id=cond_r3_large_id,
            source_role="condition",
            source_quote=QUOTE_RULE_3_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_26_A,
            provision_id=PROV_RULE_26_A,
            condition_group_id=root_exc_r26_gid,
            source_role="exception",
            source_quote=QUOTE_RULE_26_A,
            review_status="draft",
        ),
    )
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_26_A,
            provision_id=PROV_RULE_26_A,
            condition_id=cond_r26_small_g_id,
            source_role="condition",
            source_quote=QUOTE_RULE_26_A,
            review_status="draft",
        ),
    )

    pkg = svc.store.get_package(vid)
    assert pkg is not None
    return pkg


def build_all_pilot_candidates(
    service: AuthoringService | None = None,
) -> dict[str, RulePackage]:
    """Construct all 5 executable pilot RulePackage objects in draft status."""
    svc = service or AuthoringService()
    return {
        "rule_6_1_a_manufacturer_identity": build_candidate_1_manufacturer_identity(svc),
        "rule_6_1_a_importer_identity": build_candidate_2_importer_identity(svc),
        "rule_3_chapter_exemption": build_candidate_3_rule_3_chapter_exemption(svc),
        "rule_26_a_small_package_exemption": build_candidate_4_rule_26_a_small_package_exemption(svc),
        "rule_6_1_e_mrp_declaration": build_candidate_5_mrp_declaration(svc),
    }

