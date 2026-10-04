"""Deterministic, statutory evidence parsers for Phase 5D.

Transforms raw OCR observations into structured EvidenceCandidate objects
without performing legal compliance decisions or altering original OCR text.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from backend.app.services.evidence.models import (
    EvidenceCandidate,
    EvidenceField,
    EvidenceStatus,
)
from backend.app.services.evidence.normalization import normalize_evidence_text
from backend.app.services.ocr.models import OCRObservation


class BaseEvidenceParser(ABC):
    """Abstract interface for deterministic statutory declaration parsers."""

    @property
    @abstractmethod
    def parser_name(self) -> str:
        raise NotImplementedError

    @property
    def parser_version(self) -> str:
        return "1.0.0"

    @abstractmethod
    def can_parse(self, text: str) -> bool:
        """Evaluate if the observation text contains triggers relevant to this parser."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, observation: OCRObservation, normalized_text: str) -> list[EvidenceCandidate]:
        """Parse normalized text into one or more structured EvidenceCandidate objects."""
        raise NotImplementedError

    def _create_candidate(
        self,
        observation: OCRObservation,
        field: EvidenceField,
        normalized_text: str,
        parsed_value: Any = None,
        parsed_unit: str | None = None,
        status: EvidenceStatus = EvidenceStatus.VALID,
        parser_confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceCandidate:
        """Helper to construct an EvidenceCandidate strictly preserving raw observation provenance."""
        ocr_conf = observation.confidence if observation.confidence is not None else 1.0
        composite_conf = float(ocr_conf * parser_confidence)

        return EvidenceCandidate(
            observation_id=observation.observation_id,
            image_id=observation.image_id,
            field=field,
            raw_text=observation.text,
            normalized_text=normalized_text,
            parsed_value=parsed_value,
            parsed_unit=parsed_unit,
            ocr_confidence=observation.confidence,
            parser_confidence=parser_confidence,
            confidence=composite_conf,
            bounding_box=observation.bounding_box,
            sequence=observation.sequence,
            parser=self.parser_name,
            parser_version=self.parser_version,
            status=status,
            metadata=metadata or {},
        )


class MRPParser(BaseEvidenceParser):
    """Parser for statutory Maximum Retail Price (MRP / RSP) declarations."""

    _MRP_TRIGGER_RE = re.compile(
        r"\b(?:M\.?R\.?P\.?|MAX(?:IMUM)?\.?\s*RETAIL\s*PRICE|RETAIL\s*SALE\s*PRICE|RSP|RS\.?|INR)\b|₹",
        re.IGNORECASE,
    )
    _CORRUPTED_PRICE_RE = re.compile(
        r"(?:M\.?R\.?P\.?|MAX(?:IMUM)?\.?\s*RETAIL\s*PRICE|RETAIL\s*SALE\s*PRICE|RSP|RS\.?|INR|₹)\s*[:=]?\s*([0-9]+[A-Za-z]+[0-9A-Za-z.]*|[A-Za-z]+[0-9]+[0-9A-Za-z.]*)",
        re.IGNORECASE,
    )
    _NUMERIC_PRICE_RE = re.compile(
        r"(?:₹|RS\.?|INR)?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)",
        re.IGNORECASE,
    )

    @property
    def parser_name(self) -> str:
        return "MRPParser"

    def can_parse(self, text: str) -> bool:
        return bool(self._MRP_TRIGGER_RE.search(text))

    def parse(self, observation: OCRObservation, normalized_text: str) -> list[EvidenceCandidate]:
        candidates: list[EvidenceCandidate] = []
        has_tax_mention = bool(re.search(r"incl(?:usive)?\s*(?:of)?\s*all\s*taxes", normalized_text, re.IGNORECASE))

        # Detect explicit currency
        currency = "INR"
        if "$" in normalized_text or "USD" in normalized_text.upper():
            currency = "USD"
        elif "€" in normalized_text or "EUR" in normalized_text.upper():
            currency = "EUR"
        elif "£" in normalized_text or "GBP" in normalized_text.upper():
            currency = "GBP"

        # Check for corrupted OCR alphanumeric price (e.g. "MRP 12S.00")
        corrupt_match = self._CORRUPTED_PRICE_RE.search(normalized_text)
        if corrupt_match:
            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=EvidenceField.MRP,
                    normalized_text=normalized_text,
                    parsed_value=corrupt_match.group(1),
                    parsed_unit=currency,
                    status=EvidenceStatus.AMBIGUOUS,
                    parser_confidence=0.4,
                    metadata={"error": f"Alphanumeric corrupted price detected: {corrupt_match.group(1)}"},
                )
            )
            return candidates

        # Search for valid price pattern following or near MRP trigger
        match = self._NUMERIC_PRICE_RE.search(normalized_text)
        if match:
            raw_num_str = match.group(1).replace(",", "")
            try:
                price_val = float(raw_num_str)
                has_explicit_mrp_kw = bool(re.search(r"M\.?R\.?P|MAX|RETAIL|RSP", normalized_text, re.IGNORECASE))
                parser_conf = 1.0 if has_explicit_mrp_kw else 0.85
                status = EvidenceStatus.VALID

                candidates.append(
                    self._create_candidate(
                        observation=observation,
                        field=EvidenceField.MRP,
                        normalized_text=normalized_text,
                        parsed_value=price_val,
                        parsed_unit=currency,
                        status=status,
                        parser_confidence=parser_conf,
                        metadata={
                            "currency": currency,
                            "inclusive_of_taxes": has_tax_mention,
                            "explicit_mrp_keyword": has_explicit_mrp_kw,
                        },
                    )
                )
            except ValueError:
                candidates.append(
                    self._create_candidate(
                        observation=observation,
                        field=EvidenceField.MRP,
                        normalized_text=normalized_text,
                        status=EvidenceStatus.AMBIGUOUS,
                        parser_confidence=0.5,
                        metadata={"error": "Numeric conversion failed"},
                    )
                )
        else:
            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=EvidenceField.MRP,
                    normalized_text=normalized_text,
                    status=EvidenceStatus.AMBIGUOUS,
                    parser_confidence=0.4,
                    metadata={"error": "Malformed or missing numeric price after MRP trigger"},
                )
            )

        return candidates


class QuantityParser(BaseEvidenceParser):
    """Parser for statutory Net Quantity / Net Weight / Volume / Count declarations."""

    _UNITS_MAP: dict[str, str] = {
        "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
        "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
        "mg": "mg", "mgs": "mg", "milligram": "mg", "milligrams": "mg",
        "ml": "ml", "mls": "ml", "millilitre": "ml", "millilitres": "ml",
        "milliliter": "ml", "milliliters": "ml", "cl": "cl", "dl": "dl",
        "l": "l", "ltr": "l", "ltrs": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l",
        "cm": "cm", "m": "m", "metre": "m", "metres": "m", "meter": "m", "meters": "m", "mm": "mm",
        "pcs": "pieces", "pc": "pieces", "pieces": "pieces", "piece": "pieces",
        "units": "units", "unit": "units", "u": "units",
        "n": "N", "count": "count", "nos": "units", "no.": "units",
    }

    _NET_QTY_PREFIX_RE = re.compile(
        r"\b(?:NET\s*(?:QTY|QUANTITY|WT|WEIGHT|VOL|VOLUME|CONTENTS?)|QTY|QUANTITY|NET)\b",
        re.IGNORECASE,
    )
    _CORRUPTED_QTY_RE = re.compile(
        r"\b(?:NET\s*(?:QTY|QUANTITY|WT|WEIGHT|VOL|VOLUME|CONTENTS?)|QTY|QUANTITY|NET)\b\s*[:=]?\s*([0-9]+[A-Za-z]+|[A-Za-z]+[0-9]+)",
        re.IGNORECASE,
    )
    _QTY_VAL_UNIT_RE = re.compile(
        r"([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+|\bN\b)",
        re.IGNORECASE,
    )

    @property
    def parser_name(self) -> str:
        return "QuantityParser"

    def can_parse(self, text: str) -> bool:
        has_net_prefix = bool(self._NET_QTY_PREFIX_RE.search(text))
        has_unit = any(re.search(rf"\b{re.escape(u)}\b", text, re.IGNORECASE) for u in self._UNITS_MAP.keys())
        return has_net_prefix or has_unit

    def parse(self, observation: OCRObservation, normalized_text: str) -> list[EvidenceCandidate]:
        candidates: list[EvidenceCandidate] = []
        has_explicit_net = bool(re.search(r"\bNET\b", normalized_text, re.IGNORECASE))
        has_qty_keyword = bool(self._NET_QTY_PREFIX_RE.search(normalized_text))

        # Check for corrupted alphanumeric quantity following Net Qty (e.g. "Net Qty 5OO g")
        corrupted_match = self._CORRUPTED_QTY_RE.search(normalized_text)
        if corrupted_match:
            val_token = corrupted_match.group(1).lower()
            if val_token not in self._UNITS_MAP:
                candidates.append(
                    self._create_candidate(
                        observation=observation,
                        field=EvidenceField.NET_QUANTITY,
                        normalized_text=normalized_text,
                        parsed_value=corrupted_match.group(1),
                        status=EvidenceStatus.AMBIGUOUS,
                        parser_confidence=0.4,
                        metadata={"error": f"Malformed alphanumeric quantity: {corrupted_match.group(1)}"},
                    )
                )
                return candidates

        for match in self._QTY_VAL_UNIT_RE.finditer(normalized_text):
            val_str, unit_raw = match.group(1), match.group(2).lower()
            if unit_raw in self._UNITS_MAP:
                std_unit = self._UNITS_MAP[unit_raw]
                try:
                    num_val = float(val_str)
                    if has_explicit_net or has_qty_keyword:
                        status = EvidenceStatus.VALID
                        parser_conf = 1.0
                        field = EvidenceField.NET_QUANTITY
                    else:
                        status = EvidenceStatus.AMBIGUOUS
                        parser_conf = 0.7
                        field = EvidenceField.NET_QUANTITY

                    candidates.append(
                        self._create_candidate(
                            observation=observation,
                            field=field,
                            normalized_text=normalized_text,
                            parsed_value=num_val,
                            parsed_unit=std_unit,
                            status=status,
                            parser_confidence=parser_conf,
                            metadata={
                                "raw_unit": match.group(2),
                                "explicit_net_prefix": has_explicit_net,
                                "has_qty_keyword": has_qty_keyword,
                            },
                        )
                    )
                except ValueError:
                    continue

        if not candidates and has_qty_keyword:
            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=EvidenceField.NET_QUANTITY,
                    normalized_text=normalized_text,
                    status=EvidenceStatus.AMBIGUOUS,
                    parser_confidence=0.4,
                    metadata={"error": "Malformed numeric quantity following Net Qty trigger"},
                )
            )

        return candidates


class DateParser(BaseEvidenceParser):
    """Parser for statutory manufacturing, packing, import, and expiry date declarations."""

    _IDENTITY_BY_RE = re.compile(
        r"\b(?:MANUFACTURED|MFG|MFD|PACKED|PKG|PKD|IMPORTED|IMP|PRODUCED|MARKETED)\s*(?:&|AND)?\s*BY\b",
        re.IGNORECASE,
    )

    _DATE_PREFIX_MAP: dict[EvidenceField, re.Pattern] = {
        EvidenceField.MANUFACTURE_DATE: re.compile(
            r"\b(?:MFG\s*DATE|MFD\s*DATE|DATE\s*OF\s*MFG|DOM|DATE\s*OF\s*MANUFACTURE|MFG\b(?!\s*BY)|MFD\b(?!\s*BY))\b",
            re.IGNORECASE,
        ),
        EvidenceField.PACKING_DATE: re.compile(
            r"\b(?:PKG\s*DATE|PKD\s*DATE|DATE\s*OF\s*PKG|DATE\s*OF\s*PACKING|PACK\s*DATE|PKG\b(?!\s*BY)|PKD\b(?!\s*BY)|PACKED\b(?!\s*BY))\b",
            re.IGNORECASE,
        ),
        EvidenceField.IMPORT_DATE: re.compile(
            r"\b(?:IMP\s*DATE|DATE\s*OF\s*IMP|DATE\s*OF\s*IMPORT|IMPORT\s*DATE|IMP\b(?!\s*BY)|IMPORTED\b(?!\s*BY))\b",
            re.IGNORECASE,
        ),
    }

    _DATE_PATTERNS = [
        # DD/MM/YYYY or DD-MM-YYYY
        re.compile(r"\b(0[1-9]|[12][0-9]|3[01])[/\-.](0[1-9]|1[0-2])[/\-.](20\d\d|\d\d)\b"),
        # MM/YYYY or MM-YYYY
        re.compile(r"\b(0[1-9]|1[0-2])[/\-.](20\d\d|\d\d)\b"),
        # YYYY-MM-DD (ISO)
        re.compile(r"\b(20\d\d)[/\-.](0[1-9]|1[0-2])[/\-.](0[1-9]|[12][0-9]|3[01])\b"),
        # Month Year e.g. Jan 2026, January 2026
        re.compile(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[/\s,.\-]+(20\d\d|\d\d)\b", re.IGNORECASE),
    ]

    @property
    def parser_name(self) -> str:
        return "DateParser"

    def can_parse(self, text: str) -> bool:
        if self._IDENTITY_BY_RE.search(text):
            # If text is exclusively an identity clause with no date, skip
            if not any(pat.search(text) for pat in self._DATE_PATTERNS):
                return False

        has_date_prefix = any(pat.search(text) for pat in self._DATE_PREFIX_MAP.values())
        has_date_format = any(pat.search(text) for pat in self._DATE_PATTERNS)
        return has_date_prefix or has_date_format

    def parse(self, observation: OCRObservation, normalized_text: str) -> list[EvidenceCandidate]:
        if self._IDENTITY_BY_RE.search(normalized_text) and not any(pat.search(normalized_text) for pat in self._DATE_PATTERNS):
            return []

        candidates: list[EvidenceCandidate] = []

        field = EvidenceField.GENERIC_DECLARATION
        has_explicit_prefix = False
        for fld, pat in self._DATE_PREFIX_MAP.items():
            if pat.search(normalized_text):
                field = fld
                has_explicit_prefix = True
                break

        extracted_date_str = None
        for pat in self._DATE_PATTERNS:
            m = pat.search(normalized_text)
            if m:
                extracted_date_str = m.group(0)
                break

        if extracted_date_str:
            status = EvidenceStatus.VALID if has_explicit_prefix else EvidenceStatus.AMBIGUOUS
            parser_conf = 1.0 if has_explicit_prefix else 0.7

            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=field,
                    normalized_text=normalized_text,
                    parsed_value=extracted_date_str,
                    status=status,
                    parser_confidence=parser_conf,
                    metadata={
                        "date_string": extracted_date_str,
                        "explicit_prefix": has_explicit_prefix,
                    },
                )
            )
        elif has_explicit_prefix:
            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=field,
                    normalized_text=normalized_text,
                    status=EvidenceStatus.AMBIGUOUS,
                    parser_confidence=0.4,
                    metadata={"error": "Malformed date representation following date trigger"},
                )
            )

        return candidates


class ContactParser(BaseEvidenceParser):
    """Parser for statutory consumer care contact information (phone, email, address)."""

    _CONTACT_TRIGGER_RE = re.compile(
        r"\b(?:CONSUMER\s*CARE|CUSTOMER\s*CARE|FEEDBACK|QUERIES|TOLL\s*FREE|HELP\s*LINE|HELPLINE|SUPPORT|CONTACT)\b",
        re.IGNORECASE,
    )
    _PHONE_RE = re.compile(
        r"(?:(?:1800|1860)[-\s]?\d{3}[-\s]?\d{3,4}|\+?91[-\s]?[6-9]\d{9}|0\d{2,4}[-\s]?\d{6,8}|\b\d{10}\b)"
    )
    _EMAIL_RE = re.compile(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    )

    @property
    def parser_name(self) -> str:
        return "ContactParser"

    def can_parse(self, text: str) -> bool:
        return (
            bool(self._CONTACT_TRIGGER_RE.search(text))
            or bool(self._PHONE_RE.search(text))
            or bool(self._EMAIL_RE.search(text))
        )

    def parse(self, observation: OCRObservation, normalized_text: str) -> list[EvidenceCandidate]:
        candidates: list[EvidenceCandidate] = []
        has_contact_ctx = bool(self._CONTACT_TRIGGER_RE.search(normalized_text))

        # 1. Parse Phone Number
        for m in self._PHONE_RE.finditer(normalized_text):
            phone_num = m.group(0).strip()
            status = EvidenceStatus.VALID if has_contact_ctx else EvidenceStatus.AMBIGUOUS
            parser_conf = 1.0 if has_contact_ctx else 0.75

            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=EvidenceField.CONSUMER_CARE_PHONE,
                    normalized_text=normalized_text,
                    parsed_value=phone_num,
                    status=status,
                    parser_confidence=parser_conf,
                    metadata={"contact_context": has_contact_ctx},
                )
            )

        # 2. Parse Email Address
        for m in self._EMAIL_RE.finditer(normalized_text):
            email_addr = m.group(0).strip()
            status = EvidenceStatus.VALID if has_contact_ctx else EvidenceStatus.AMBIGUOUS
            parser_conf = 1.0 if has_contact_ctx else 0.85

            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=EvidenceField.CONSUMER_CARE_EMAIL,
                    normalized_text=normalized_text,
                    parsed_value=email_addr,
                    status=status,
                    parser_confidence=parser_conf,
                    metadata={"contact_context": has_contact_ctx},
                )
            )

        if not candidates and has_contact_ctx:
            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=EvidenceField.CONSUMER_CARE,
                    normalized_text=normalized_text,
                    parsed_value=normalized_text,
                    status=EvidenceStatus.VALID,
                    parser_confidence=0.8,
                    metadata={"contact_context": True},
                )
            )

        return candidates


class IdentityParser(BaseEvidenceParser):
    """Parser for manufacturer, packer, importer, and country of origin declarations."""

    _MFG_RE = re.compile(r"\b(?:MANUFACTURED\s*(?:&|AND)?\s*PACKED\s*BY|MANUFACTURED\s*BY|MFD\s*BY|MFG\s*BY|PRODUCED\s*BY)\b\s*:?\s*(.+)", re.IGNORECASE)
    _PKD_RE = re.compile(r"\b(?:PACKED\s*BY|PKD\s*BY|PACKAGED\s*BY|MARKETED\s*BY)\b\s*:?\s*(.+)", re.IGNORECASE)
    _IMP_RE = re.compile(r"\b(?:IMPORTED\s*BY|IMP\s*BY)\b\s*:?\s*(.+)", re.IGNORECASE)
    _COO_RE = re.compile(r"\b(?:COUNTRY\s*OF\s*ORIGIN|MADE\s*IN|PRODUCT\s*OF)\b\s*:?\s*(.+)", re.IGNORECASE)

    @property
    def parser_name(self) -> str:
        return "IdentityParser"

    def can_parse(self, text: str) -> bool:
        return bool(
            self._MFG_RE.search(text)
            or self._PKD_RE.search(text)
            or self._IMP_RE.search(text)
            or self._COO_RE.search(text)
        )

    def parse(self, observation: OCRObservation, normalized_text: str) -> list[EvidenceCandidate]:
        candidates: list[EvidenceCandidate] = []

        m_mfg = self._MFG_RE.search(normalized_text)
        m_pkd = self._PKD_RE.search(normalized_text)
        m_imp = self._IMP_RE.search(normalized_text)
        m_coo = self._COO_RE.search(normalized_text)

        # Prioritize single identity declaration per clause
        if m_mfg:
            val = m_mfg.group(1).strip()
            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=EvidenceField.MANUFACTURER_NAME,
                    normalized_text=normalized_text,
                    parsed_value=val or normalized_text,
                    status=EvidenceStatus.VALID,
                    parser_confidence=0.95,
                )
            )
        elif m_imp:
            val = m_imp.group(1).strip()
            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=EvidenceField.IMPORTER_NAME,
                    normalized_text=normalized_text,
                    parsed_value=val or normalized_text,
                    status=EvidenceStatus.VALID,
                    parser_confidence=0.95,
                )
            )
        elif m_pkd:
            val = m_pkd.group(1).strip()
            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=EvidenceField.PACKER_NAME,
                    normalized_text=normalized_text,
                    parsed_value=val or normalized_text,
                    status=EvidenceStatus.VALID,
                    parser_confidence=0.95,
                )
            )

        if m_coo:
            val = m_coo.group(1).strip()
            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=EvidenceField.COUNTRY_OF_ORIGIN,
                    normalized_text=normalized_text,
                    parsed_value=val or normalized_text,
                    status=EvidenceStatus.VALID,
                    parser_confidence=0.95,
                )
            )

        return candidates


class BatchParser(BaseEvidenceParser):
    """Parser for statutory Batch Number and Lot Number declarations."""

    _BATCH_TRIGGER_RE = re.compile(
        r"\b(?:BATCH\s*(?:NO\.?|#|NUMBER)|B\.?\s*NO\.?|LOT\s*(?:NO\.?|#|NUMBER)|LOT)\b\s*:?\s*(.+)?",
        re.IGNORECASE,
    )

    @property
    def parser_name(self) -> str:
        return "BatchParser"

    def can_parse(self, text: str) -> bool:
        return bool(self._BATCH_TRIGGER_RE.search(text))

    def parse(self, observation: OCRObservation, normalized_text: str) -> list[EvidenceCandidate]:
        candidates: list[EvidenceCandidate] = []
        match = self._BATCH_TRIGGER_RE.search(normalized_text)

        if match:
            captured_val = match.group(1)
            parsed_code = captured_val.strip() if captured_val else normalized_text
            is_lot = bool(re.search(r"\bLOT\b", normalized_text, re.IGNORECASE))
            field = EvidenceField.LOT_NUMBER if is_lot else EvidenceField.BATCH_NUMBER

            candidates.append(
                self._create_candidate(
                    observation=observation,
                    field=field,
                    normalized_text=normalized_text,
                    parsed_value=parsed_code,
                    status=EvidenceStatus.VALID,
                    parser_confidence=0.95,
                    metadata={"is_lot": is_lot},
                )
            )

        return candidates


class GenericParser(BaseEvidenceParser):
    """Fallback parser for unclassified OCR observations."""

    @property
    def parser_name(self) -> str:
        return "GenericParser"

    def can_parse(self, text: str) -> bool:
        return True

    def parse(self, observation: OCRObservation, normalized_text: str) -> list[EvidenceCandidate]:
        return [
            self._create_candidate(
                observation=observation,
                field=EvidenceField.GENERIC_DECLARATION,
                normalized_text=normalized_text,
                parsed_value=normalized_text,
                status=EvidenceStatus.UNPARSED,
                parser_confidence=0.5,
            )
        ]

