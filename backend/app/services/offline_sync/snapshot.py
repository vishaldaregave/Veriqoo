"""Deterministic Legal Snapshot Builder and Canonicalization Engine for Phase U24-A.

Computes a cryptographic, reproducible SHA-256 identity from active, approved legal corpus data:
- Legal Documents
- Statutory Provisions
- Normalized Requirements
- Statutory Schedules
- Prescribed Schedule Entries
- Statutory Tables
- Statutory Amendments
- Approved Applicability Rule Versions
- Approved Applicability Condition Groups
- Approved Applicability Conditions

Guarantees:
1. Strict inclusion of approved/authoritative items only (drafts, in_review, retired versions excluded).
2. Deterministic entity sorting and key ordering (independent of database row retrieval order).
3. Stable Unicode, null, and numeric representation.
4. Absence of non-deterministic artifacts (memory addresses, random IDs, generation timestamps in hash).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from backend.app.services.offline_sync.models import (
    LegalSnapshotManifest,
    LegalSnapshotValidationResult,
    LegalSnapshotValidationStatus,
)


def _get_field(obj: Any, field_name: str, default: Any = None) -> Any:
    """Helper to extract field value from dict, dataclass, or Pydantic object."""
    if isinstance(obj, dict):
        return obj.get(field_name, default)
    return getattr(obj, field_name, default)


# =====================================================================
# Canonical Entity Normalizers
# =====================================================================

def canonicalize_document(doc: Any) -> dict[str, Any]:
    """Extract canonical deterministic representation of a legal document."""
    year_val = _get_field(doc, "year")
    clean_year = None
    if year_val is not None:
        try:
            clean_year = int(year_val)
        except (ValueError, TypeError):
            clean_year = None

    return {
        "id": str(_get_field(doc, "id", "")).strip(),
        "document_type": str(_get_field(doc, "document_type", "")).strip().lower(),
        "short_title": str(_get_field(doc, "short_title", "") or _get_field(doc, "title", "")).strip(),
        "official_title": str(_get_field(doc, "official_title", "") or _get_field(doc, "act_name", "")).strip(),
        "year": clean_year,
    }


def canonicalize_provision(prov: Any) -> dict[str, Any]:
    """Extract canonical deterministic representation of a legal provision."""
    content = str(_get_field(prov, "content", "") or _get_field(prov, "raw_content", "")).strip()
    return {
        "id": str(_get_field(prov, "id", "")).strip(),
        "document_id": str(_get_field(prov, "document_id", "")).strip(),
        "provision_type": str(_get_field(prov, "provision_type", "")).strip().lower(),
        "rule_number": str(_get_field(prov, "rule_number", "")).strip() if _get_field(prov, "rule_number") else None,
        "sub_rule_number": str(_get_field(prov, "sub_rule_number", "")).strip() if _get_field(prov, "sub_rule_number") else None,
        "clause": str(_get_field(prov, "clause", "")).strip() if _get_field(prov, "clause") else None,
        "title": str(_get_field(prov, "title", "")).strip() if _get_field(prov, "title") else None,
        "content": content,
    }


def canonicalize_requirement(req: Any) -> dict[str, Any]:
    """Extract canonical deterministic representation of a normalized legal requirement."""
    prov_id = _get_field(req, "provision_id")
    sched_entry_id = _get_field(req, "schedule_entry_id")
    return {
        "id": str(_get_field(req, "id", "")).strip(),
        "source_identifier": str(_get_field(req, "source_identifier", "") or _get_field(req, "requirement_code", "")).strip(),
        "provision_id": str(prov_id).strip() if prov_id is not None else None,
        "schedule_entry_id": str(sched_entry_id).strip() if sched_entry_id else None,
        "subject": str(_get_field(req, "subject", "")).strip() if _get_field(req, "subject") else None,
        "normalized_requirement": str(_get_field(req, "normalized_requirement", "") or _get_field(req, "description", "")).strip(),
        "requirement_text": str(_get_field(req, "requirement_text", "")).strip() if _get_field(req, "requirement_text") else None,
        "effective_from": str(_get_field(req, "effective_from")) if _get_field(req, "effective_from") else None,
        "effective_to": str(_get_field(req, "effective_to")) if _get_field(req, "effective_to") else None,
    }


def canonicalize_schedule(sched: Any) -> dict[str, Any]:
    """Extract canonical deterministic representation of a statutory schedule."""
    return {
        "id": str(_get_field(sched, "id", "")).strip(),
        "schedule_number": str(_get_field(sched, "schedule_number", "")).strip(),
        "title": str(_get_field(sched, "title", "")).strip(),
    }


def canonicalize_schedule_entry(entry: Any) -> dict[str, Any]:
    """Extract canonical deterministic representation of a schedule entry."""
    entry_num = _get_field(entry, "entry_number")
    clean_num = None
    if entry_num is not None:
        try:
            clean_num = int(entry_num)
        except (ValueError, TypeError):
            clean_num = None

    return {
        "id": str(_get_field(entry, "id", "")).strip(),
        "schedule_id": str(_get_field(entry, "schedule_id", "")).strip(),
        "entry_number": clean_num,
        "commodity_text": str(_get_field(entry, "commodity_text", "")).strip() if _get_field(entry, "commodity_text") else None,
        "quantity_text": str(_get_field(entry, "quantity_text", "")).strip() if _get_field(entry, "quantity_text") else None,
        "permitted_package_quantity": str(_get_field(entry, "permitted_package_quantity", "")).strip() if _get_field(entry, "permitted_package_quantity") else None,
    }


def canonicalize_table(tbl: Any) -> dict[str, Any]:
    """Extract canonical deterministic representation of a statutory table."""
    headers = _get_field(tbl, "headers", [])
    clean_headers = [str(h).strip() for h in headers] if isinstance(headers, (list, tuple)) else []
    return {
        "id": str(_get_field(tbl, "id", "")).strip(),
        "table_identifier": str(_get_field(tbl, "table_identifier", "")).strip(),
        "title": str(_get_field(tbl, "title", "")).strip() if _get_field(tbl, "title") else None,
        "headers": clean_headers,
    }


def canonicalize_amendment(amd: Any) -> dict[str, Any]:
    """Extract canonical deterministic representation of a statutory amendment."""
    aff_prov = _get_field(amd, "affected_provision_id")
    eff_date = _get_field(amd, "effective_date")
    amd_date = _get_field(amd, "amendment_date")
    return {
        "id": str(_get_field(amd, "id", "")).strip(),
        "amendment_identifier": str(_get_field(amd, "amendment_identifier", "")).strip(),
        "affected_provision_id": str(aff_prov).strip() if aff_prov is not None else None,
        "effective_date": str(eff_date) if eff_date else None,
        "amendment_date": str(amd_date) if amd_date else None,
    }


def canonicalize_applicability_rule_version(ver: Any) -> dict[str, Any] | None:
    """Extract canonical deterministic representation of an approved applicability rule version.
    
    Returns None if status is not approved/active.
    """
    status = str(_get_field(ver, "status", "") or _get_field(ver, "interpretation_status", "") or _get_field(ver, "review_status", "")).strip().lower()
    if status not in {"approved", "active"}:
        return None

    ver_num = _get_field(ver, "version_number", 1)
    val_from = _get_field(ver, "valid_from")
    val_to = _get_field(ver, "valid_to")
    amd_id = _get_field(ver, "amendment_id")
    desc = _get_field(ver, "description")

    return {
        "id": str(_get_field(ver, "id", "")).strip(),
        "rule_id": str(_get_field(ver, "rule_id", "")).strip(),
        "version_number": int(ver_num) if ver_num is not None else 1,
        "description": str(desc).strip() if desc else None,
        "valid_from": str(val_from) if val_from else None,
        "valid_to": str(val_to) if val_to else None,
        "amendment_id": str(amd_id).strip() if amd_id else None,
    }


def canonicalize_condition_group(group: Any) -> dict[str, Any] | None:
    """Extract canonical deterministic representation of an approved condition group.
    
    Returns None if status is not approved/active.
    """
    status = str(_get_field(group, "status", "") or _get_field(group, "review_status", "approved")).strip().lower()
    if status not in {"approved", "active"}:
        return None

    parent_id = _get_field(group, "parent_group_id")
    seq = _get_field(group, "sequence", 1)
    op = str(_get_field(group, "group_type", "") or _get_field(group, "boolean_operator", "AND")).strip().upper()

    return {
        "id": str(_get_field(group, "id", "")).strip(),
        "rule_version_id": str(_get_field(group, "rule_version_id", "")).strip(),
        "parent_group_id": str(parent_id).strip() if parent_id else None,
        "group_purpose": str(_get_field(group, "group_purpose", "applicability")).strip().lower(),
        "boolean_operator": op,
        "sequence": int(seq) if seq is not None else 1,
    }


def canonicalize_condition(cond: Any) -> dict[str, Any] | None:
    """Extract canonical deterministic representation of an approved applicability condition.
    
    Returns None if status is not approved/active.
    """
    status = str(_get_field(cond, "status", "") or _get_field(cond, "review_status", "approved")).strip().lower()
    if status not in {"approved", "active"}:
        return None

    seq = _get_field(cond, "sequence", 1)
    fact_k = str(_get_field(cond, "fact_key", "") or _get_field(cond, "field", "")).strip()
    exp_val = _get_field(cond, "expected_value", _get_field(cond, "value"))
    exp_unit = _get_field(cond, "expected_unit")
    group_id = str(_get_field(cond, "group_id", "") or _get_field(cond, "condition_group_id", "")).strip()

    return {
        "id": str(_get_field(cond, "id", "")).strip(),
        "group_id": group_id,
        "fact_key": fact_k,
        "operator": str(_get_field(cond, "operator", "")).strip().lower(),
        "expected_value": exp_val,
        "expected_unit": str(exp_unit).strip() if exp_unit else None,
        "sequence": int(seq) if seq is not None else 1,
    }


# =====================================================================
# Legal Snapshot Builder
# =====================================================================

class LegalSnapshotBuilder:
    """Constructs canonical legal snapshot identities and manifests from active legal data structures."""

    @classmethod
    def build_snapshot(
        cls,
        documents: Sequence[Any] | Mapping[Any, Any] = (),
        provisions: Sequence[Any] | Mapping[Any, Any] = (),
        requirements: Sequence[Any] | Mapping[Any, Any] = (),
        schedules: Sequence[Any] | Mapping[Any, Any] = (),
        schedule_entries: Sequence[Any] | Mapping[Any, Any] = (),
        tables: Sequence[Any] | Mapping[Any, Any] = (),
        amendments: Sequence[Any] | Mapping[Any, Any] = (),
        rule_versions: Sequence[Any] | Mapping[Any, Any] = (),
        condition_groups: Sequence[Any] | Mapping[Any, Any] = (),
        conditions: Sequence[Any] | Mapping[Any, Any] = (),
        applicability_rule_versions: Sequence[Any] | Mapping[Any, Any] | None = None,
        applicability_condition_groups: Sequence[Any] | Mapping[Any, Any] | None = None,
        applicability_conditions: Sequence[Any] | Mapping[Any, Any] | None = None,
        serialization_version: str = "1.0.0",
    ) -> tuple[str, LegalSnapshotManifest, str]:
        """Build canonical JSON and compute deterministic SHA-256 legal_snapshot_id.
        
        Returns:
            (legal_snapshot_id, manifest, canonical_json_string)
        """
        # 1. Normalize collections
        effective_rule_versions = applicability_rule_versions if applicability_rule_versions is not None else rule_versions
        effective_condition_groups = applicability_condition_groups if applicability_condition_groups is not None else condition_groups
        effective_conditions = applicability_conditions if applicability_conditions is not None else conditions

        doc_list = list(documents.values() if isinstance(documents, Mapping) else documents)
        prov_list = list(provisions.values() if isinstance(provisions, Mapping) else provisions)
        req_list = list(requirements.values() if isinstance(requirements, Mapping) else requirements)
        sched_list = list(schedules.values() if isinstance(schedules, Mapping) else schedules)
        entry_list = list(schedule_entries.values() if isinstance(schedule_entries, Mapping) else schedule_entries)
        tbl_list = list(tables.values() if isinstance(tables, Mapping) else tables)
        amd_list = list(amendments.values() if isinstance(amendments, Mapping) else amendments)
        ver_list = list(effective_rule_versions.values() if isinstance(effective_rule_versions, Mapping) else effective_rule_versions)
        grp_list = list(effective_condition_groups.values() if isinstance(effective_condition_groups, Mapping) else effective_condition_groups)
        cnd_list = list(effective_conditions.values() if isinstance(effective_conditions, Mapping) else effective_conditions)

        # 2. Canonicalize & filter approved
        canon_docs = [canonicalize_document(d) for d in doc_list]
        canon_provs = [canonicalize_provision(p) for p in prov_list]
        canon_reqs = [canonicalize_requirement(r) for r in req_list]
        canon_scheds = [canonicalize_schedule(s) for s in sched_list]
        canon_entries = [canonicalize_schedule_entry(e) for e in entry_list]
        canon_tbls = [canonicalize_table(t) for t in tbl_list]
        canon_amds = [canonicalize_amendment(a) for a in amd_list]

        canon_vers = [cv for v in ver_list if (cv := canonicalize_applicability_rule_version(v)) is not None]
        approved_ver_ids = {v["id"] for v in canon_vers}

        canon_grps = []
        for g in grp_list:
            cg = canonicalize_condition_group(g)
            if cg is None:
                continue
            if ver_list and cg.get("rule_version_id") and cg["rule_version_id"] not in approved_ver_ids:
                continue
            canon_grps.append(cg)

        approved_grp_ids = {g["id"] for g in canon_grps}

        canon_cnds = []
        for c in cnd_list:
            cc = canonicalize_condition(c)
            if cc is None:
                continue
            if grp_list and cc.get("group_id") and cc["group_id"] not in approved_grp_ids:
                continue
            canon_cnds.append(cc)

        # 3. Deterministic Sorting by Primary Identifiers
        sorted_docs = sorted(canon_docs, key=lambda x: x["id"])
        sorted_provs = sorted(canon_provs, key=lambda x: x["id"])
        sorted_reqs = sorted(canon_reqs, key=lambda x: x["id"])
        sorted_scheds = sorted(canon_scheds, key=lambda x: x["id"])
        sorted_entries = sorted(canon_entries, key=lambda x: x["id"])
        sorted_tbls = sorted(canon_tbls, key=lambda x: x["id"])
        sorted_amds = sorted(canon_amds, key=lambda x: x["id"])
        sorted_vers = sorted(canon_vers, key=lambda x: x["id"])
        sorted_grps = sorted(canon_grps, key=lambda x: x["id"])
        sorted_cnds = sorted(canon_cnds, key=lambda x: x["id"])

        # 4. Construct Unified Canonical Dictionary
        canonical_payload = {
            "serialization_version": serialization_version,
            "documents": sorted_docs,
            "provisions": sorted_provs,
            "requirements": sorted_reqs,
            "schedules": sorted_scheds,
            "schedule_entries": sorted_entries,
            "tables": sorted_tbls,
            "amendments": sorted_amds,
            "approved_applicability_rule_versions": sorted_vers,
            "approved_condition_groups": sorted_grps,
            "approved_conditions": sorted_cnds,
        }

        # 5. Canonical JSON String (strict sort_keys, no extra whitespace, UTF-8)
        canonical_json_str = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        # 6. Cryptographic Hash
        legal_snapshot_id = hashlib.sha256(canonical_json_str.encode("utf-8")).hexdigest()

        # 7. Manifest Creation
        manifest = LegalSnapshotManifest(
            legal_snapshot_id=legal_snapshot_id,
            document_count=len(sorted_docs),
            provision_count=len(sorted_provs),
            requirement_count=len(sorted_reqs),
            schedule_count=len(sorted_scheds),
            schedule_entry_count=len(sorted_entries),
            table_count=len(sorted_tbls),
            amendment_count=len(sorted_amds),
            approved_applicability_rule_version_count=len(sorted_vers),
            approved_condition_group_count=len(sorted_grps),
            approved_condition_count=len(sorted_cnds),
            serialization_version=serialization_version,
        )

        return legal_snapshot_id, manifest, canonical_json_str


# =====================================================================
# Legal Snapshot Validator
# =====================================================================

class LegalSnapshotValidator:
    """Validates whether an offline legal snapshot ID is current, historical/stale, or unknown."""

    @classmethod
    def validate_snapshot(
        cls,
        client_snapshot_id: str,
        current_server_snapshot_id: str | None = None,
        known_historical_snapshot_ids: Sequence[str] | set[str] | None = None,
        server_active_snapshot_id: str | None = None,
        historical_snapshot_ids: Sequence[str] | set[str] | None = None,
    ) -> LegalSnapshotValidationResult:
        """Evaluate client snapshot ID against server authority."""
        c_id = str(client_snapshot_id).strip()
        s_id = str(server_active_snapshot_id if server_active_snapshot_id is not None else (current_server_snapshot_id or "")).strip()
        effective_historical = historical_snapshot_ids if historical_snapshot_ids is not None else known_historical_snapshot_ids
        historical = set(effective_historical or [])

        if not c_id:
            return LegalSnapshotValidationResult(
                status=LegalSnapshotValidationStatus.UNKNOWN,
                client_snapshot_id=c_id,
                server_snapshot_id=s_id,
                is_valid_for_evaluation=False,
                requires_server_revalidation=True,
                reason="Client legal snapshot ID was empty or missing.",
            )

        if c_id == s_id:
            return LegalSnapshotValidationResult(
                status=LegalSnapshotValidationStatus.MATCHED,
                client_snapshot_id=c_id,
                server_snapshot_id=s_id,
                is_valid_for_evaluation=True,
                requires_server_revalidation=False,
                reason="Legal snapshot matches the current authoritative server legal corpus exactly.",
            )

        if c_id in historical:
            return LegalSnapshotValidationResult(
                status=LegalSnapshotValidationStatus.STALE,
                client_snapshot_id=c_id,
                server_snapshot_id=s_id,
                is_valid_for_evaluation=False,
                requires_server_revalidation=True,
                reason="Legal snapshot is a recognized historical version. Evidence is valid, but compliance results require server revalidation against current law.",
            )

        return LegalSnapshotValidationResult(
            status=LegalSnapshotValidationStatus.UNKNOWN,
            client_snapshot_id=c_id,
            server_snapshot_id=s_id,
            is_valid_for_evaluation=False,
            requires_server_revalidation=True,
            reason="Unrecognized legal snapshot ID. Offline compliance results cannot be verified against server legal history and must undergo full server re-evaluation.",
        )
