"""Deterministic Evidence Matcher for Phase 5E."""

from __future__ import annotations

from typing import Any, Sequence

from backend.app.services.evidence.models import EvidenceCandidate, EvidenceField, EvidenceStatus
from backend.app.services.verification.models import RequirementReference


class EvidenceMatcher:
    """Matches evidence candidates against requirement target fields and checks consistency."""

    FIELD_ALIASES: dict[str, set[EvidenceField]] = {
        "mrp": {EvidenceField.MRP},
        "maximum_retail_price": {EvidenceField.MRP},
        "retail_sale_price": {EvidenceField.MRP},
        "price": {EvidenceField.MRP},
        "mrp_currency": {EvidenceField.MRP_CURRENCY},
        "net_quantity": {EvidenceField.NET_QUANTITY},
        "quantity": {EvidenceField.NET_QUANTITY},
        "net_weight": {EvidenceField.NET_QUANTITY},
        "net_volume": {EvidenceField.NET_QUANTITY},
        "net_quantity_unit": {EvidenceField.NET_QUANTITY_UNIT},
        "unit": {EvidenceField.NET_QUANTITY_UNIT},
        "manufacturer_name": {EvidenceField.MANUFACTURER_NAME},
        "manufacturer_address": {EvidenceField.MANUFACTURER_ADDRESS},
        "manufacturer": {EvidenceField.MANUFACTURER_NAME, EvidenceField.MANUFACTURER_ADDRESS},
        "packer_name": {EvidenceField.PACKER_NAME},
        "packer_address": {EvidenceField.PACKER_ADDRESS},
        "packer": {EvidenceField.PACKER_NAME, EvidenceField.PACKER_ADDRESS},
        "importer_name": {EvidenceField.IMPORTER_NAME},
        "importer_address": {EvidenceField.IMPORTER_ADDRESS},
        "importer": {EvidenceField.IMPORTER_NAME, EvidenceField.IMPORTER_ADDRESS},
        "consumer_care": {
            EvidenceField.CONSUMER_CARE,
            EvidenceField.CONSUMER_CARE_PHONE,
            EvidenceField.CONSUMER_CARE_EMAIL,
        },
        "consumer_care_phone": {EvidenceField.CONSUMER_CARE_PHONE},
        "consumer_care_email": {EvidenceField.CONSUMER_CARE_EMAIL},
        "customer_care": {
            EvidenceField.CONSUMER_CARE,
            EvidenceField.CONSUMER_CARE_PHONE,
            EvidenceField.CONSUMER_CARE_EMAIL,
        },
        "batch_number": {EvidenceField.BATCH_NUMBER, EvidenceField.LOT_NUMBER},
        "lot_number": {EvidenceField.LOT_NUMBER, EvidenceField.BATCH_NUMBER},
        "manufacture_date": {EvidenceField.MANUFACTURE_DATE},
        "mfg_date": {EvidenceField.MANUFACTURE_DATE},
        "packing_date": {EvidenceField.PACKING_DATE},
        "pkd_date": {EvidenceField.PACKING_DATE},
        "import_date": {EvidenceField.IMPORT_DATE},
        "country_of_origin": {EvidenceField.COUNTRY_OF_ORIGIN},
        "origin": {EvidenceField.COUNTRY_OF_ORIGIN},
        "generic_name": {EvidenceField.COMMODITY_NAME, EvidenceField.GENERIC_DECLARATION},
        "commodity_name": {EvidenceField.COMMODITY_NAME, EvidenceField.GENERIC_DECLARATION},
    }

    @classmethod
    def resolve_target_fields(cls, requirement: RequirementReference) -> set[EvidenceField]:
        target_fields: set[EvidenceField] = set()

        if requirement.target_field:
            if isinstance(requirement.target_field, EvidenceField):
                target_fields.add(requirement.target_field)
            else:
                key = str(requirement.target_field).lower().strip()
                if key in cls.FIELD_ALIASES:
                    target_fields.update(cls.FIELD_ALIASES[key])
                else:
                    try:
                        target_fields.add(EvidenceField(key))
                    except ValueError:
                        pass

        for tf in requirement.target_fields:
            if isinstance(tf, EvidenceField):
                target_fields.add(tf)
            else:
                key = str(tf).lower().strip()
                if key in cls.FIELD_ALIASES:
                    target_fields.update(cls.FIELD_ALIASES[key])
                else:
                    try:
                        target_fields.add(EvidenceField(key))
                    except ValueError:
                        pass

        if not target_fields and requirement.metadata.get("target_field"):
            raw_field = str(requirement.metadata["target_field"]).lower().strip()
            if raw_field in cls.FIELD_ALIASES:
                target_fields.update(cls.FIELD_ALIASES[raw_field])

        return target_fields

    @classmethod
    def match_candidates(
        cls,
        requirement: RequirementReference,
        candidates: Sequence[EvidenceCandidate],
    ) -> list[EvidenceCandidate]:
        target_fields = cls.resolve_target_fields(requirement)
        if not target_fields:
            return []

        matched: list[EvidenceCandidate] = []
        for cand in candidates:
            cand_field = cand.field
            if isinstance(cand_field, str):
                try:
                    cand_field = EvidenceField(cand_field)
                except ValueError:
                    continue
            if cand_field in target_fields:
                matched.append(cand)

        return matched

    @classmethod
    def find_contradictions(
        cls,
        candidates: Sequence[EvidenceCandidate],
    ) -> list[tuple[EvidenceCandidate, EvidenceCandidate]]:
        valid_candidates = [c for c in candidates if c.status == EvidenceStatus.VALID]
        contradictions: list[tuple[EvidenceCandidate, EvidenceCandidate]] = []

        for i in range(len(valid_candidates)):
            for j in range(i + 1, len(valid_candidates)):
                c1 = valid_candidates[i]
                c2 = valid_candidates[j]

                if c1.field != c2.field:
                    continue

                if cls._are_conflicting(c1, c2):
                    contradictions.append((c1, c2))

        return contradictions

    @classmethod
    def _are_conflicting(cls, c1: EvidenceCandidate, c2: EvidenceCandidate) -> bool:
        if c1.field in (EvidenceField.MRP, EvidenceField.MRP_CURRENCY):
            if c1.parsed_value is not None and c2.parsed_value is not None:
                try:
                    v1 = float(c1.parsed_value)
                    v2 = float(c2.parsed_value)
                    if abs(v1 - v2) > 0.001:
                        return True
                except (ValueError, TypeError):
                    if str(c1.parsed_value).strip().lower() != str(c2.parsed_value).strip().lower():
                        return True

        elif c1.field == EvidenceField.NET_QUANTITY:
            if c1.parsed_value is not None and c2.parsed_value is not None:
                if str(c1.parsed_value).strip().lower() != str(c2.parsed_value).strip().lower():
                    return True
            if c1.parsed_unit and c2.parsed_unit:
                if c1.parsed_unit.lower().strip() != c2.parsed_unit.lower().strip():
                    return True

        elif c1.field in (
            EvidenceField.COUNTRY_OF_ORIGIN,
            EvidenceField.MANUFACTURE_DATE,
            EvidenceField.PACKING_DATE,
            EvidenceField.IMPORT_DATE,
            EvidenceField.BATCH_NUMBER,
            EvidenceField.LOT_NUMBER,
        ):
            if c1.parsed_value is not None and c2.parsed_value is not None:
                val1 = str(c1.parsed_value).strip().lower()
                val2 = str(c2.parsed_value).strip().lower()
                if val1 and val2 and val1 != val2:
                    return True

        return False

