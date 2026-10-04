"""Direct legal lookup by authoritative identifiers (Phase 4C).

Grounded in authoritative corpus:
- Deterministic ID lookup takes precedence over semantic search.
- When an authoritative ID is known (e.g. from Applicability Engine), retrieval
  fetches the exact entity directly without semantic guesswork.
"""

from __future__ import annotations

from typing import Any

from backend.app.services.legal_rag.models import (
    LegalEntityType,
    LegalProvenance,
    RetrievalMethod,
    TemporalStatus,
)
from backend.app.services.legal_rag.retrieval.models import (
    RetrievalRequest,
    RetrievedEntityContext,
)
from backend.app.services.legal_rag.retrieval.repository import LegalCorpusRepository
from backend.app.services.legal_rag.temporal import resolve_temporal_status


class DirectLookupResolver:
    """Resolves legal entities directly by authoritative primary keys."""

    def __init__(self, repository: LegalCorpusRepository) -> None:
        self.repository = repository

    def resolve(self, request: RetrievalRequest) -> list[RetrievedEntityContext]:
        """Perform exact legal lookups for all explicit IDs in request."""
        results: list[RetrievedEntityContext] = []

        # 1. Requirements lookup
        for rid in request.requirement_ids:
            req = self.repository.get_requirement(str(rid))
            if req:
                results.append(self._build_requirement_context(req, request))

        # 2. Provisions lookup
        for pid in request.provision_ids:
            prov = self.repository.get_provision(int(pid))
            if prov:
                results.append(self._build_provision_context(prov))

        # 3. Schedule Entries lookup
        for eid in request.schedule_entry_ids:
            entry = self.repository.get_schedule_entry(str(eid))
            if entry:
                results.append(self._build_schedule_entry_context(entry))

        # 4. Tables lookup
        for tid in request.table_ids:
            tbl = self.repository.get_table(str(tid))
            if tbl:
                results.append(self._build_table_context(tbl))

        # 5. Amendments lookup
        for aid in request.amendment_ids:
            amd = self.repository.get_amendment(str(aid))
            if amd:
                results.append(self._build_amendment_context(amd))

        return results

    def _build_requirement_context(
        self,
        req: dict[str, Any],
        request: RetrievalRequest,
    ) -> RetrievedEntityContext:
        rid = str(req.get("id"))
        src_id = str(req.get("source_identifier") or f"requirement_{rid}")
        prov_id = req.get("provision_id")
        norm_req = req.get("normalized_requirement") or ""
        req_text = req.get("requirement_text") or norm_req
        subject = req.get("subject") or ""
        src_quote = req.get("source_quote") or ""
        src_ref = req.get("source_reference") or {}

        # Look up parent provision details if available
        rule_num = None
        sub_rule = None
        clause = None
        if prov_id is not None:
            parent_p = self.repository.get_provision(int(prov_id))
            if parent_p:
                rule_num = parent_p.get("rule_number")
                sub_rule = parent_p.get("sub_rule_number")
                clause = parent_p.get("clause")

        provenance = LegalProvenance(
            source_identifier=src_id,
            document_id=src_ref.get("document_id", 1),
            provision_id=int(prov_id) if prov_id is not None else None,
            rule_number=rule_num or src_ref.get("rule_number"),
            sub_rule_number=sub_rule or src_ref.get("sub_rule_number"),
            clause=clause or src_ref.get("clause"),
            schedule_entry_id=str(req["schedule_entry_id"]) if req.get("schedule_entry_id") else None,
            source_page=src_ref.get("source_page"),
            source_page_end=src_ref.get("source_page_end"),
            source_line_start=src_ref.get("source_line_start"),
            source_line_end=src_ref.get("source_line_end"),
            source_quote=src_quote,
            source_reference=src_ref,
        )

        eff_from = req.get("effective_from")
        eff_to = req.get("effective_to")
        temporal_status = resolve_temporal_status(eff_from, eff_to, request.as_of_date)

        linked_provs = [int(prov_id)] if prov_id is not None else []
        linked_scheds = [str(req["schedule_entry_id"])] if req.get("schedule_entry_id") else []

        return RetrievedEntityContext(
            entity_type=LegalEntityType.REQUIREMENT,
            entity_id=rid,
            source_identifier=src_id,
            source_reference=src_ref,
            legal_text=req_text,
            source_quote=src_quote,
            similarity_score=1.0,
            retrieval_method=RetrievalMethod.REQUIREMENT_LOOKUP,
            ranking_tier=1,
            title=f"Requirement: {subject}" if subject else f"Requirement {rid}",
            provenance=provenance,
            linked_provision_ids=linked_provs,
            linked_schedule_entry_ids=linked_scheds,
            temporal_status=temporal_status,
            effective_from=eff_from,
            effective_to=eff_to,
            metadata={
                "normalized_requirement": norm_req,
                "requirement_type": req.get("requirement_type"),
                "subject": subject,
            },
        )

    def _build_provision_context(self, prov: dict[str, Any]) -> RetrievedEntityContext:
        pid = int(prov.get("id", 0))
        doc_id = prov.get("document_id", 1)
        src_id = str(prov.get("source_identifier") or f"provision_{pid}")
        content = prov.get("content") or ""
        raw_content = prov.get("raw_content") or content
        rule_num = prov.get("rule_number")
        sub_rule = prov.get("sub_rule_number")
        clause = prov.get("clause")
        title = prov.get("title")
        src_loc = prov.get("source_location") or ""

        label = f"Rule {rule_num}" if rule_num else "Provision"
        if sub_rule:
            label += f"({sub_rule})"
        if clause:
            label += f"({clause})"
        if title:
            label += f": {title}"

        provenance = LegalProvenance(
            source_identifier=src_id,
            document_id=doc_id,
            provision_id=pid,
            rule_number=rule_num,
            sub_rule_number=sub_rule,
            clause=clause,
            source_quote=raw_content,
            source_reference={"source_location": src_loc, "provision_type": prov.get("provision_type")},
        )

        return RetrievedEntityContext(
            entity_type=LegalEntityType.PROVISION,
            entity_id=str(pid),
            source_identifier=src_id,
            source_reference={"source_location": src_loc, "provision_type": prov.get("provision_type")},
            legal_text=content or raw_content,
            source_quote=raw_content,
            similarity_score=1.0,
            retrieval_method=RetrievalMethod.EXACT_ID,
            ranking_tier=1,
            title=label,
            provenance=provenance,
            linked_provision_ids=[int(prov["parent_provision_id"])] if prov.get("parent_provision_id") else [],
            metadata={
                "rule_number": rule_num,
                "sub_rule_number": sub_rule,
                "clause": clause,
                "provision_type": prov.get("provision_type"),
            },
        )

    def _build_schedule_entry_context(self, entry: dict[str, Any]) -> RetrievedEntityContext:
        eid = str(entry.get("id"))
        src_id = str(entry.get("source_identifier") or f"schedule_entry_{eid}")
        sched_id = str(entry.get("schedule_id", ""))
        raw = entry.get("raw_content") or ""
        norm = entry.get("normalized_content") or raw
        commodity = entry.get("commodity_text")
        quantity = entry.get("quantity_text")

        provenance = LegalProvenance(
            source_identifier=src_id,
            document_id=1,
            schedule_id=sched_id,
            schedule_entry_id=eid,
            source_quote=raw or norm,
            source_reference={"entry_key": entry.get("entry_key")},
        )

        return RetrievedEntityContext(
            entity_type=LegalEntityType.SCHEDULE_ENTRY,
            entity_id=eid,
            source_identifier=src_id,
            source_reference={"entry_key": entry.get("entry_key"), "schedule_id": sched_id},
            legal_text=raw or norm,
            source_quote=raw or norm,
            similarity_score=1.0,
            retrieval_method=RetrievalMethod.EXACT_ID,
            ranking_tier=1,
            title=f"Schedule Entry: {commodity}" if commodity else f"Schedule Entry {eid}",
            commodity_text=commodity,
            quantity_text=quantity,
            provenance=provenance,
            metadata={
                "schedule_id": sched_id,
                "entry_number": entry.get("entry_number"),
                "item_text": entry.get("item_text"),
                "permitted_package_quantity": entry.get("permitted_package_quantity"),
            },
        )

    def _build_table_context(self, tbl: dict[str, Any]) -> RetrievedEntityContext:
        tid = str(tbl.get("id"))
        src_id = str(tbl.get("source_identifier") or f"table_{tid}")
        tbl_ident = str(tbl.get("table_identifier") or tid)
        title = tbl.get("title")
        raw = tbl.get("raw_content") or ""
        norm = tbl.get("normalized_content") or raw
        prov_id = tbl.get("provision_id")
        sched_id = tbl.get("schedule_id")

        provenance = LegalProvenance(
            source_identifier=src_id,
            document_id=1,
            schedule_id=str(sched_id) if sched_id else None,
            table_id=tid,
            provision_id=int(prov_id) if prov_id else None,
            source_quote=raw or norm,
            source_reference={"table_identifier": tbl_ident},
        )

        return RetrievedEntityContext(
            entity_type=LegalEntityType.TABLE,
            entity_id=tid,
            source_identifier=src_id,
            source_reference={"table_identifier": tbl_ident, "schedule_id": sched_id},
            legal_text=raw or norm,
            source_quote=raw or norm,
            similarity_score=1.0,
            retrieval_method=RetrievalMethod.EXACT_ID,
            ranking_tier=1,
            title=title or f"Table: {tbl_ident}",
            provenance=provenance,
            linked_provision_ids=[int(prov_id)] if prov_id else [],
            metadata={
                "table_identifier": tbl_ident,
                "headers": tbl.get("headers", []),
                "rows_count": tbl.get("rows_count"),
            },
        )

    def _build_amendment_context(self, amd: dict[str, Any]) -> RetrievedEntityContext:
        aid = str(amd.get("id"))
        src_id = str(amd.get("source_identifier") or f"amendment_{aid}")
        amd_ident = amd.get("amendment_identifier") or f"amendment_{aid}"
        raw = amd.get("raw_content") or ""
        norm = amd.get("normalized_content") or raw
        aff_prov = amd.get("affected_provision_id")
        eff_date = amd.get("effective_date")
        amd_date = amd.get("amendment_date")

        provenance = LegalProvenance(
            source_identifier=src_id,
            document_id=1,
            amendment_id=aid,
            provision_id=int(aff_prov) if aff_prov else None,
            source_quote=raw or norm,
            source_reference={"amendment_identifier": amd_ident, "amendment_date": str(amd_date) if amd_date else None},
        )

        return RetrievedEntityContext(
            entity_type=LegalEntityType.AMENDMENT,
            entity_id=aid,
            source_identifier=src_id,
            source_reference={"amendment_identifier": amd_ident, "amendment_date": str(amd_date) if amd_date else None},
            legal_text=raw or norm,
            source_quote=raw or norm,
            similarity_score=1.0,
            retrieval_method=RetrievalMethod.EXACT_ID,
            ranking_tier=1,
            title=f"Amendment: {amd_ident}",
            provenance=provenance,
            linked_provision_ids=[int(aff_prov)] if aff_prov else [],
            effective_from=eff_date,
            temporal_status=TemporalStatus.CURRENT if eff_date else TemporalStatus.UNKNOWN,
            metadata={
                "amendment_identifier": amd_ident,
                "gazette_notification_number": amd.get("gazette_notification_number"),
                "amendment_date": str(amd_date) if amd_date else None,
            },
        )

