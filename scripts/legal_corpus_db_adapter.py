from __future__ import annotations

from typing import Any, Mapping


class SchemaAdapterError(ValueError):
    """Raised when a database payload does not match the deployed schema."""


PHASE1_PAYLOAD_COLUMNS = {
    "legal_documents": frozenset(
        {"source", "document_title", "document_version", "source_pdf_path", "source_hash"}
    ),
    "legal_provisions": frozenset(
        {
            "document_id",
            "parent_provision_id",
            "provision_type",
            "rule_number",
            "sub_rule_number",
            "clause",
            "schedule_number",
            "title",
            "content",
            "raw_content",
            "source_location",
            "source",
        }
    ),
}

PHASE2_PAYLOAD_COLUMNS = {
    "legal_schedules": frozenset(
        {
            "id", "source_identifier", "document_id", "schedule_number",
            "referenced_rule_number", "title", "raw_content", "normalized_content",
            "source_page", "source_page_end", "source_line_start", "source_line_end",
            "sequence", "structure_status", "source_provision_id",
            "referenced_provision_id",
        }
    ),
    "legal_schedule_entries": frozenset(
        {
            "id", "source_identifier", "schedule_id", "table_id", "parent_entry_id",
            "entry_key", "entry_number", "entry_type", "item_text", "commodity_text",
            "quantity_text", "permitted_package_quantity", "cells", "raw_content",
            "normalized_content", "source_page", "source_page_end", "source_line_start",
            "source_line_end", "sequence", "structure_status", "metadata",
        }
    ),
    "legal_tables": frozenset(
        {
            "id", "source_identifier", "document_id", "schedule_id", "provision_id",
            "table_identifier", "title", "headers", "raw_content", "normalized_content",
            "source_page", "source_page_end", "source_line_start", "source_line_end",
            "sequence", "structure_status",
        }
    ),
    "legal_amendments": frozenset(
        {
            "id", "source_identifier", "document_id", "affected_provision_id",
            "affected_schedule_id", "amendment_identifier", "amendment_date",
            "effective_date", "raw_content", "normalized_content", "source_page",
            "source_page_end", "source_line_start", "source_line_end", "sequence",
        }
    ),
    "legal_requirements": frozenset(
        {
            "id", "source_identifier", "provision_id", "schedule_entry_id",
            "requirement_type", "requirement_text", "normalized_requirement", "subject",
            "condition_text", "obligation", "exception_text", "applicability_metadata",
            "evidence_type", "source_quote", "source_reference", "sequence", "review_status",
            "effective_from", "effective_to", "is_active",
        }
    ),
}

PHASE2_TABLE_COLUMNS = {
    **PHASE1_PAYLOAD_COLUMNS,
    **PHASE2_PAYLOAD_COLUMNS,
}

CANONICAL_RECORD_COLUMNS = {
    "legal_documents": frozenset(
        {
            "id", "source_identifier", "title", "document_version", "source_type",
            "source_file", "source_hash", "jurisdiction", "publication_date",
            "effective_from", "metadata",
        }
    ),
    "legal_provisions": frozenset(
        {
            "id", "source_identifier", "document_id", "parent_id", "provision_type",
            "rule_number", "subrule_identifier", "clause_number", "title", "raw_content",
            "normalized_content", "source_page", "source_page_end", "source_line_start",
            "source_line_end", "document_line_start", "document_line_end", "hierarchy_path",
            "sequence", "amendment_metadata", "effective_from", "effective_to", "is_active",
            "applicability_metadata",
        }
    ),
    "legal_schedules": frozenset(
        {
            "id", "source_identifier", "document_id", "schedule_number",
            "referenced_rule_number", "title", "raw_content", "normalized_content",
            "source_page", "source_page_end", "source_line_start", "source_line_end",
            "sequence", "structure_status", "source_provision_id", "referenced_provision_id",
        }
    ),
    "legal_schedule_entries": PHASE2_PAYLOAD_COLUMNS["legal_schedule_entries"],
    "legal_tables": PHASE2_PAYLOAD_COLUMNS["legal_tables"],
    "legal_amendments": PHASE2_PAYLOAD_COLUMNS["legal_amendments"],
    "legal_requirements": frozenset(
        {
            "id", "source_identifier", "raw_content", "normalized_content", "provision_id",
            "schedule_entry_id", "requirement_type", "requirement_text", "normalized_requirement",
            "subject", "condition_text", "obligation", "exception_text", "applicability_metadata",
            "evidence_type", "source_quote", "source_reference", "sequence", "review_status",
            "effective_from", "effective_to", "is_active",
        }
    ),
}

CANONICAL_FIELDS_NOT_PERSISTED = {
    "legal_documents": [
        "canonical id (UUID; database identity generates bigint id)",
        "source_identifier (represented in deterministic source_hash lookup)",
        "source_type", "jurisdiction", "publication_date", "effective_from", "metadata",
    ],
    "legal_provisions": [
        "canonical id (UUID; database identity generates bigint id)",
        "source_identifier (embedded in source_location for deterministic lookup)",
        "hierarchy_path (parent relationships are persisted through parent_provision_id)",
        "sequence", "amendment_metadata (amendments are separate rows)", "effective_from",
        "effective_to", "is_active", "applicability_metadata",
        "source_page/source_page_end/source_line_start/source_line_end/document_line_start/document_line_end "
        "as separate columns (all are encoded in source_location)",
    ],
    "legal_requirements": [
        "raw_content and normalized_content keys (preserved as source_quote and normalized_requirement)",
    ],
}


def _validated(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = PHASE2_TABLE_COLUMNS.get(table)
    if allowed is None:
        raise SchemaAdapterError(f"No deployed-schema allowlist is defined for {table}")
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise SchemaAdapterError(
            f"Payload for {table} contains columns not present in the deployed schema: "
            + ", ".join(unknown)
        )
    return payload


def validate_outgoing_payload(table: str, payload: Mapping[str, Any]) -> None:
    _validated(table, dict(payload))


def _validate_canonical_record(table: str, record: Mapping[str, Any]) -> None:
    allowed = CANONICAL_RECORD_COLUMNS.get(table)
    if allowed is None:
        raise SchemaAdapterError(f"No canonical record allowlist is defined for {table}")
    unknown = sorted(set(record) - allowed)
    if unknown:
        raise SchemaAdapterError(
            f"Canonical record for {table} contains unrecognized fields: " + ", ".join(unknown)
        )


def _bigint_id(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SchemaAdapterError(f"{context} must resolve to a positive database bigint ID")
    return value


def document_source_location(record: Mapping[str, Any]) -> str:
    return f"sha256:{record['source_hash']}"


def provision_source_location(record: Mapping[str, Any], source_file: str) -> str:
    return (
        f"{source_file}#page={record['source_page']}-{record['source_page_end']}"
        f";page_line={record['source_line_start']}-{record['source_line_end']}"
        f";document_line={record['document_line_start']}-{record['document_line_end']}"
        f";source_identifier={record['source_identifier']}"
    )


def serialize_phase1_document(record: Mapping[str, Any]) -> dict[str, Any]:
    _validate_canonical_record("legal_documents", record)
    payload = {
        "source": record["source_file"],
        "document_title": record["title"],
        "document_version": record["document_version"],
        "source_pdf_path": f"assets/{record['source_file']}",
        "source_hash": record["source_hash"],
    }
    return _validated("legal_documents", payload)


def serialize_phase1_provision(
    record: Mapping[str, Any],
    document_id: int,
    parent_provision_id: int | None,
    source_file: str,
) -> dict[str, Any]:
    _validate_canonical_record("legal_provisions", record)
    payload = {
        "document_id": _bigint_id(document_id, "document_id"),
        "parent_provision_id": (
            _bigint_id(parent_provision_id, "parent_provision_id")
            if parent_provision_id is not None else None
        ),
        "provision_type": record["provision_type"],
        "rule_number": record["rule_number"],
        "sub_rule_number": record["subrule_identifier"],
        "clause": record["clause_number"],
        "schedule_number": record.get("schedule_number"),
        "title": record["title"],
        "content": record["normalized_content"],
        "raw_content": record["raw_content"],
        "source_location": provision_source_location(record, source_file),
        "source": "pdf",
    }
    return _validated("legal_provisions", payload)


def serialize_phase2_record(
    table: str,
    record: Mapping[str, Any],
    document_id: int,
    provision_ids: Mapping[str, int],
    source_file: str = "",
) -> dict[str, Any]:
    if table in PHASE1_PAYLOAD_COLUMNS:
        if table == "legal_documents":
            return serialize_phase1_document(record)
        parent_key = record.get("parent_id")
        parent_id = _resolve_provision_id(
            provision_ids, parent_key, "parent_provision_id", required=False
        )
        return serialize_phase1_provision(
            record,
            document_id,
            parent_id,
            source_file,
        )

    _validate_canonical_record(table, record)
    allowed = PHASE2_PAYLOAD_COLUMNS.get(table)
    if allowed is None:
        raise SchemaAdapterError(f"No deployed-schema allowlist is defined for {table}")
    if table == "legal_requirements":
        payload = {column: record.get(column) for column in allowed}
    else:
        payload = {column: record[column] for column in allowed if column in record}
    if table == "legal_schedules":
        payload["document_id"] = _bigint_id(document_id, "document_id")
        payload["source_provision_id"] = _resolve_provision_id(
            provision_ids, record.get("source_provision_id"), "source_provision_id"
        )
        referenced = record.get("referenced_provision_id")
        payload["referenced_provision_id"] = _resolve_provision_id(
            provision_ids, referenced, "referenced_provision_id", required=False
        )
    elif table == "legal_tables":
        payload["document_id"] = _bigint_id(document_id, "document_id")
        provision_id = record.get("provision_id")
        payload["provision_id"] = _resolve_provision_id(
            provision_ids, provision_id, "provision_id", required=False
        )
    elif table == "legal_amendments":
        payload["document_id"] = _bigint_id(document_id, "document_id")
        provision_id = record.get("affected_provision_id")
        payload["affected_provision_id"] = _resolve_provision_id(
            provision_ids, provision_id, "affected_provision_id", required=False
        )
    elif table == "legal_requirements":
        provision_id = record.get("provision_id")
        payload["provision_id"] = _resolve_provision_id(
            provision_ids, provision_id, "provision_id"
        )
    return _validated(table, payload)


def serialize_corpus_groups(
    corpus: Any,
    document_id: int,
    provision_ids: Mapping[str, int],
) -> list[tuple[str, list[dict[str, Any]]]]:
    source_file = corpus.document["source_file"]
    ordered = [
        ("legal_documents", [corpus.document]),
        (
            "legal_provisions",
            sorted(corpus.provisions, key=lambda row: (len(row["hierarchy_path"]), row["sequence"])),
        ),
        ("legal_schedules", corpus.schedules),
        ("legal_tables", corpus.tables),
        ("legal_schedule_entries", corpus.schedule_entries),
        ("legal_amendments", corpus.amendments),
        ("legal_requirements", corpus.requirements),
    ]
    return [
        (
            table,
            [
                serialize_phase2_record(
                    table,
                    row,
                    document_id,
                    provision_ids,
                    source_file=source_file,
                )
                for row in rows
            ],
        )
        for table, rows in ordered
    ]


def preview_serialized_groups(corpus: Any) -> list[tuple[str, list[dict[str, Any]]]]:
    document_id = 1
    provision_ids = {
        record["id"]: position
        for position, record in enumerate(corpus.provisions, start=1)
    }
    return serialize_corpus_groups(corpus, document_id, provision_ids)


def _resolve_provision_id(
    provision_ids: Mapping[str, int],
    canonical_id: str | None,
    field: str,
    *,
    required: bool = True,
) -> int | None:
    if canonical_id is None:
        if required:
            raise SchemaAdapterError(f"Missing canonical provision ID for required {field}")
        return None
    try:
        database_id = provision_ids[canonical_id]
    except KeyError as exc:
        raise SchemaAdapterError(f"No bigint mapping exists for canonical provision used by {field}") from exc
    return _bigint_id(database_id, field)