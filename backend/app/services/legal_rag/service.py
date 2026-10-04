"""Canonical implementation of LegalRetrievalContract for Veriqoo (Phase 4A).

Implements:
- Requirement-first retrieval for applicable requirement IDs
- Exact entity lookups (requirements, provisions, schedule entries, tables, amendments)
- Deterministic lexical filtering and provenance expansion
- Completeness evaluation (retrieval_complete != semantic_top_k_complete)
- Deterministic deduplication and ranking
- No-result handling without hallucinations
"""

from __future__ import annotations

import time
from typing import Any, Mapping, Sequence

from backend.app.services.legal_rag.completeness import evaluate_completeness
from backend.app.services.legal_rag.contract import (
    LegalRetrievalContract,
)
from backend.app.services.legal_rag.deduplication import deduplicate_results
from backend.app.services.legal_rag.models import (
    LegalEntityType,
    LegalProvenance,
    LegalRetrievalQuery,
    LegalRetrievalResponse,
    LegalSearchResult,
    RankingMetadata,
    RetrievalConfig,
    RetrievalMethod,
    RetrievalMode,
    TemporalStatus,
)
from backend.app.services.legal_rag.ranking import apply_provisional_threshold, rank_results
from backend.app.services.legal_rag.schedule_table import (
    build_schedule_entry_result,
    build_table_result,
)
from backend.app.services.legal_rag.temporal import resolve_temporal_status


class LegalRetrievalService(LegalRetrievalContract):
    """Statutory Legal RAG service operating under the formal Phase 4A retrieval contract."""

    def __init__(
        self,
        config: RetrievalConfig | None = None,
        requirements_store: Mapping[str, Any] | None = None,
        provisions_store: Mapping[int, Any] | None = None,
        schedule_entries_store: Mapping[str, Any] | None = None,
        tables_store: Mapping[str, Any] | None = None,
        amendments_store: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(config=config)
        self.requirements_store: dict[str, Any] = dict(requirements_store or {})
        self.provisions_store: dict[int, Any] = dict(provisions_store or {})
        self.schedule_entries_store: dict[str, Any] = dict(schedule_entries_store or {})
        self.tables_store: dict[str, Any] = dict(tables_store or {})
        self.amendments_store: dict[str, Any] = dict(amendments_store or {})

    def register_requirement(self, req: Any) -> None:
        """Register a legal requirement in the retrieval store."""
        req_id = str(getattr(req, "id", req.get("id") if isinstance(req, dict) else ""))
        self.requirements_store[req_id] = req

    def register_provision(self, prov: Any) -> None:
        """Register a legal provision in the retrieval store."""
        prov_id = int(getattr(prov, "id", prov.get("id") if isinstance(prov, dict) else 0))
        self.provisions_store[prov_id] = prov

    def register_schedule_entry(self, entry: Any) -> None:
        """Register a schedule entry in the retrieval store."""
        entry_id = str(getattr(entry, "id", entry.get("id") if isinstance(entry, dict) else ""))
        self.schedule_entries_store[entry_id] = entry

    def register_table(self, tbl: Any) -> None:
        """Register a legal table in the retrieval store."""
        tbl_id = str(getattr(tbl, "id", tbl.get("id") if isinstance(tbl, dict) else ""))
        self.tables_store[tbl_id] = tbl

    def register_amendment(self, amd: Any) -> None:
        """Register an amendment in the retrieval store."""
        amd_id = str(getattr(amd, "id", amd.get("id") if isinstance(amd, dict) else ""))
        self.amendments_store[amd_id] = amd

    def retrieve_for_applicable_requirements(
        self,
        requirement_ids: list[str],
        context_filters: dict[str, Any] | None = None,
    ) -> LegalRetrievalResponse:
        """Requirement-First Retrieval: Retrieve full statutory context for applicable requirements

        determined by the Applicability Engine.
        """
        query = LegalRetrievalQuery(
            requirement_ids=requirement_ids,
            mode=RetrievalMode.REQUIREMENT_CONTEXT,
            context_filters=context_filters or {},
            limit=max(len(requirement_ids) * 3, 20),
        )
        return self.retrieve(query)

    def retrieve(self, query: LegalRetrievalQuery) -> LegalRetrievalResponse:
        """Execute statutory retrieval according to query specification."""
        start_time = time.perf_counter()

        # 1. Validate query
        errors = self.validate_query(query)
        if errors:
            return LegalRetrievalResponse(
                results=[],
                query=query,
                total_found=0,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                no_result_reason=f"Validation failed: {'; '.join(errors)}",
            )

        raw_results: list[LegalSearchResult] = []

        # 2. Exact Requirement IDs lookup
        if query.requirement_ids:
            for rid in query.requirement_ids:
                req_obj = self.requirements_store.get(str(rid))
                if req_obj:
                    res = self._convert_requirement_to_result(
                        req_obj,
                        query=query,
                        retrieval_method=RetrievalMethod.REQUIREMENT_LOOKUP,
                    )
                    raw_results.append(res)
                    # Provenance expansion: include parent provision if configured
                    if self.config.enable_provenance_expansion and res.provenance and res.provenance.provision_id:
                        prov_obj = self.provisions_store.get(res.provenance.provision_id)
                        if prov_obj:
                            raw_results.append(
                                self._convert_provision_to_result(
                                    prov_obj,
                                    retrieval_method=RetrievalMethod.PROVENANCE_EXPANSION,
                                )
                            )

        # 3. Exact Provision IDs lookup
        if query.provision_ids:
            for pid in query.provision_ids:
                prov_obj = self.provisions_store.get(pid)
                if prov_obj:
                    raw_results.append(
                        self._convert_provision_to_result(
                            prov_obj,
                            retrieval_method=RetrievalMethod.EXACT_ID,
                        )
                    )

        # 4. Exact Schedule Entry IDs lookup
        if query.schedule_entry_ids:
            for eid in query.schedule_entry_ids:
                entry_obj = self.schedule_entries_store.get(str(eid))
                if entry_obj:
                    raw_results.append(
                        self._convert_schedule_entry_to_result(
                            entry_obj,
                            retrieval_method=RetrievalMethod.EXACT_ID,
                        )
                    )

        # 5. Exact Table IDs lookup
        if query.table_ids:
            for tid in query.table_ids:
                tbl_obj = self.tables_store.get(str(tid))
                if tbl_obj:
                    raw_results.append(
                        self._convert_table_to_result(
                            tbl_obj,
                            retrieval_method=RetrievalMethod.EXACT_ID,
                        )
                    )

        # 6. Exact Amendment IDs lookup
        if query.amendment_ids:
            for aid in query.amendment_ids:
                amd_obj = self.amendments_store.get(str(aid))
                if amd_obj:
                    raw_results.append(
                        self._convert_amendment_to_result(
                            amd_obj,
                            retrieval_method=RetrievalMethod.EXACT_ID,
                        )
                    )

        # 7. Lexical / text search if query_text is provided
        if query.query_text and query.query_text.strip():
            terms = [t.lower() for t in query.query_text.strip().split() if len(t) > 2]
            if terms:
                for req_id, req in self.requirements_store.items():
                    norm_text = (self._get_val(req, "normalized_requirement") or "").lower()
                    req_text = (self._get_val(req, "requirement_text") or "").lower()
                    matches = [term for term in terms if term in norm_text or term in req_text]
                    if matches:
                        score = len(matches) / len(terms)
                        raw_results.append(
                            self._convert_requirement_to_result(
                                req,
                                query=query,
                                retrieval_method=RetrievalMethod.LEXICAL_SEARCH,
                                score=score,
                                matched_terms=matches,
                            )
                        )

        # 8. Deduplicate while preserving provenance and hierarchy
        deduped = deduplicate_results(raw_results)

        # 9. Apply deterministic ranking
        ranked = rank_results(deduped)

        # 10. Apply provisional threshold
        if query.mode == RetrievalMode.SEMANTIC_CONTEXT and query.min_similarity_threshold > 0:
            final_results, fallback = apply_provisional_threshold(
                ranked,
                threshold=query.min_similarity_threshold,
                allow_fallback=False,
            )
        else:
            final_results = ranked

        # Apply query limit
        final_results = final_results[: query.limit]

        # 11. Evaluate Completeness
        completeness = evaluate_completeness(
            requested_requirement_ids=query.requirement_ids,
            results=final_results,
            semantic_top_k_count=len(final_results),
        )

        no_result_reason = None
        if not final_results:
            no_result_reason = "No matching authoritative legal provisions or requirements found"

        return LegalRetrievalResponse(
            results=final_results,
            completeness=completeness,
            query=query,
            total_found=len(final_results),
            execution_time_ms=(time.perf_counter() - start_time) * 1000,
            no_result_reason=no_result_reason,
        )

    # --------------------------------------------------
    # INTERNAL ENTITY CONVERTERS
    # --------------------------------------------------

    def _get_val(self, obj: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(field_name, default)
        return getattr(obj, field_name, default)

    def _convert_requirement_to_result(
        self,
        req: Any,
        query: LegalRetrievalQuery | None = None,
        retrieval_method: RetrievalMethod = RetrievalMethod.REQUIREMENT_LOOKUP,
        score: float = 1.0,
        matched_terms: Sequence[str] = (),
    ) -> LegalSearchResult:
        rid = str(self._get_val(req, "id"))
        src_id = str(self._get_val(req, "source_identifier"))
        prov_id = self._get_val(req, "provision_id")
        src_quote = str(self._get_val(req, "source_quote", ""))
        src_ref = self._get_val(req, "source_reference", {}) or {}
        norm_req = self._get_val(req, "normalized_requirement", "")
        req_text = self._get_val(req, "requirement_text", "")
        subject = self._get_val(req, "subject", "")

        # Look up parent provision details for rule number if available
        rule_num = None
        sub_rule = None
        clause = None
        if prov_id and prov_id in self.provisions_store:
            parent_p = self.provisions_store[prov_id]
            rule_num = self._get_val(parent_p, "rule_number")
            sub_rule = self._get_val(parent_p, "sub_rule_number")
            clause = self._get_val(parent_p, "clause")

        prov = LegalProvenance(
            source_identifier=src_id,
            document_id=src_ref.get("document_id", 1),
            provision_id=int(prov_id) if prov_id else None,
            rule_number=rule_num or src_ref.get("rule_number"),
            sub_rule_number=sub_rule or src_ref.get("sub_rule_number"),
            clause=clause or src_ref.get("clause"),
            schedule_entry_id=str(self._get_val(req, "schedule_entry_id")) if self._get_val(req, "schedule_entry_id") else None,
            source_page=src_ref.get("source_page"),
            source_page_end=src_ref.get("source_page_end"),
            source_line_start=src_ref.get("source_line_start"),
            source_line_end=src_ref.get("source_line_end"),
            source_quote=src_quote,
            source_reference=src_ref,
        )

        eff_from = self._get_val(req, "effective_from")
        eff_to = self._get_val(req, "effective_to")
        as_of = query.as_of_date if query else None
        temporal_status = resolve_temporal_status(eff_from, eff_to, as_of)

        ranking = RankingMetadata(
            score=score,
            lexical_score=score if retrieval_method == RetrievalMethod.LEXICAL_SEARCH else None,
            semantic_similarity=1.0 if retrieval_method in (RetrievalMethod.EXACT_ID, RetrievalMethod.REQUIREMENT_LOOKUP) else None,
            provenance_specificity=1.0,
            requirement_priority=1,
            matched_terms=tuple(matched_terms),
        )

        return LegalSearchResult(
            entity_type=LegalEntityType.REQUIREMENT,
            entity_id=rid,
            source_identifier=src_id,
            title=f"Requirement: {subject}" if subject else f"Requirement {rid}",
            relevant_text=req_text or norm_req,
            normalized_requirement=norm_req,
            source_quote=src_quote,
            source_reference=src_ref,
            provenance=prov,
            ranking=ranking,
            retrieval_method=retrieval_method,
            parent_entity_id=str(prov_id) if prov_id else None,
            parent_entity_type=LegalEntityType.PROVISION if prov_id else None,
            temporal_status=temporal_status,
            effective_from=eff_from,
            effective_to=eff_to,
        )

    def _convert_provision_to_result(
        self,
        prov: Any,
        retrieval_method: RetrievalMethod = RetrievalMethod.EXACT_ID,
    ) -> LegalSearchResult:
        pid = int(self._get_val(prov, "id"))
        doc_id = self._get_val(prov, "document_id", 1)
        src_id = str(self._get_val(prov, "source_identifier", f"provision_{pid}"))
        content = self._get_val(prov, "content", "")
        raw_content = self._get_val(prov, "raw_content", "") or content
        rule_num = self._get_val(prov, "rule_number")
        sub_rule = self._get_val(prov, "sub_rule_number")
        clause = self._get_val(prov, "clause")
        title = self._get_val(prov, "title")
        src_loc = self._get_val(prov, "source_location", "")

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
            source_reference={"source_location": src_loc, "provision_type": self._get_val(prov, "provision_type")},
        )

        return LegalSearchResult(
            entity_type=LegalEntityType.PROVISION,
            entity_id=str(pid),
            source_identifier=src_id,
            title=label,
            relevant_text=content or raw_content,
            source_quote=raw_content,
            provenance=provenance,
            ranking=RankingMetadata(score=0.9, provenance_specificity=0.8, requirement_priority=2),
            retrieval_method=retrieval_method,
            parent_entity_id=str(self._get_val(prov, "parent_provision_id")) if self._get_val(prov, "parent_provision_id") else None,
            parent_entity_type=LegalEntityType.PROVISION,
        )

    def _convert_schedule_entry_to_result(
        self,
        entry: Any,
        retrieval_method: RetrievalMethod = RetrievalMethod.EXACT_ID,
    ) -> LegalSearchResult:
        eid = str(self._get_val(entry, "id"))
        src_id = str(self._get_val(entry, "source_identifier"))
        sched_id = str(self._get_val(entry, "schedule_id"))
        raw = self._get_val(entry, "raw_content", "")
        norm = self._get_val(entry, "normalized_content", "")
        commodity = self._get_val(entry, "commodity_text")
        quantity = self._get_val(entry, "quantity_text")
        item = self._get_val(entry, "item_text")
        permitted = self._get_val(entry, "permitted_package_quantity")
        entry_num = self._get_val(entry, "entry_number")
        cells = self._get_val(entry, "cells", [])

        prov = LegalProvenance(
            source_identifier=src_id,
            document_id=1,
            schedule_id=sched_id,
            schedule_entry_id=eid,
            source_quote=raw or norm,
            source_reference={"entry_key": self._get_val(entry, "entry_key")},
        )

        return build_schedule_entry_result(
            entry_id=eid,
            source_identifier=src_id,
            schedule_id=sched_id,
            schedule_number="Second",
            commodity_text=commodity,
            quantity_text=quantity,
            raw_content=raw or norm,
            provenance=prov,
            item_text=item,
            permitted_package_quantity=permitted,
            entry_number=entry_num,
            cells=cells,
            retrieval_method=retrieval_method,
        )

    def _convert_table_to_result(
        self,
        tbl: Any,
        retrieval_method: RetrievalMethod = RetrievalMethod.EXACT_ID,
    ) -> LegalSearchResult:
        tid = str(self._get_val(tbl, "id"))
        src_id = str(self._get_val(tbl, "source_identifier"))
        tbl_ident = str(self._get_val(tbl, "table_identifier", tid))
        title = self._get_val(tbl, "title")
        headers = self._get_val(tbl, "headers", [])
        raw = self._get_val(tbl, "raw_content", "")
        norm = self._get_val(tbl, "normalized_content", "")
        sched_id = str(self._get_val(tbl, "schedule_id")) if self._get_val(tbl, "schedule_id") else None
        prov_id = self._get_val(tbl, "provision_id")

        prov = LegalProvenance(
            source_identifier=src_id,
            document_id=1,
            schedule_id=sched_id,
            table_id=tid,
            provision_id=int(prov_id) if prov_id else None,
            source_quote=raw or norm,
            source_reference={"table_identifier": tbl_ident},
        )

        return build_table_result(
            table_id=tid,
            source_identifier=src_id,
            table_identifier=tbl_ident,
            title=title,
            headers=headers if isinstance(headers, list) else [],
            raw_content=raw or norm,
            provenance=prov,
            schedule_id=sched_id,
            provision_id=int(prov_id) if prov_id else None,
            retrieval_method=retrieval_method,
        )

    def _convert_amendment_to_result(
        self,
        amd: Any,
        retrieval_method: RetrievalMethod = RetrievalMethod.EXACT_ID,
    ) -> LegalSearchResult:
        aid = str(self._get_val(amd, "id"))
        src_id = str(self._get_val(amd, "source_identifier"))
        amd_ident = self._get_val(amd, "amendment_identifier", f"amendment_{aid}")
        raw = self._get_val(amd, "raw_content", "")
        norm = self._get_val(amd, "normalized_content", "")
        aff_prov = self._get_val(amd, "affected_provision_id")
        eff_date = self._get_val(amd, "effective_date")
        amd_date = self._get_val(amd, "amendment_date")

        prov = LegalProvenance(
            source_identifier=src_id,
            document_id=1,
            amendment_id=aid,
            provision_id=int(aff_prov) if aff_prov else None,
            source_quote=raw or norm,
            source_reference={"amendment_identifier": amd_ident, "amendment_date": str(amd_date) if amd_date else None},
        )

        return LegalSearchResult(
            entity_type=LegalEntityType.AMENDMENT,
            entity_id=aid,
            source_identifier=src_id,
            title=f"Amendment: {amd_ident}",
            relevant_text=raw or norm,
            source_quote=raw or norm,
            provenance=prov,
            ranking=RankingMetadata(score=0.8, provenance_specificity=0.7, requirement_priority=5),
            retrieval_method=retrieval_method,
            parent_entity_id=str(aff_prov) if aff_prov else None,
            parent_entity_type=LegalEntityType.PROVISION if aff_prov else None,
            effective_from=eff_date,
            temporal_status=TemporalStatus.CURRENT if eff_date else TemporalStatus.UNKNOWN,
        )

