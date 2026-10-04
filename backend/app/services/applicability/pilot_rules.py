"""Phase 3C Stage 3: In-Memory Pilot Rule Package Construction Service.

Constructs exactly FIVE executable pilot RulePackage objects using the Stage 2 AuthoringService:
1. rule_6_1_a_manufacturer_identity
2. rule_6_1_a_importer_identity
3. rule_3_chapter_exemption
4. rule_26_a_small_package_exemption
5. rule_6_1_e_mrp_declaration

NON-NEGOTIABLE SAFETY CONSTRAINTS:
- In-memory only: zero rows inserted into Supabase/PostgreSQL.
- All five packages start and remain in interpretation_status = 'draft'.
- No automated approval, no automated transitions.
- Every condition and exception group has verified legal provenance.
- All source quotes are exact verbatim substrings of the linked legal provisions.
- Candidate 1 does NOT encode is_imported == false.
- Candidate 2 requires is_prepackaged == true AND is_imported == true (independent facts).
- Candidate 3 preserves all 3 distinct statutory branches of Rule 3 in an OR structure.
  * Branch A: quantity > 25 kg OR quantity > 25 litre
  * Branch B: commodity in [cement, fertilizer, agricultural_farm_produce] AND package_type == bag AND quantity > 50 kg
  * Branch C: consumer_type == institutional OR consumer_type == industrial
- Candidate 4 preserves 10g / 10ml threshold branches, does NOT use sold_by, does NOT use
  commodity_category, does NOT invent a tobacco fact or taxonomy, and does NOT implement
  commodity != tobacco as if that proves non-tobacco.
- Candidate 5 uses observed_declarations without inventing MRP-specific fact keys.
- Temporal fields: left unset (valid_from=None, valid_to=None) to prevent invented dates.
"""

from __future__ import annotations

from typing import Mapping
from uuid import uuid4

from backend.app.services.applicability.authoring import (
    AuthoringService,
    RulePackage,
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


# Exact Corpus Quotes (Verbatim substrings of legal_provisions.content):
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
# Pilot 1: Rule 6(1)(a) Manufacturer Identity
# ---------------------------------------------------------------------
def build_rule_6_1_a_manufacturer_identity(
    service: AuthoringService | None = None,
) -> RulePackage:
    """Candidate 1: Rule 6(1)(a) Manufacturer/Packer Identity Declaration.

    CRITICAL STATUTORY BOUNDARIES:
    - Base applicability: is_prepackaged == true.
    - MUST NOT contain is_imported == false (rejected universal domestic assumption).
    - Status: draft.
    - Temporal: unset (valid_from=None, valid_to=None).
    """
    svc = service or AuthoringService()
    rule_key = "rule_6_1_a_manufacturer_identity"

    rule = svc.create_rule(
        rule_key=rule_key,
        created_by="AuthoringService Stage 3 Pilot Builder",
    )
    version = svc.create_draft_version(
        rule_id=str(rule.id),
        valid_from=None,
        valid_to=None,
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
            source_reference={
                "unresolved_interpretation": (
                    "Domestic/imported scope boundary not treated as mutually exclusive "
                    "without explicit statutory text"
                )
            },
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
# Pilot 2: Rule 6(1)(a) Importer Identity
# ---------------------------------------------------------------------
def build_rule_6_1_a_importer_identity(
    service: AuthoringService | None = None,
) -> RulePackage:
    """Candidate 2: Rule 6(1)(a) Importer Declaration on Imported Goods.

    STATUTORY BOUNDARIES:
    - Applicability requires: is_prepackaged == true AND is_imported == true.
    - Both conditions are independent.
    - Does NOT require actor_role == importer.
    - Status: draft.
    - Temporal: unset (valid_from=None, valid_to=None).
    """
    svc = service or AuthoringService()
    rule_key = "rule_6_1_a_importer_identity"

    rule = svc.create_rule(
        rule_key=rule_key,
        created_by="AuthoringService Stage 3 Pilot Builder",
    )
    version = svc.create_draft_version(
        rule_id=str(rule.id),
        valid_from=None,
        valid_to=None,
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

    # 2. Independent Condition 1: is_prepackaged == True
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

    # 3. Independent Condition 2: is_imported == True
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
# Pilot 3: Rule 3 Chapter II Exemption (All Three Branches)
# ---------------------------------------------------------------------
def build_rule_3_chapter_exemption(
    service: AuthoringService | None = None,
) -> RulePackage:
    """Candidate 3: Rule 3 Chapter II Statutory Exemption.

    Preserves ALL THREE legally distinct branches in an OR structure:
    - Root Exception Group (Purpose: exception, Op: OR)
      * Branch A (Large Packages): quantity > 25 kg OR quantity > 25 litre (Op: OR)
      * Branch B (Bulk Goods in Bags): commodity in [cement, fertilizer, agricultural_farm_produce]
                                       AND package_type == bag AND quantity > 50 kg (Op: AND)
      * Branch C (Institutional/Industrial): consumer_type == institutional
                                             OR consumer_type == industrial (Op: OR)
    Status: draft.
    Temporal: unset (valid_from=None, valid_to=None).
    """
    svc = service or AuthoringService()
    rule_key = "rule_3_chapter_exemption"

    rule = svc.create_rule(
        rule_key=rule_key,
        created_by="AuthoringService Stage 3 Pilot Builder",
    )
    version = svc.create_draft_version(
        rule_id=str(rule.id),
        valid_from=None,
        valid_to=None,
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
    cond_c1_institutional = str(uuid4())
    cond_c2_industrial = str(uuid4())

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

    # 2. Root Exception Group (Purpose: exception, Op: OR connecting all 3 branches)
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

    # Branch A: Packages containing quantity > 25 kg or 25 litre (Op: OR)
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

    # Branch B: Cement, fertilizer, agricultural farm produce in bags > 50 kg (Op: AND)
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

    # Branch C: Meant for institutional consumers or industrial consumers (Op: OR)
    svc.add_condition_group(
        vid,
        ApplicabilityConditionGroup(
            id=branch_c_gid,
            rule_version_id=vid,
            parent_group_id=root_exc_gid,
            group_purpose="exception",
            boolean_operator="OR",
            sequence=3,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_c1_institutional,
            group_id=branch_c_gid,
            fact_key="consumer_type",
            operator="equals",
            expected_value="institutional",
            sequence=1,
            review_status="draft",
        ),
    )
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_c2_industrial,
            group_id=branch_c_gid,
            fact_key="consumer_type",
            operator="equals",
            expected_value="industrial",
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
            condition_id=cond_c1_institutional,
            source_role="condition",
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
            condition_id=cond_c2_industrial,
            source_role="condition",
            source_quote=QUOTE_RULE_3_C,
            review_status="draft",
        ),
    )

    pkg = svc.store.get_package(vid)
    assert pkg is not None
    return pkg


# ---------------------------------------------------------------------
# Pilot 4: Rule 26(a) Small Package Exemption
# ---------------------------------------------------------------------
def build_rule_26_a_small_package_exemption(
    service: AuthoringService | None = None,
) -> RulePackage:
    """Candidate 4: Rule 26(a) Small Package Statutory Exemption.

    CRITICAL STATUTORY BOUNDARIES:
    - Threshold: quantity <= 10 g OR quantity <= 10 ml.
    - Does NOT use sold_by.
    - Does NOT use commodity_category.
    - Does NOT create a tobacco-specific fact.
    - Does NOT implement commodity != tobacco AND commodity != tobacco_products
      (which would falsely treat arbitrary unknown commodities as non-tobacco).
    - Preserves tobacco proviso through statutory exception provenance.
    - Status: draft.
    - Temporal: unset (valid_from=None, valid_to=None).
    """
    svc = service or AuthoringService()
    rule_key = "rule_26_a_small_package_exemption"

    rule = svc.create_rule(
        rule_key=rule_key,
        created_by="AuthoringService Stage 3 Pilot Builder",
    )
    version = svc.create_draft_version(
        rule_id=str(rule.id),
        valid_from=None,
        valid_to=None,
    )
    vid = str(version.id)

    root_app_gid = str(uuid4())
    root_exc_gid = str(uuid4())

    cond_prepkg_id = str(uuid4())
    cond_qty_g_id = str(uuid4())
    cond_qty_ml_id = str(uuid4())

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

    # 2. Root Exception Group (Purpose: exception, Op: OR connecting 10g or 10ml threshold)
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
    svc.add_condition(
        vid,
        ApplicabilityCondition(
            id=cond_qty_g_id,
            group_id=root_exc_gid,
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
            group_id=root_exc_gid,
            fact_key="quantity",
            operator="less_or_equal",
            expected_value=10,
            expected_unit="ml",
            sequence=2,
            review_status="draft",
        ),
    )

    # 3. Provenance Sources
    # 3a. Rule 26(a) General Provision
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

    # 3b. Tobacco Proviso (Provision 99) Preserved Through Exception Provenance
    svc.add_rule_source(
        vid,
        ApplicabilityRuleSource(
            id=str(uuid4()),
            rule_version_id=vid,
            requirement_id=REQ_RULE_26_TOBACCO,
            provision_id=PROV_RULE_26_TOBACCO,
            condition_group_id=root_exc_gid,
            source_role="exception",
            source_quote=QUOTE_RULE_26_TOBACCO,
            source_reference={
                "unresolved_interpretation": (
                    "Tobacco proviso carveout: commodity classification ontology is unapproved; "
                    "unmapped commodities must not be treated as proven non-tobacco"
                )
            },
            review_status="draft",
        ),
    )

    pkg = svc.store.get_package(vid)
    assert pkg is not None
    return pkg


# ---------------------------------------------------------------------
# Pilot 5: Rule 6(1)(e) MRP Declaration
# ---------------------------------------------------------------------
def build_rule_6_1_e_mrp_declaration(
    service: AuthoringService | None = None,
) -> RulePackage:
    """Candidate 5: Rule 6(1)(e) Maximum Retail Price Declaration.

    STATUTORY BOUNDARIES:
    - Base applicability: is_prepackaged == true.
    - Uses observed_declarations without inventing MRP-specific fact keys.
    - Incorporates Rule 3 and Rule 26 statutory exception groups.
    - Status: draft.
    - Temporal: unset (valid_from=None, valid_to=None).
    """
    svc = service or AuthoringService()
    rule_key = "rule_6_1_e_mrp_declaration"

    rule = svc.create_rule(
        rule_key=rule_key,
        created_by="AuthoringService Stage 3 Pilot Builder",
    )
    version = svc.create_draft_version(
        rule_id=str(rule.id),
        valid_from=None,
        valid_to=None,
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


# ---------------------------------------------------------------------
# Builder: All Pilot Rule Packages
# ---------------------------------------------------------------------
def build_all_pilot_rules(
    service: AuthoringService | None = None,
) -> dict[str, RulePackage]:
    """Construct all 5 executable pilot RulePackage objects in memory (status=draft)."""
    svc = service or AuthoringService()
    return {
        "rule_6_1_a_manufacturer_identity": build_rule_6_1_a_manufacturer_identity(svc),
        "rule_6_1_a_importer_identity": build_rule_6_1_a_importer_identity(svc),
        "rule_3_chapter_exemption": build_rule_3_chapter_exemption(svc),
        "rule_26_a_small_package_exemption": build_rule_26_a_small_package_exemption(svc),
        "rule_6_1_e_mrp_declaration": build_rule_6_1_e_mrp_declaration(svc),
    }


# Backwards compatibility aliases
build_all_pilot_candidates = build_all_pilot_rules
build_candidate_1_manufacturer_identity = build_rule_6_1_a_manufacturer_identity
build_candidate_2_importer_identity = build_rule_6_1_a_importer_identity
build_candidate_3_rule_3_chapter_exemption = build_rule_3_chapter_exemption
build_candidate_4_rule_26_a_small_package_exemption = build_rule_26_a_small_package_exemption
build_candidate_5_mrp_declaration = build_rule_6_1_e_mrp_declaration
