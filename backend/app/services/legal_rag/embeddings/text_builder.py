"""Deterministic, provenance-preserving embedding text builders for legal corpus entities (Phase 4B).

Rules:
- Strictly deterministic and reproducible
- Provenance-preserving
- No synthetic / AI-generated paraphrases
- No invented metadata or dates
- Missing optional fields are omitted rather than defaulted or guessed
"""

from __future__ import annotations

import hashlib
from typing import Any


def _get_val(obj: Any, field_name: str, default: Any = None) -> Any:
    """Retrieve field value from either dictionary or object attribute."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(field_name, default)
    return getattr(obj, field_name, default)


def compute_embedding_text_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash of canonical embedding text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_requirement_embedding_text(
    req: Any,
    provision: Any | None = None,
) -> str:
    """Build deterministic embedding representation for a legal requirement.

    Includes statutory hierarchy, normalized requirement, obligation, condition,
    exceptions, and exact source quote.
    """
    lines = ["[ENTITY: LEGAL_REQUIREMENT]"]

    # Statutory reference from parent provision or source_reference
    src_ref = _get_val(req, "source_reference", {}) or {}
    rule_num = _get_val(provision, "rule_number") or src_ref.get("rule_number")
    sub_rule = _get_val(provision, "sub_rule_number") or src_ref.get("sub_rule_number")
    clause = _get_val(provision, "clause") or src_ref.get("clause")

    if rule_num:
        rule_str = f"Rule {rule_num}"
        if sub_rule:
            rule_str += f"({sub_rule})"
        if clause:
            rule_str += f"({clause})"
        lines.append(f"Statutory Reference: {rule_str}")

    req_type = _get_val(req, "requirement_type")
    if req_type and str(req_type).strip():
        lines.append(f"Requirement Type: {str(req_type).strip()}")

    subject = _get_val(req, "subject")
    if subject and str(subject).strip():
        lines.append(f"Subject: {str(subject).strip()}")

    norm_req = _get_val(req, "normalized_requirement")
    if norm_req and str(norm_req).strip():
        lines.append(f"Normalized Requirement: {str(norm_req).strip()}")

    obligation = _get_val(req, "obligation")
    if obligation and str(obligation).strip():
        lines.append(f"Obligation: {str(obligation).strip()}")

    req_text = _get_val(req, "requirement_text")
    if req_text and str(req_text).strip() and req_text != obligation:
        lines.append(f"Statutory Text: {str(req_text).strip()}")

    cond_text = _get_val(req, "condition_text")
    if cond_text and str(cond_text).strip():
        lines.append(f"Condition: {str(cond_text).strip()}")

    exc_text = _get_val(req, "exception_text")
    if exc_text and str(exc_text).strip():
        lines.append(f"Exception: {str(exc_text).strip()}")

    src_quote = _get_val(req, "source_quote")
    if src_quote and str(src_quote).strip():
        lines.append(f'Statutory Quote: "{str(src_quote).strip()}"')

    # Effective dates: ONLY if explicitly set in corpus
    eff_from = _get_val(req, "effective_from")
    if eff_from:
        lines.append(f"Effective From: {str(eff_from)}")
    eff_to = _get_val(req, "effective_to")
    if eff_to:
        lines.append(f"Effective To: {str(eff_to)}")

    return "\n".join(lines)


def build_provision_embedding_text(prov: Any) -> str:
    """Build deterministic embedding representation for a legal provision.

    Preserves provision type, hierarchical position, title, and raw statutory text.
    """
    lines = ["[ENTITY: LEGAL_PROVISION]"]

    p_type = _get_val(prov, "provision_type")
    if p_type and str(p_type).strip():
        lines.append(f"Provision Type: {str(p_type).strip()}")

    rule_num = _get_val(prov, "rule_number")
    sub_rule = _get_val(prov, "sub_rule_number")
    clause = _get_val(prov, "clause")
    sched_num = _get_val(prov, "schedule_number")

    if rule_num:
        rule_str = f"Rule {rule_num}"
        if sub_rule:
            rule_str += f"({sub_rule})"
        if clause:
            rule_str += f"({clause})"
        lines.append(f"Rule: {rule_str}")
    elif sched_num:
        lines.append(f"Schedule: {sched_num}")

    title = _get_val(prov, "title")
    if title and str(title).strip():
        lines.append(f"Title: {str(title).strip()}")

    src_loc = _get_val(prov, "source_location")
    if src_loc and str(src_loc).strip():
        lines.append(f"Location: {str(src_loc).strip()}")

    content = _get_val(prov, "raw_content") or _get_val(prov, "content")
    if content and str(content).strip():
        lines.append("Content:")
        lines.append(str(content).strip())

    return "\n".join(lines)


def build_schedule_entry_embedding_text(
    entry: Any,
    schedule: Any | None = None,
) -> str:
    """Build deterministic embedding representation for a schedule entry.

    Preserves schedule ordinal, entry number, commodity, quantities, package sizes,
    and structured cell content.
    """
    lines = ["[ENTITY: LEGAL_SCHEDULE_ENTRY]"]

    sched_num = _get_val(schedule, "schedule_number")
    if sched_num:
        lines.append(f"Schedule: {sched_num}")

    entry_num = _get_val(entry, "entry_number")
    if entry_num and str(entry_num).strip():
        lines.append(f"Entry Number: {str(entry_num).strip()}")

    entry_key = _get_val(entry, "entry_key")
    if entry_key and str(entry_key).strip():
        lines.append(f"Entry Key: {str(entry_key).strip()}")

    entry_type = _get_val(entry, "entry_type")
    if entry_type and str(entry_type).strip():
        lines.append(f"Entry Type: {str(entry_type).strip()}")

    item_text = _get_val(entry, "item_text")
    if item_text and str(item_text).strip():
        lines.append(f"Item: {str(item_text).strip()}")

    commodity = _get_val(entry, "commodity_text")
    if commodity and str(commodity).strip():
        lines.append(f"Commodity: {str(commodity).strip()}")

    qty_text = _get_val(entry, "quantity_text")
    if qty_text and str(qty_text).strip():
        lines.append(f"Prescribed Quantities: {str(qty_text).strip()}")

    permitted = _get_val(entry, "permitted_package_quantity")
    if permitted and str(permitted).strip():
        lines.append(f"Permitted Package Sizes: {str(permitted).strip()}")

    content = _get_val(entry, "raw_content") or _get_val(entry, "normalized_content")
    if content and str(content).strip():
        lines.append("Statutory Text:")
        lines.append(str(content).strip())

    return "\n".join(lines)


def build_table_embedding_text(
    table: Any,
    schedule: Any | None = None,
) -> str:
    """Build deterministic embedding representation for a legal table.

    Preserves table identifier, headers, schedule context, and tabular content.
    """
    lines = ["[ENTITY: LEGAL_TABLE]"]

    tbl_id = _get_val(table, "table_identifier")
    if tbl_id and str(tbl_id).strip():
        lines.append(f"Table Identifier: {str(tbl_id).strip()}")

    sched_num = _get_val(schedule, "schedule_number")
    if sched_num:
        lines.append(f"Schedule: {sched_num}")

    title = _get_val(table, "title")
    if title and str(title).strip():
        lines.append(f"Title: {str(title).strip()}")

    headers = _get_val(table, "headers")
    if headers and isinstance(headers, list) and headers:
        header_str = ", ".join(str(h) for h in headers)
        lines.append(f"Headers: {header_str}")

    content = _get_val(table, "raw_content") or _get_val(table, "normalized_content")
    if content and str(content).strip():
        lines.append("Table Content:")
        lines.append(str(content).strip())

    return "\n".join(lines)


def build_amendment_embedding_text(
    amd: Any,
    affected_prov: Any | None = None,
) -> str:
    """Build deterministic embedding representation for a legal amendment.

    Preserves amendment identifier, dates (ONLY if explicitly set in corpus),
    affected provision reference, and statutory content.
    """
    lines = ["[ENTITY: LEGAL_AMENDMENT]"]

    amd_ident = _get_val(amd, "amendment_identifier")
    if amd_ident and str(amd_ident).strip():
        lines.append(f"Amendment Identifier: {str(amd_ident).strip()}")

    rule_num = _get_val(affected_prov, "rule_number")
    sub_rule = _get_val(affected_prov, "sub_rule_number")
    clause = _get_val(affected_prov, "clause")
    if rule_num:
        rule_str = f"Rule {rule_num}"
        if sub_rule:
            rule_str += f"({sub_rule})"
        if clause:
            rule_str += f"({clause})"
        lines.append(f"Affected Rule: {rule_str}")

    amd_date = _get_val(amd, "amendment_date")
    if amd_date:
        lines.append(f"Amendment Date: {str(amd_date)}")

    eff_date = _get_val(amd, "effective_date")
    if eff_date:
        lines.append(f"Effective Date: {str(eff_date)}")

    content = _get_val(amd, "raw_content") or _get_val(amd, "normalized_content")
    if content and str(content).strip():
        lines.append("Amendment Content:")
        lines.append(str(content).strip())

    return "\n".join(lines)
