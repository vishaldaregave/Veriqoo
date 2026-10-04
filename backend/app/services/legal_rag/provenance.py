"""Provenance verification and resolution for the Legal RAG layer (Phase 4A).

Every retrieved legal result must be traceable back to the authoritative legal corpus.
Neither LLM outputs ("Gemini says this is the rule") nor vector search results
("Vector search retrieved this") are valid statutory provenance.
"""

from __future__ import annotations

from typing import Any

from backend.app.services.legal_rag.models import LegalProvenance

FORBIDDEN_PROVENANCE_SUBSTRINGS = frozenset({
    "gemini says",
    "ai says",
    "model inferred",
    "vector search says",
    "synthetic",
    "[paraphrased]",
    "unverified assumption",
})


class ProvenanceValidationError(ValueError):
    """Raised when statutory provenance is missing, synthetic, or ungrounded."""
    pass


def validate_provenance(prov: LegalProvenance | None) -> list[str]:
    """Validate a LegalProvenance object against statutory integrity rules.

    Returns a list of validation errors.
    """
    if prov is None:
        return ["LegalProvenance is missing (None)"]

    errors: list[str] = []

    if not prov.source_identifier or not str(prov.source_identifier).strip():
        errors.append("source_identifier is empty or missing")

    if not prov.source_quote or not prov.source_quote.strip():
        errors.append("source_quote is empty; every retrieved legal entity must quote authoritative source text")
    else:
        quote_lower = prov.source_quote.lower()
        for forbidden in FORBIDDEN_PROVENANCE_SUBSTRINGS:
            if forbidden in quote_lower:
                errors.append(
                    f"source_quote contains ungrounded/synthetic marker '{forbidden}'. "
                    "Only exact statutory text is permitted."
                )

    # Document ID must be present
    if prov.document_id is None or not str(prov.document_id).strip():
        errors.append("document_id is missing from provenance")

    # At least one legal locator must be present
    has_locator = (
        prov.provision_id is not None
        or prov.schedule_id is not None
        or prov.schedule_entry_id is not None
        or prov.table_id is not None
        or prov.amendment_id is not None
    )
    if not has_locator:
        errors.append(
            "Provenance must reference at least one statutory entity "
            "(provision_id, schedule_id, schedule_entry_id, table_id, or amendment_id)"
        )

    return errors


def merge_provenance(primary: LegalProvenance, secondary: LegalProvenance) -> LegalProvenance:
    """Merge two provenance records for the same statutory requirement or provision,

    preserving all linked locators and citations without losing statutory ground.
    """
    combined_refs = dict(primary.source_reference)
    combined_refs.update(secondary.source_reference)

    # If quotes differ, preserve primary quote or combine them cleanly
    merged_quote = primary.source_quote
    if secondary.source_quote and secondary.source_quote != primary.source_quote:
        if secondary.source_quote not in merged_quote:
            merged_quote = f"{primary.source_quote} | {secondary.source_quote}"

    return LegalProvenance(
        source_identifier=primary.source_identifier,
        document_id=primary.document_id or secondary.document_id,
        provision_id=primary.provision_id or secondary.provision_id,
        rule_number=primary.rule_number or secondary.rule_number,
        sub_rule_number=primary.sub_rule_number or secondary.sub_rule_number,
        clause=primary.clause or secondary.clause,
        schedule_id=primary.schedule_id or secondary.schedule_id,
        schedule_number=primary.schedule_number or secondary.schedule_number,
        schedule_entry_id=primary.schedule_entry_id or secondary.schedule_entry_id,
        table_id=primary.table_id or secondary.table_id,
        amendment_id=primary.amendment_id or secondary.amendment_id,
        source_page=primary.source_page or secondary.source_page,
        source_page_end=primary.source_page_end or secondary.source_page_end,
        source_line_start=primary.source_line_start or secondary.source_line_start,
        source_line_end=primary.source_line_end or secondary.source_line_end,
        source_quote=merged_quote,
        source_reference=combined_refs,
    )

