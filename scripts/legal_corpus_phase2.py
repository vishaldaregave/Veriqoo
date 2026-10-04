from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from pypdf import PdfReader

from scripts.legal_corpus_db_adapter import (
    PHASE1_PAYLOAD_COLUMNS,
    SchemaAdapterError,
    preview_serialized_groups,
    provision_source_location,
    serialize_phase1_document,
    serialize_phase1_provision,
    serialize_phase2_record,
)
from scripts.legal_corpus_parser import (
    CLAUSE_RE,
    EXPLANATION_RE,
    PROVISO_RE,
    RULES_BODY_START_RE,
    SUB_RULE_RE,
    TOP_LEVEL_RULE_RE,
    LegalDocument,
    _normalize_rule_number,
    extract_pdf_text,
    parse_document,
)


ID_NAMESPACE = uuid.UUID("d45df540-0a50-45c4-a6f0-2c4c8c62b519")
RULE_SEQUENCE = [str(number) for number in range(1, 33)] + ["32A", "33", "34"]
SCHEDULE_ORDINALS = {
    "FIRST": "1",
    "SECOND": "2",
    "THIRD": "3",
    "FOURTH": "4",
    "FIFTH": "5",
    "SIXTH": "6",
    "SEVENTH": "7",
}
SCHEDULE_HEADER_RE = re.compile(
    r"^\s*[*$#]*\s*THE\s+(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH)\s+SCHEDULE\b",
    re.IGNORECASE,
)
DATE_HEADER_RE = re.compile(r"^\s*\d{1,2}\.\d{1,2}\.\d{4}(?:\b|[.)])")
ENTRY_RE = re.compile(
    r"^\s*[*$#]*\s*(?:(?P<number>\d{1,2})\s*\.\s+|\((?P<label>[a-z]|[ivxlcdm]+)\)\s*)(?P<body>.*)$",
    re.IGNORECASE,
)
AMENDMENT_CITATION_RE = re.compile(
    r"\b((?:G\s*\.?\s*S\s*\.?\s*R\s*\.?|S\s*\.?\s*O\s*\.?)\s*[\d,]+(?:\s*\([A-Z]\))?)(?![A-Za-z0-9])",
    re.IGNORECASE,
)
AMENDMENT_DATE_RE = re.compile(
    r"\b(?:dated|date\s+of)\s+(\d{1,2}\s*(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})\b",
    re.IGNORECASE,
)
EFFECTIVE_DATE_RE = re.compile(
    r"\b(?:w\s*\.?\s*e\s*\.?\s*f\s*\.?|with\s+effect\s+from)\s*((?:\d{1,2}\s*(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})|(?:\d{1,2}\.\d{1,2}\.\d{4}))\b",
    re.IGNORECASE,
)
MONTHS = {
    name.lower(): number
    for number, names in enumerate(
        (
            ("January", "Jan"),
            ("February", "Feb"),
            ("March", "Mar"),
            ("April", "Apr"),
            ("May",),
            ("June", "Jun"),
            ("July", "Jul"),
            ("August", "Aug"),
            ("September", "Sep", "Sept"),
            ("October", "Oct"),
            ("November", "Nov"),
            ("December", "Dec"),
        ),
        start=1,
    )
    for name in names
}


@dataclass(frozen=True)
class SourceLine:
    page: int
    page_line: int
    document_line: int
    text: str


@dataclass
class Phase2Corpus:
    document: dict[str, Any]
    provisions: list[dict[str, Any]]
    schedules: list[dict[str, Any]]
    schedule_entries: list[dict[str, Any]]
    tables: list[dict[str, Any]]
    amendments: list[dict[str, Any]]
    requirements: list[dict[str, Any]]
    unresolved_structures: list[dict[str, Any]]
    normalization_warnings: list[dict[str, Any]]


def normalize_legal_text(raw_text: str) -> str:
    text = unicodedata.normalize("NFC", raw_text or "")
    text = text.replace("\u00ad", "").replace("\u00a0", " ")
    return " ".join(text.split())


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_id(source_identifier: str) -> str:
    return str(uuid.uuid5(ID_NAMESPACE, source_identifier))


def _source_identifier(document_hash: str, kind: str, locator: str, raw_text: str) -> str:
    return _stable_hash("\0".join((document_hash, kind, locator, raw_text)))


def _date_from_explicit_text(value: str | None) -> str | None:
    if not value:
        return None
    numeric = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", value)
    if numeric:
        try:
            return date(int(numeric.group(3)), int(numeric.group(2)), int(numeric.group(1))).isoformat()
        except ValueError:
            return None
    match = re.search(r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})", value, re.I)
    if not match:
        return None
    month = MONTHS.get(match.group(2).lower())
    if month is None:
        return None
    try:
        return date(int(match.group(3)), month, int(match.group(1))).isoformat()
    except ValueError:
        return None


def _line_index(pages: list[str]) -> tuple[list[SourceLine], list[str]]:
    full_text = "\n".join(pages)
    line_offsets = [0]
    line_offsets.extend(index + 1 for index, char in enumerate(full_text) if char == "\n")
    page_lines: list[SourceLine] = []
    page_offset = 0
    for page_number, page_text in enumerate(pages, start=1):
        local_offset = 0
        for page_line, raw_line in enumerate(page_text.splitlines(keepends=True), start=1):
            text = raw_line.rstrip("\r\n")
            document_line = bisect_right(line_offsets, page_offset + local_offset)
            page_lines.append(SourceLine(page_number, page_line, document_line, text))
            local_offset += len(raw_line)
        page_offset += len(page_text) + 1
    return page_lines, full_text.splitlines()


def _line_payload(lines: Iterable[SourceLine]) -> tuple[str, int | None, int | None, int | None, int | None]:
    selected = list(lines)
    raw = "\n".join(line.text for line in selected)
    if not selected:
        return raw, None, None, None, None
    return raw, selected[0].page, selected[0].page_line, selected[-1].page, selected[-1].page_line


def _rule_headers(lines: list[SourceLine]) -> list[tuple[int, re.Match[str]]]:
    return [
        (index, match)
        for index, line in enumerate(lines)
        if (match := TOP_LEVEL_RULE_RE.match(line.text)) and not DATE_HEADER_RE.match(line.text)
    ]


def _find_rule_body(lines: list[SourceLine]) -> tuple[int, int]:
    start = next(
        (index + 1 for index, line in enumerate(lines) if RULES_BODY_START_RE.search(line.text)),
        None,
    )
    if start is None:
        raise ValueError("Could not locate the rules body in the source PDF")
    end = next(
        (
            index
            for index in range(start, len(lines))
            if re.match(r"^\s*THE\s+FIRST\s+SCHEDULE\b", lines[index].text, re.I)
        ),
        None,
    )
    if end is None:
        raise ValueError("Could not locate the First Schedule boundary in the source PDF")
    return start, end


def _canonical_rule_lines(lines: list[SourceLine]) -> list[tuple[str, int, str]]:
    body_start, body_end = _find_rule_body(lines)
    region = lines[body_start:body_end]
    candidates = _rule_headers(region)
    selected: list[tuple[str, int, str]] = []
    cursor = 0
    for expected in RULE_SEQUENCE:
        found = None
        for index, match in candidates:
            if index < cursor:
                continue
            if _normalize_rule_number(match.group(1)) == expected:
                found = (index, match.group(2).strip())
                break
        if found is None:
            raise ValueError(f"Source PDF does not contain expected top-level rule {expected}")
        cursor, title = found
        selected.append((expected, body_start + cursor, title))
        cursor += 1
    return selected


def _make_record(document_hash: str, kind: str, locator: str, raw_text: str, **fields: Any) -> dict[str, Any]:
    source_identifier = _source_identifier(document_hash, kind, locator, raw_text)
    return {
        "id": _stable_id(source_identifier),
        "source_identifier": source_identifier,
        "raw_content": raw_text,
        "normalized_content": normalize_legal_text(raw_text),
        **fields,
    }


def _rule_and_child_records(
    document_hash: str,
    document_id: str,
    lines: list[SourceLine],
) -> list[dict[str, Any]]:
    selected = _canonical_rule_lines(lines)
    body_end = _find_rule_body(lines)[1]
    provisions: list[dict[str, Any]] = []
    for position, (rule_number, start, title) in enumerate(selected):
        end = selected[position + 1][1] if position + 1 < len(selected) else body_end
        block = lines[start:end]
        raw, source_page, line_start, source_page_end, line_end = _line_payload(block)
        hierarchy_path = [rule_number]
        locator = f"rule:{rule_number}:{block[0].document_line}"
        rule = _make_record(
            document_hash,
            "provision",
            locator,
            raw,
            document_id=document_id,
            parent_id=None,
            provision_type="rule",
            rule_number=rule_number,
            subrule_identifier=None,
            clause_number=None,
            title=title,
            source_page=source_page,
            source_page_end=source_page_end,
            source_line_start=line_start,
            source_line_end=line_end,
            document_line_start=block[0].document_line,
            document_line_end=block[-1].document_line,
            hierarchy_path=hierarchy_path,
            sequence=position + 1,
            amendment_metadata={},
            effective_from=None,
            effective_to=None,
            is_active=None,
            applicability_metadata={},
        )
        provisions.append(rule)
        anchors = _child_anchors(block)
        active_subrule: dict[str, Any] | None = None
        for child_position, anchor in enumerate(anchors):
            child_end = anchors[child_position + 1]["index"] if child_position + 1 < len(anchors) else len(block)
            child_lines = block[anchor["index"]:child_end]
            child_raw, child_page, child_line_start, child_page_end, child_line_end = _line_payload(child_lines)
            if anchor["type"] == "sub_rule":
                parent_id = rule["id"]
                parent_path = hierarchy_path
            else:
                parent_id = active_subrule["id"] if active_subrule else rule["id"]
                parent_path = active_subrule["hierarchy_path"] if active_subrule else hierarchy_path
            child_path = parent_path + [anchor["label"]]
            child_locator = f"{locator}:{anchor['type']}:{child_lines[0].document_line}"
            child = _make_record(
                document_hash,
                "provision",
                child_locator,
                child_raw,
                document_id=document_id,
                parent_id=parent_id,
                provision_type=anchor["type"],
                rule_number=rule_number,
                subrule_identifier=anchor["label"] if anchor["type"] == "sub_rule" else None,
                clause_number=anchor["label"] if anchor["type"] == "clause" else None,
                title=anchor["title"],
                source_page=child_page,
                source_page_end=child_page_end,
                source_line_start=child_line_start,
                source_line_end=child_line_end,
                document_line_start=child_lines[0].document_line,
                document_line_end=child_lines[-1].document_line,
                hierarchy_path=child_path,
                sequence=child_position + 1,
                amendment_metadata={},
                effective_from=None,
                effective_to=None,
                is_active=None,
                applicability_metadata={},
            )
            provisions.append(child)
            if anchor["type"] == "sub_rule":
                active_subrule = {"id": child["id"], "hierarchy_path": child_path}
    return provisions


def _child_anchors(block: list[SourceLine]) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for index, source_line in enumerate(block):
        text = source_line.text.strip()
        top_header = bool(TOP_LEVEL_RULE_RE.match(text))
        content = TOP_LEVEL_RULE_RE.sub("", text, count=1).strip() if top_header else text
        subrule = SUB_RULE_RE.match(content) if content else None
        clause = CLAUSE_RE.match(content) if content else None
        if subrule and subrule.group(1).isdigit():
            anchors.append({"index": index, "type": "sub_rule", "label": subrule.group(1), "title": subrule.group(2).strip()})
        elif clause:
            anchors.append({"index": index, "type": "clause", "label": clause.group(1), "title": clause.group(2).strip()})
        elif PROVISO_RE.search(text):
            anchors.append({"index": index, "type": "proviso", "label": f"proviso-{len(anchors) + 1}", "title": text[:120]})
        elif EXPLANATION_RE.search(text):
            anchors.append({"index": index, "type": "explanation", "label": f"explanation-{len(anchors) + 1}", "title": text[:120]})
    return anchors


def _layout_lines(pdf_path: Path) -> list[SourceLine]:
    reader = PdfReader(str(pdf_path))
    records: list[SourceLine] = []
    document_line = 0
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except (TypeError, ValueError):
            text = page.extract_text() or ""
        for page_line, line in enumerate(text.splitlines(), start=1):
            document_line += 1
            records.append(SourceLine(page_number, page_line, document_line, line))
    return records


def _schedule_records(
    document_hash: str,
    document_id: str,
    layout: list[SourceLine],
    rules: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rule_34 = next(rule for rule in rules if rule["rule_number"] == "34")
    candidates = [
        (index, match)
        for index, line in enumerate(layout)
        if (match := SCHEDULE_HEADER_RE.match(line.text)) and line.page >= rule_34["source_page"]
    ]
    actual: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for index, match in candidates:
        ordinal = match.group(1).upper()
        number = SCHEDULE_ORDINALS[ordinal]
        if number not in seen:
            seen.add(number)
            actual.append((index, ordinal, number))
    expected = [str(number) for number in range(1, 8)]
    if [number for _, _, number in actual] != expected:
        raise ValueError(f"Expected source schedule sequence {expected}, found {[number for _, _, number in actual]}")

    schedules: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for position, (start, ordinal, number) in enumerate(actual):
        end = actual[position + 1][0] if position + 1 < len(actual) else len(layout)
        block = layout[start:end]
        raw, page_start, line_start, page_end, line_end = _line_payload(block)
        title = f"{ordinal.title()} Schedule"
        locator = f"schedule:{number}:{block[0].page}:{block[0].page_line}"
        schedule = _make_record(
            document_hash,
            "schedule",
            locator,
            raw,
            document_id=document_id,
            schedule_number=number,
            title=title,
            source_page=page_start,
            source_page_end=page_end,
            source_line_start=line_start,
            source_line_end=line_end,
            sequence=position + 1,
            structure_status="raw_preserved",
        )
        see_rule = re.search(r"\bSee\s+Rule\s+(\d{1,2}[A-Z]?)\b", raw, re.I)
        if see_rule:
            schedule["referenced_rule_number"] = _normalize_rule_number(see_rule.group(1))
        elif number == "7":
            cited_rules = [
                rule["rule_number"]
                for rule in rules
                if re.search(r"\bSeventh\s+Schedule\b", rule["raw_content"], re.I)
            ]
            if len(cited_rules) == 1:
                schedule["referenced_rule_number"] = cited_rules[0]
        else:
            schedule["referenced_rule_number"] = None
        schedules.append(schedule)
        schedule_entries, schedule_unresolved = _schedule_entry_records(
            document_hash, schedule, block, position + 1
        )
        entries.extend(schedule_entries)
        unresolved.extend(schedule_unresolved)
        tables.extend(_schedule_table_records(document_hash, document_id, schedule, block))
        if not schedule_entries:
            unresolved.append({
                "source_identifier": schedule["source_identifier"],
                "structure_type": "schedule_entries",
                "reason": "No explicit numbered row or labeled form was extracted; raw schedule text is retained.",
            })
    return schedules, entries, tables, unresolved


def _schedule_entry_records(
    document_hash: str,
    schedule: dict[str, Any],
    block: list[SourceLine],
    schedule_sequence: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    anchors: list[tuple[int, str, str, str]] = []
    for index, line in enumerate(block):
        text = line.text.strip()
        match = ENTRY_RE.match(text)
        if match:
            number = match.group("number")
            label = match.group("label")
            if number:
                body = match.group("body")
                if schedule["schedule_number"] == "4" and number == "1" and body.lower().startswith("the following commodities"):
                    continue
                if re.fullmatch(r"(?:\d+[.)]\s*)+", body):
                    continue
                if schedule["schedule_number"] == "6":
                    entry_type = "numbered_paragraph"
                elif schedule["schedule_number"] == "5" and (
                    body.lower().startswith(("for determination", "the sample shall", "where,"))
                ):
                    entry_type = "numbered_paragraph"
                elif schedule["schedule_number"] == "1" and body.lower().startswith("maximum permissible errors"):
                    entry_type = "numbered_paragraph"
                else:
                    entry_type = "numbered_entry"
                key = number
            else:
                entry_type = "subentry"
                key = label.lower()
            anchors.append((index, key, entry_type, match.group("body")))
            continue
        if schedule["schedule_number"] == "5" and re.match(r"^\s*(?:Less than|More than)\s+\d", text, re.I):
            anchors.append((index, text.strip(), "table_row", text.strip()))
        elif schedule["schedule_number"] == "7" and re.match(r"^\s*Form\s+[AB]\b", text, re.I):
            label_match = re.search(r"Form\s+[AB]", text, re.I)
            anchors.append((index, label_match.group(0), "form", text.strip()))

    result: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    parent_entry_id: str | None = None
    row_starts = [anchor[0] for anchor in anchors]
    if schedule["schedule_number"] == "2":
        for anchor_index, (anchor_start, _, _, _) in enumerate(anchors):
            lower_bound = anchors[anchor_index - 1][0] + 1 if anchor_index else 0
            cursor = anchor_start - 1
            while cursor >= lower_bound and block[cursor].text.strip():
                cursor -= 1
            row_starts[anchor_index] = cursor + 1

    for sequence, (start, key, entry_type, body_start) in enumerate(anchors, start=1):
        row_start = row_starts[sequence - 1]
        end = row_starts[sequence] if sequence < len(anchors) else len(block)
        source_block = block[row_start:end]
        raw, page_start, line_start, page_end, line_end = _line_payload(source_block)
        if entry_type == "numbered_entry":
            parent_entry_id = None
        elif entry_type != "subentry":
            parent_entry_id = None
        cells = _layout_cells(body_start)
        item_text = cells[0] if len(cells) >= 2 else None
        quantity_text = " ".join(cells[1:]) if len(cells) >= 2 else None
        if entry_type in {"form", "numbered_paragraph"}:
            item_text = body_start
            quantity_text = None
        if schedule["schedule_number"] == "3" and entry_type == "numbered_entry":
            item_text = body_start
            quantity_text = None
        if schedule["schedule_number"] == "2":
            item_text = cells[0] if len(cells) == 2 else None
            quantity_text = cells[1] if len(cells) == 2 else None
            prefix_lines = block[row_start:start]
            prefix_is_quantity = all(
                len(line.text) - len(line.text.lstrip()) >= 35
                for line in prefix_lines
                if line.text.strip()
            )
            prefix_values = [line.text.strip() for line in prefix_lines if line.text.strip()]
            continuation_values = [
                line.text.strip()
                for line in block[start + 1:end]
                if line.text.strip()
                and len(line.text) - len(line.text.lstrip()) >= 35
                and not re.fullmatch(r"\d{1,3}", line.text.strip())
            ]
            if item_text and quantity_text and prefix_is_quantity:
                quantity_text = " ".join(prefix_values + [quantity_text] + continuation_values)
            elif prefix_lines:
                item_text = None
                quantity_text = None
        split_word_artifact = len(cells) > 2 or (
            schedule["schedule_number"] == "2" and bool(prefix_lines) and not prefix_is_quantity
        )
        if schedule["schedule_number"] == "4" and len(cells) != 2:
            item_text = None
            quantity_text = None
        locator = f"schedule:{schedule['schedule_number']}:entry:{key}:{source_block[0].page}:{source_block[0].page_line}"
        entry = _make_record(
            document_hash,
            "schedule_entry",
            locator,
            raw,
            schedule_id=schedule["id"],
            table_id=None,
            parent_entry_id=parent_entry_id,
            entry_key=key,
            entry_type=entry_type,
            entry_number=key if key.isdigit() else None,
            item_text=item_text,
            commodity_text=item_text,
            quantity_text=quantity_text,
            permitted_package_quantity=quantity_text if schedule["schedule_number"] == "2" else None,
            cells=cells,
            source_page=page_start,
            source_page_end=page_end,
            source_line_start=line_start,
            source_line_end=line_end,
            sequence=sequence,
            structure_status=(
                "explicit_label"
                if entry_type in {"form", "subentry", "numbered_paragraph"}
                or (entry_type == "table_row" and len(cells) == 2)
                or (schedule["schedule_number"] == "3" and item_text)
                or (schedule["schedule_number"] in {"2", "4"} and item_text and quantity_text and not split_word_artifact)
                else "raw_row_unresolved"
            ),
            metadata={"schedule_sequence": schedule_sequence},
        )
        result.append(entry)
        if entry_type == "numbered_entry":
            parent_entry_id = entry["id"]
        if entry["structure_status"] == "raw_row_unresolved":
            unresolved.append({
                "source_identifier": entry["source_identifier"],
                "structure_type": "schedule_entry_columns",
                "reason": "The row label was explicit but item/quantity columns could not be separated confidently.",
            })
    return result, unresolved


def _layout_cells(text: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"\s{2,}", text.strip()) if cell.strip()]


def _schedule_table_records(
    document_hash: str,
    document_id: str,
    schedule: dict[str, Any],
    block: list[SourceLine],
) -> list[dict[str, Any]]:
    number = schedule["schedule_number"]
    patterns: list[tuple[str, re.Pattern[str]]] = []
    if number == "1":
        patterns = [("TABLE-I", re.compile(r"^\s*TABLE\s*-?\s*I\s*$", re.I)), ("TABLE-II", re.compile(r"^\s*TABLE\s*-?\s*II\s*$", re.I))]
    elif number == "2":
        patterns = [("commodities-quantities", re.compile(r"^\s*Sl\.?\s+Commodities\s+Quantities", re.I))]
    elif number == "3":
        patterns = [("commodity-list", re.compile(r"^\s*Sl\.?\s*No\.?\s+Name\s+of\s+commodity", re.I))]
    elif number == "4":
        patterns = [("declaration-units", re.compile(r"^\s*TABLE\s*$", re.I))]
    elif number == "5":
        patterns = [
            ("lot-sample-size", re.compile(r"^\s*Lot\s+Size\s+Sample\s+Size\s*$", re.I)),
            ("inspection-lot-correction", re.compile(r"Serial\s+numb.*Inspection\s+lot.*Correctio", re.I)),
        ]
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(block):
        for name, pattern in patterns:
            if pattern.search(line.text):
                starts.append((index, name))
                break
    result: list[dict[str, Any]] = []
    for position, (start, name) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(block)
        table_block = block[start:end]
        raw, page_start, line_start, page_end, line_end = _line_payload(table_block)
        locator = f"schedule:{number}:table:{name}:{table_block[0].page}:{table_block[0].page_line}"
        result.append(
            _make_record(
                document_hash,
                "table",
                locator,
                raw,
                document_id=document_id,
                schedule_id=schedule["id"],
                provision_id=None,
                table_identifier=name,
                title=next((line.text.strip() for line in table_block[1:5] if line.text.strip()), name),
                headers=[],
                source_page=page_start,
                source_page_end=page_end,
                source_line_start=line_start,
                source_line_end=line_end,
                sequence=position + 1,
                structure_status="raw_preserved",
            )
        )
    return result


def _paragraph_blocks(lines: list[SourceLine]) -> list[list[SourceLine]]:
    blocks: list[list[SourceLine]] = []
    current: list[SourceLine] = []
    for line in lines:
        if line.text.strip():
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _amendment_records(
    document_hash: str,
    document_id: str,
    lines: list[SourceLine],
    provisions: list[dict[str, Any]],
    schedules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    amendment_terms = re.compile(r"\b(?:substitut(?:ed|ion)|insert(?:ed|ion)|omit(?:ted|sion)|amend(?:ed|ment))\b", re.I)
    citation_terms = re.compile(r"\b(?:vide\s+)?(?:G\s*\.?\s*S\s*\.?\s*R\s*\.?|S\s*\.?\s*O\s*\.?|notification)\b", re.I)
    for sequence, block in enumerate(_paragraph_blocks(lines), start=1):
        raw, page_start, line_start, page_end, line_end = _line_payload(block)
        if not amendment_terms.search(raw) or not citation_terms.search(raw):
            continue
        first_line = block[0].document_line
        affected = next(
            (
                provision
                for provision in provisions
                if provision["document_line_start"] is not None
                and provision["document_line_end"] is not None
                and provision["document_line_start"] <= first_line <= provision["document_line_end"]
            ),
            None,
        )
        affected_schedule = next(
            (
                schedule
                for schedule in schedules
                if schedule["source_page"] <= page_start <= schedule["source_page_end"]
            ),
            None,
        )
        identifier_match = AMENDMENT_CITATION_RE.search(raw)
        amendment_date_match = AMENDMENT_DATE_RE.search(raw)
        effective_match = EFFECTIVE_DATE_RE.search(raw)
        locator = f"amendment:{page_start}:{line_start}:{sequence}"
        result.append(
            _make_record(
                document_hash,
                "amendment",
                locator,
                raw,
                document_id=document_id,
                affected_provision_id=affected["id"] if affected else None,
                affected_schedule_id=affected_schedule["id"] if affected_schedule else None,
                amendment_identifier=identifier_match.group(1).strip() if identifier_match else None,
                amendment_date=_date_from_explicit_text(amendment_date_match.group(1)) if amendment_date_match else None,
                effective_date=_date_from_explicit_text(effective_match.group(1)) if effective_match else None,
                source_page=page_start,
                source_page_end=page_end,
                source_line_start=line_start,
                source_line_end=line_end,
                sequence=len(result) + 1,
            )
        )
    return result


def _provision_tables(
    document_hash: str,
    document_id: str,
    layout: list[SourceLine],
    provisions: list[dict[str, Any]],
    schedules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    marker = re.compile(r"^\s*TABLE\s*(?:[-–]\s*)?(?:[IVX]+|\d+)?\s*$", re.I)
    table_headers = [(index, line) for index, line in enumerate(layout) if marker.match(line.text)]
    schedule_pages = {schedule["source_page"] for schedule in schedules}
    result: list[dict[str, Any]] = []
    for index, (start, line) in enumerate(table_headers):
        if line.page in schedule_pages:
            continue
        end = table_headers[index + 1][0] if index + 1 < len(table_headers) else len(layout)
        raw, page_start, line_start, page_end, line_end = _line_payload(layout[start:end])
        containing = next(
            (
                provision
                for provision in provisions
                if provision["source_page"] <= page_start <= provision["source_page_end"]
            ),
            None,
        )
        locator = f"table:provision:{page_start}:{line_start}:{line.text.strip()}"
        result.append(
            _make_record(
                document_hash,
                "table",
                locator,
                raw,
                document_id=document_id,
                schedule_id=None,
                provision_id=containing["id"] if containing else None,
                table_identifier=line.text.strip(),
                title=line.text.strip(),
                headers=[],
                source_page=page_start,
                source_page_end=page_end,
                source_line_start=line_start,
                source_line_end=line_end,
                sequence=len(result) + 1,
                structure_status="raw_preserved",
            )
        )
    return result


def _requirement_records(
    document_hash: str,
    provisions: list[dict[str, Any]],
    schedules: list[dict[str, Any]],
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for sequence, provision in enumerate(provisions, start=1):
        raw = provision["raw_content"]
        locator = f"requirement:{provision['source_identifier']}"
        normalized = normalize_legal_text(raw)
        result.append(
            _make_record(
                document_hash,
                "requirement",
                locator,
                raw,
                provision_id=provision["id"],
                requirement_type="unclassified_provision",
                requirement_text=normalized,
                normalized_requirement=normalized,
                subject=None,
                condition_text=None,
                obligation=None,
                exception_text=None,
                applicability_metadata={},
                evidence_type=[],
                source_quote=raw,
                source_reference={
                    "source_page": provision["source_page"],
                    "source_line_start": provision["source_line_start"],
                    "source_line_end": provision["source_line_end"],
                    "hierarchy_path": provision["hierarchy_path"],
                },
                sequence=sequence,
                review_status="requires_review",
                effective_from=provision["effective_from"],
                effective_to=provision["effective_to"],
                is_active=provision["is_active"],
            )
        )
    schedules_by_id = {schedule["id"]: schedule for schedule in schedules}
    for sequence, entry in enumerate(entries, start=len(result) + 1):
        schedule = schedules_by_id[entry["schedule_id"]]
        source_provision_id = schedule["source_provision_id"]
        raw = entry["raw_content"]
        normalized = normalize_legal_text(raw)
        locator = f"requirement:{entry['source_identifier']}"
        result.append(
            _make_record(
                document_hash,
                "requirement",
                locator,
                raw,
                provision_id=source_provision_id,
                schedule_entry_id=entry["id"],
                requirement_type="unclassified_schedule_entry",
                requirement_text=normalized,
                normalized_requirement=normalized,
                subject=None,
                condition_text=None,
                obligation=None,
                exception_text=None,
                applicability_metadata={},
                evidence_type=[],
                source_quote=raw,
                source_reference={
                    "schedule_id": schedule["id"],
                    "schedule_entry_id": entry["id"],
                    "source_page": entry["source_page"],
                    "source_line_start": entry["source_line_start"],
                    "source_line_end": entry["source_line_end"],
                    "hierarchy_path": ["schedule", schedule["schedule_number"], entry["entry_key"]],
                },
                sequence=sequence,
                review_status="requires_review",
                effective_from=None,
                effective_to=None,
                is_active=None,
            )
        )
    return result


def _schedule_provision_records(
    document_hash: str,
    document_id: str,
    schedules: list[dict[str, Any]],
    rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rule_ids = {rule["rule_number"]: rule["id"] for rule in rules}
    result = []
    for sequence, schedule in enumerate(schedules, start=1):
        locator = f"schedule-provision:{schedule['schedule_number']}:{schedule['source_page']}:{schedule['source_line_start']}"
        provision = _make_record(
            document_hash,
            "provision",
            locator,
            schedule["raw_content"],
            document_id=document_id,
            parent_id=None,
            provision_type="schedule",
            rule_number=None,
            subrule_identifier=None,
            clause_number=None,
            title=schedule["title"],
            source_page=schedule["source_page"],
            source_page_end=schedule["source_page_end"],
            source_line_start=schedule["source_line_start"],
            source_line_end=schedule["source_line_end"],
            document_line_start=None,
            document_line_end=None,
            hierarchy_path=["schedule", schedule["schedule_number"]],
            sequence=sequence,
            amendment_metadata={},
            effective_from=None,
            effective_to=None,
            is_active=None,
            applicability_metadata={},
        )
        schedule["source_provision_id"] = provision["id"]
        schedule["referenced_provision_id"] = rule_ids.get(schedule.get("referenced_rule_number"))
        result.append(provision)
    return result


def build_phase2_corpus(
    pdf_path: Path | str,
    phase1_document: LegalDocument | None = None,
) -> Phase2Corpus:
    source_path = Path(pdf_path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Source PDF not found: {source_path}")
    reader = PdfReader(str(source_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    source_lines, _ = _line_index(pages)
    layout = _layout_lines(source_path)
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    document_source = f"sha256:{source_hash}"
    document_id = _stable_id(_source_identifier(source_hash, "document", source_path.name, source_hash))
    full_text = "\n".join(pages)
    publication_match = re.search(r"New\s+Delhi,\s*the\s+([^\n]+)", full_text, re.I)
    effective_match = re.search(r"1st\s+day\s+of\s+([A-Za-z]+),\s*(\d{4})", full_text, re.I)
    publication_date = _date_from_explicit_text(publication_match.group(1)) if publication_match else None
    effective_date = None
    if effective_match:
        month = MONTHS.get(effective_match.group(1).lower())
        if month:
            effective_date = date(int(effective_match.group(2)), month, 1).isoformat()
    phase1_document = phase1_document or parse_document(source_path)
    if phase1_document.source_path.resolve() != source_path:
        raise ValueError("Phase 1 corpus source path does not match the supplied authoritative PDF")
    document_id = _stable_id(_source_identifier(source_hash, "document", source_path.name, source_hash))
    provisions = _rule_and_child_records(source_hash, document_id, source_lines)
    rules = [provision for provision in provisions if provision["provision_type"] == "rule"]
    schedules, entries, schedule_tables, unresolved = _schedule_records(
        source_hash, document_id, layout, rules
    )
    provisions.extend(_schedule_provision_records(source_hash, document_id, schedules, rules))
    tables = schedule_tables + _provision_tables(
        source_hash, document_id, layout, provisions, schedules
    )
    unresolved.extend(
        {
            "source_identifier": table["source_identifier"],
            "structure_type": "table_cells",
            "reason": "The table is preserved verbatim; cell headers and values are not normalized where extraction is ambiguous.",
        }
        for table in tables
        if table["structure_status"] == "raw_preserved"
    )
    for entry in entries:
        start = (entry["source_page"], entry["source_line_start"])
        containing_table = next(
            (
                table
                for table in tables
                if table["schedule_id"] == entry["schedule_id"]
                and (table["source_page"], table["source_line_start"]) <= start
                and (table["source_page_end"], table["source_line_end"]) >= start
            ),
            None,
        )
        if containing_table:
            entry["table_id"] = containing_table["id"]
    amendments = _amendment_records(
        source_hash, document_id, source_lines, provisions, schedules
    )
    requirements = _requirement_records(source_hash, provisions, schedules, entries)
    warnings: list[dict[str, Any]] = []
    for provision in provisions:
        if "\u00ad" in provision["raw_content"]:
            warnings.append({"source_identifier": provision["source_identifier"], "warning": "Soft hyphen normalized in normalized_content."})
    phase1_by_number = {
        _normalize_rule_number(str(rule.rule_number)): rule
        for rule in phase1_document.rules
        if rule.rule_number
    }
    mismatched_phase1_rules = [
        rule["rule_number"]
        for rule in rules
        if rule["rule_number"] not in phase1_by_number
        or normalize_legal_text(phase1_by_number[rule["rule_number"]].title)
        != normalize_legal_text(rule["title"])
    ]
    if mismatched_phase1_rules:
        unresolved.append({
            "structure_type": "phase1_rule_adapter",
            "reason": "Phase 1 title selection differs from sequential authoritative source headings for rules: "
            + ", ".join(mismatched_phase1_rules),
        })
    document = {
        "id": document_id,
        "source_identifier": document_source,
        "title": "The Legal Metrology (Packaged Commodities) Rules, 2011",
        "document_version": "2011",
        "source_type": "pdf_compilation",
        "source_file": source_path.name,
        "source_hash": source_hash,
        "jurisdiction": "IN",
        "publication_date": publication_date,
        "effective_from": effective_date,
        "metadata": {
            "pdf_pages": len(pages),
            "pdf_title": str(reader.metadata.title) if reader.metadata and reader.metadata.title else None,
            "extraction": "pypdf text plus layout mode for explicit schedule/table structure",
            "phase1_parser_rules": len(phase1_document.rules),
            "phase1_title_mismatches": mismatched_phase1_rules,
        },
    }
    return Phase2Corpus(
        document=document,
        provisions=provisions,
        schedules=schedules,
        schedule_entries=entries,
        tables=tables,
        amendments=amendments,
        requirements=requirements,
        unresolved_structures=unresolved,
        normalization_warnings=warnings,
    )


def corpus_coverage(corpus: Phase2Corpus) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for provision in corpus.provisions:
        key = provision["provision_type"]
        counts[key] = counts.get(key, 0) + 1
    provision_ids = {provision["id"] for provision in corpus.provisions}
    duplicate_identifiers = _duplicate_count(
        row["source_identifier"]
        for group in (
            [corpus.document], corpus.provisions, corpus.schedules, corpus.schedule_entries,
            corpus.tables, corpus.amendments, corpus.requirements,
        )
        for row in group
    )
    document_ids = {corpus.document["id"]}
    orphan_provisions = sum(
        provision["document_id"] not in document_ids
        or (provision["parent_id"] is not None and provision["parent_id"] not in provision_ids)
        for provision in corpus.provisions
    )
    schedule_entry_ids = {entry["id"] for entry in corpus.schedule_entries}
    orphan_requirements = sum(
        requirement["provision_id"] not in provision_ids
        or (
            requirement.get("schedule_entry_id") is not None
            and requirement["schedule_entry_id"] not in schedule_entry_ids
        )
        for requirement in corpus.requirements
    )
    requirements_with_provenance = sum(
        bool(requirement["source_quote"] and requirement["source_reference"].get("source_page"))
        for requirement in corpus.requirements
    )
    return {
        "documents": 1,
        "provisions_by_type": counts,
        "rules": counts.get("rule", 0),
        "sub_rules": counts.get("sub_rule", 0),
        "clauses": counts.get("clause", 0),
        "provisos": counts.get("proviso", 0),
        "explanations": counts.get("explanation", 0),
        "schedules": len(corpus.schedules),
        "schedule_entries": len(corpus.schedule_entries),
        "tables": len(corpus.tables),
        "amendments": len(corpus.amendments),
        "requirements": len(corpus.requirements),
        "requirements_with_provenance": requirements_with_provenance,
        "requirements_without_provenance": len(corpus.requirements) - requirements_with_provenance,
        "orphan_provisions": orphan_provisions,
        "orphan_requirements": orphan_requirements,
        "unresolved_structures": len(corpus.unresolved_structures),
        "duplicate_source_identifiers": duplicate_identifiers,
        "normalization_warnings": len(corpus.normalization_warnings),
    }


def _duplicate_count(values: Iterable[str]) -> int:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return len(duplicates)


def _database_bigint(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SchemaAdapterError(f"Supabase did not return a valid bigint for {field_name}")
    return value


def ordered_load_groups(corpus: Phase2Corpus) -> list[tuple[str, list[dict[str, Any]]]]:
    return [
        ("legal_documents", [corpus.document]),
        ("legal_provisions", sorted(corpus.provisions, key=lambda row: (len(row["hierarchy_path"]), row["sequence"]))),
        ("legal_schedules", corpus.schedules),
        ("legal_tables", corpus.tables),
        ("legal_schedule_entries", corpus.schedule_entries),
        ("legal_amendments", corpus.amendments),
        ("legal_requirements", corpus.requirements),
    ]


def load_groups_to_supabase(url: str, key: str, corpus: Phase2Corpus, batch_size: int = 100) -> dict[str, int]:
    import requests

    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    preview_serialized_groups(corpus)
    base_headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    base_url = url.rstrip("/")

    def request_rows(method: str, table: str, **kwargs: Any) -> list[dict[str, Any]]:
        response = getattr(requests, method)(
            f"{base_url}/rest/v1/{table}",
            headers={**base_headers, **kwargs.pop("headers", {})},
            timeout=60,
            **kwargs,
        )
        if not response.ok:
            raise RuntimeError(
                f"Supabase {method.upper()} {table} failed ({response.status_code}): {response.text}"
            )
        if response.status_code == 204 or not response.content:
            return []
        body = response.json()
        if isinstance(body, dict):
            return [body]
        if not isinstance(body, list):
            raise RuntimeError(f"Supabase {method.upper()} {table} returned an unexpected response body")
        return body

    def required_bigint(row: Mapping[str, Any], field: str) -> int:
        try:
            return _database_bigint(row.get(field), field)
        except SchemaAdapterError as exc:
            raise RuntimeError(str(exc)) from exc

    def fetch_document_id() -> int:
        payload = serialize_phase1_document(corpus.document)
        matching = request_rows(
            "get",
            "legal_documents",
            params={
                "select": "id,source,document_title,document_version,source_pdf_path,source_hash",
                "source_hash": f"eq.{corpus.document['source_hash']}",
                "limit": "2",
            },
        )
        if len(matching) > 1:
            raise RuntimeError("Multiple legal_documents rows share this source_hash; refusing ambiguous bigint mapping")
        if matching:
            existing = matching[0]
            document_id = required_bigint(existing, "id")
            conflicts = [name for name, value in payload.items() if existing.get(name) != value]
            if conflicts:
                raise RuntimeError(
                    "Existing legal_documents row for source_hash has conflicting fields: "
                    + ", ".join(conflicts)
                )
            return document_id
        created = request_rows(
            "post",
            "legal_documents",
            params={"select": "id,source_hash"},
            headers={"Prefer": "return=representation"},
            json=payload,
        )
        if len(created) != 1 or created[0].get("source_hash") != corpus.document["source_hash"]:
            raise RuntimeError("Could not resolve the database-generated legal_documents bigint ID")
        return required_bigint(created[0], "id")

    def fetch_existing_provisions(document_id: int) -> dict[str, int]:
        matches: dict[str, int] = {}
        offset = 0
        page_size = 1000
        while True:
            rows = request_rows(
                "get",
                "legal_provisions",
                params={
                    "select": "id,source_location",
                    "document_id": f"eq.{document_id}",
                    "order": "id.asc",
                },
                headers={"Range-Unit": "items", "Range": f"{offset}-{offset + page_size - 1}"},
            )
            for row in rows:
                locator = row.get("source_location")
                if not locator:
                    continue
                if locator in matches:
                    raise RuntimeError(
                        "Duplicate legal_provisions.source_location prevents deterministic bigint mapping: "
                        + str(locator)
                    )
                matches[locator] = required_bigint(row, "id")
            if len(rows) < page_size:
                break
            offset += page_size
        return matches

    document_id = fetch_document_id()
    existing_locations = fetch_existing_provisions(document_id)
    provision_ids: dict[str, int] = {}
    source_file = corpus.document["source_file"]
    ordered_provisions = sorted(
        corpus.provisions,
        key=lambda row: (len(row["hierarchy_path"]), row["sequence"]),
    )
    for provision in ordered_provisions:
        location = provision_source_location(provision, source_file)
        existing_id = existing_locations.get(location)
        if existing_id is not None:
            provision_ids[provision["id"]] = existing_id

    provisions_by_depth: dict[int, list[dict[str, Any]]] = {}
    for provision in ordered_provisions:
        provisions_by_depth.setdefault(len(provision["hierarchy_path"]), []).append(provision)
    for depth in sorted(provisions_by_depth):
        pending: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for provision in provisions_by_depth[depth]:
            if provision["id"] in provision_ids:
                continue
            parent_canonical_id = provision.get("parent_id")
            if parent_canonical_id and parent_canonical_id not in provision_ids:
                raise SchemaAdapterError(
                    "Parent provision has no database bigint mapping: " + str(parent_canonical_id)
                )
            parent_id = provision_ids.get(parent_canonical_id) if parent_canonical_id else None
            payload = serialize_phase1_provision(provision, document_id, parent_id, source_file)
            pending.append((provision, payload))
        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            created = request_rows(
                "post",
                "legal_provisions",
                params={"select": "id,source_location"},
                headers={"Prefer": "return=representation"},
                json=[payload for _, payload in batch],
            )
            if len(created) != len(batch):
                raise RuntimeError(
                    f"Supabase returned {len(created)} legal_provisions IDs for {len(batch)} submitted rows"
                )
            submitted_locations = {payload["source_location"] for _, payload in batch}
            for result in created:
                location = result.get("source_location")
                if location not in submitted_locations:
                    raise RuntimeError("Supabase legal_provisions response omitted a submitted source_location")
                canonical = next(
                    record for record, _ in batch if _["source_location"] == location
                )
                provision_ids[canonical["id"]] = required_bigint(result, "id")

    counts: dict[str, int] = {
        "legal_documents": 1,
        "legal_provisions": len(corpus.provisions),
    }
    for table_name, rows in ordered_load_groups(corpus):
        if table_name in PHASE1_PAYLOAD_COLUMNS:
            continue
        counts[table_name] = len(rows)
        payloads = [
            serialize_phase2_record(
                table_name,
                row,
                document_id,
                provision_ids,
                source_file=source_file,
            )
            for row in rows
        ]
        for start in range(0, len(payloads), batch_size):
            request_rows(
                "post",
                table_name,
                params={"on_conflict": "source_identifier"},
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                json=payloads[start : start + batch_size],
            )
    return counts


def coverage_json(corpus: Phase2Corpus) -> str:
    return json.dumps(corpus_coverage(corpus), indent=2, ensure_ascii=False)