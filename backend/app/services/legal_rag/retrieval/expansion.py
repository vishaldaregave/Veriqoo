"""Statutory relationship expansion along explicit legal hierarchy (Phase 4C).

Grounded in authoritative corpus:
- Traverses explicit database foreign keys and references:
  * Requirement -> Provision
  * Provision -> Schedule / Table
  * Entity -> Amendment
- NEVER infers schedule/amendment relationships using semantic similarity
  when an explicit database relationship exists.
- NEVER manufactures historical applicability or invents effective dates.
"""

from __future__ import annotations

from typing import Any

from backend.app.services.legal_rag.models import (
    LegalEntityType,
    LegalProvenance,
    RetrievalMethod,
    TemporalStatus,
)
from backend.app.services.legal_rag.retrieval.models import RetrievedEntityContext
from backend.app.services.legal_rag.retrieval.repository import LegalCorpusRepository


class StatutoryRelationshipExpander:
    """Expands authoritative statutory context through verified database relationships."""

    def __init__(self, repository: LegalCorpusRepository) -> None:
        self.repository = repository

    def expand(
        self,
        entities: list[RetrievedEntityContext],
        expand_amendments: bool = True,
        expand_schedules_and_tables: bool = True,
    ) -> list[RetrievedEntityContext]:
        """Expand explicit statutory relationships for retrieved entities."""
        expanded: list[RetrievedEntityContext] = []
        seen_keys: set[tuple[str, str]] = {
            (e.entity_type.value, str(e.entity_id)) for e in entities
        }

        # Track provisions to expand tables and amendments for
        provisions_to_expand: set[int] = set()

        for entity in entities:
            # 1. Requirement -> Parent Provision expansion
            if entity.entity_type == LegalEntityType.REQUIREMENT:
                prov_ids = entity.linked_provision_ids
                if not prov_ids and entity.provenance and entity.provenance.provision_id:
                    prov_ids = [entity.provenance.provision_id]

                for pid in prov_ids:
                    key = (LegalEntityType.PROVISION.value, str(pid))
                    if key not in seen_keys:
                        prov_data = self.repository.get_provision(int(pid))
                        if prov_data:
                            prov_ctx = self._build_expanded_provision(prov_data, linked_req_id=entity.entity_id)
                            expanded.append(prov_ctx)
                            seen_keys.add(key)
                            provisions_to_expand.add(int(pid))
                    else:
                        # Link existing provision if in initial list
                        provisions_to_expand.add(int(pid))

                # Also check if requirement links directly to a schedule entry
                for eid in entity.linked_schedule_entry_ids:
                    s_key = (LegalEntityType.SCHEDULE_ENTRY.value, str(eid))
                    if s_key not in seen_keys:
                        entry_data = self.repository.get_schedule_entry(str(eid))
                        if entry_data:
                            entry_ctx = self._build_expanded_schedule_entry(entry_data, linked_req_id=entity.entity_id)
                            expanded.append(entry_ctx)
                            seen_keys.add(s_key)

            elif entity.entity_type == LegalEntityType.PROVISION:
                try:
                    provisions_to_expand.add(int(entity.entity_id))
                except (ValueError, TypeError):
                    pass

        # 2. Provision -> Tables & Amendments expansion
        for pid in provisions_to_expand:
            # Tables linked to this provision
            if expand_schedules_and_tables:
                tables = self.repository.get_tables_by_provision(pid)
                for tbl in tables:
                    tid = str(tbl.get("id"))
                    t_key = (LegalEntityType.TABLE.value, tid)
                    if t_key not in seen_keys:
                        tbl_ctx = self._build_expanded_table(tbl, linked_prov_id=pid)
                        expanded.append(tbl_ctx)
                        seen_keys.add(t_key)

            # Amendments affecting this provision
            if expand_amendments:
                amendments = self.repository.get_amendments_by_provision(pid)
                for amd in amendments:
                    aid = str(amd.get("id"))
                    a_key = (LegalEntityType.AMENDMENT.value, aid)
                    if a_key not in seen_keys:
                        amd_ctx = self._build_expanded_amendment(amd, linked_prov_id=pid)
                        expanded.append(amd_ctx)
                        seen_keys.add(a_key)

        return expanded

    def _build_expanded_provision(self, prov: dict[str, Any], linked_req_id: str | None = None) -> RetrievedEntityContext:
        pid = int(prov.get("id", 0))
        doc_id = prov.get("document_id", 1)
        src_id = str(prov.get("source_identifier") or f"provision_{pid}")
        content = prov.get("content") or ""
        raw_content = prov.get("raw_content") or content
        rule_num = prov.get("rule_number")
        sub_rule = prov.get("sub_rule_number")
        clause = prov.get("clause")
        title = prov.get("title")

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
            source_reference={"source_location": prov.get("source_location"), "provision_type": prov.get("provision_type")},
        )

        linked_reqs = [str(linked_req_id)] if linked_req_id else []

        return RetrievedEntityContext(
            entity_type=LegalEntityType.PROVISION,
            entity_id=str(pid),
            source_identifier=src_id,
            source_reference={"source_location": prov.get("source_location"), "provision_type": prov.get("provision_type")},
            legal_text=content or raw_content,
            source_quote=raw_content,
            similarity_score=0.9,
            retrieval_method=RetrievalMethod.PROVENANCE_EXPANSION,
            ranking_tier=2,
            title=label,
            provenance=provenance,
            linked_requirement_ids=linked_reqs,
            metadata={"rule_number": rule_num, "sub_rule_number": sub_rule, "clause": clause},
        )

    def _build_expanded_schedule_entry(self, entry: dict[str, Any], linked_req_id: str | None = None) -> RetrievedEntityContext:
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

        linked_reqs = [str(linked_req_id)] if linked_req_id else []

        return RetrievedEntityContext(
            entity_type=LegalEntityType.SCHEDULE_ENTRY,
            entity_id=eid,
            source_identifier=src_id,
            source_reference={"entry_key": entry.get("entry_key"), "schedule_id": sched_id},
            legal_text=raw or norm,
            source_quote=raw or norm,
            similarity_score=0.85,
            retrieval_method=RetrievalMethod.HIERARCHICAL_TRAVERSAL,
            ranking_tier=2,
            title=f"Schedule Entry: {commodity}" if commodity else f"Schedule Entry {eid}",
            commodity_text=commodity,
            quantity_text=quantity,
            provenance=provenance,
            linked_requirement_ids=linked_reqs,
        )

    def _build_expanded_table(self, tbl: dict[str, Any], linked_prov_id: int | None = None) -> RetrievedEntityContext:
        tid = str(tbl.get("id"))
        src_id = str(tbl.get("source_identifier") or f"table_{tid}")
        tbl_ident = str(tbl.get("table_identifier") or tid)
        raw = tbl.get("raw_content") or ""
        norm = tbl.get("normalized_content") or raw

        provenance = LegalProvenance(
            source_identifier=src_id,
            document_id=1,
            schedule_id=str(tbl.get("schedule_id")) if tbl.get("schedule_id") else None,
            table_id=tid,
            provision_id=linked_prov_id or (int(tbl["provision_id"]) if tbl.get("provision_id") else None),
            source_quote=raw or norm,
            source_reference={"table_identifier": tbl_ident},
        )

        linked_provs = [int(linked_prov_id)] if linked_prov_id else []

        return RetrievedEntityContext(
            entity_type=LegalEntityType.TABLE,
            entity_id=tid,
            source_identifier=src_id,
            source_reference={"table_identifier": tbl_ident},
            legal_text=raw or norm,
            source_quote=raw or norm,
            similarity_score=0.8,
            retrieval_method=RetrievalMethod.HIERARCHICAL_TRAVERSAL,
            ranking_tier=2,
            title=tbl.get("title") or f"Table: {tbl_ident}",
            provenance=provenance,
            linked_provision_ids=linked_provs,
        )

    def _build_expanded_amendment(self, amd: dict[str, Any], linked_prov_id: int | None = None) -> RetrievedEntityContext:
        aid = str(amd.get("id"))
        src_id = str(amd.get("source_identifier") or f"amendment_{aid}")
        amd_ident = amd.get("amendment_identifier") or f"amendment_{aid}"
        raw = amd.get("raw_content") or ""
        norm = amd.get("normalized_content") or raw
        eff_date = amd.get("effective_date")
        amd_date = amd.get("amendment_date")

        provenance = LegalProvenance(
            source_identifier=src_id,
            document_id=1,
            amendment_id=aid,
            provision_id=linked_prov_id or (int(amd["affected_provision_id"]) if amd.get("affected_provision_id") else None),
            source_quote=raw or norm,
            source_reference={"amendment_identifier": amd_ident, "amendment_date": str(amd_date) if amd_date else None},
        )

        linked_provs = [int(linked_prov_id)] if linked_prov_id else []

        return RetrievedEntityContext(
            entity_type=LegalEntityType.AMENDMENT,
            entity_id=aid,
            source_identifier=src_id,
            source_reference={"amendment_identifier": amd_ident},
            legal_text=raw or norm,
            source_quote=raw or norm,
            similarity_score=0.75,
            retrieval_method=RetrievalMethod.HIERARCHICAL_TRAVERSAL,
            ranking_tier=2,
            title=f"Amendment: {amd_ident}",
            provenance=provenance,
            linked_provision_ids=linked_provs,
            effective_from=eff_date,
            temporal_status=TemporalStatus.CURRENT if eff_date else TemporalStatus.UNKNOWN,
        )

