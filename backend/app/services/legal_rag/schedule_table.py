"""Structured representation for Schedule Entries and Tables in Legal RAG (Phase 4A).

Statutory constraint:
Schedule entries and tables must not be treated merely as flat text paragraphs.
Preserves:
- schedule ordinal and identifier
- entry number and key
- commodity / item text
- prescribed quantities and unit sizes
- table headers and structured cell matrices
- exact source provenance
"""

from __future__ import annotations

from typing import Any

from backend.app.services.legal_rag.models import (
    LegalEntityType,
    LegalProvenance,
    LegalSearchResult,
    RankingMetadata,
    RetrievalMethod,
)


def format_schedule_entry_text(
    commodity_text: str | None,
    quantity_text: str | None,
    item_text: str | None,
    permitted_sizes: str | None,
    entry_number: str | None,
) -> str:
    """Format structured schedule entry data into a high-fidelity representation."""
    parts = []
    if entry_number:
        parts.append(f"Entry {entry_number}")
    if item_text:
        parts.append(f"Item: {item_text}")
    if commodity_text:
        parts.append(f"Commodity: {commodity_text}")
    if quantity_text:
        parts.append(f"Quantities: {quantity_text}")
    if permitted_sizes:
        parts.append(f"Permitted Package Sizes: {permitted_sizes}")
    return " | ".join(parts)


def build_schedule_entry_result(
    entry_id: str,
    source_identifier: str,
    schedule_id: str,
    schedule_number: str,
    commodity_text: str | None,
    quantity_text: str | None,
    raw_content: str,
    provenance: LegalProvenance,
    item_text: str | None = None,
    permitted_package_quantity: str | None = None,
    entry_number: str | None = None,
    cells: list[dict[str, Any]] | None = None,
    ranking: RankingMetadata | None = None,
    retrieval_method: RetrievalMethod = RetrievalMethod.EXACT_ID,
) -> LegalSearchResult:
    """Build a LegalSearchResult for a structured schedule entry."""
    formatted_text = format_schedule_entry_text(
        commodity_text=commodity_text,
        quantity_text=quantity_text,
        item_text=item_text,
        permitted_sizes=permitted_package_quantity,
        entry_number=entry_number,
    )
    if not formatted_text:
        formatted_text = raw_content

    return LegalSearchResult(
        entity_type=LegalEntityType.SCHEDULE_ENTRY,
        entity_id=entry_id,
        source_identifier=source_identifier,
        title=f"Schedule {schedule_number}, Entry {entry_number or ''}".strip(),
        relevant_text=formatted_text,
        source_quote=raw_content,
        provenance=provenance,
        ranking=ranking or RankingMetadata(),
        retrieval_method=retrieval_method,
        parent_entity_id=schedule_id,
        parent_entity_type=LegalEntityType.PROVISION,
        commodity_text=commodity_text,
        quantity_text=quantity_text or permitted_package_quantity,
        raw_cells=cells or [],
        metadata={
            "schedule_number": schedule_number,
            "entry_number": entry_number,
            "item_text": item_text,
            "permitted_package_quantity": permitted_package_quantity,
        },
    )


def build_table_result(
    table_id: str,
    source_identifier: str,
    table_identifier: str,
    title: str | None,
    headers: list[str],
    raw_content: str,
    provenance: LegalProvenance,
    schedule_id: str | None = None,
    provision_id: int | None = None,
    ranking: RankingMetadata | None = None,
    retrieval_method: RetrievalMethod = RetrievalMethod.EXACT_ID,
) -> LegalSearchResult:
    """Build a LegalSearchResult for a structured legal table."""
    return LegalSearchResult(
        entity_type=LegalEntityType.TABLE,
        entity_id=table_id,
        source_identifier=source_identifier,
        title=title or f"Table {table_identifier}",
        relevant_text=raw_content,
        source_quote=raw_content,
        provenance=provenance,
        ranking=ranking or RankingMetadata(),
        retrieval_method=retrieval_method,
        parent_entity_id=schedule_id or (str(provision_id) if provision_id else None),
        table_headers=headers,
        metadata={
            "table_identifier": table_identifier,
            "headers": headers,
        },
    )

