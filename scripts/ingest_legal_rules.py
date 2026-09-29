"""Ingest inspection-relevant provisions from the supplied Legal Metrology PDF.

Usage:
  python scripts/ingest_legal_rules.py --dry-run
  python scripts/ingest_legal_rules.py --url https://PROJECT.supabase.co --key ANON_KEY

The script never invents rule text: every content value comes directly from PDF
text extraction. Insertion is opt-in; --dry-run is the default.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfReader

EXPECTED_COLUMNS = {
    "source",
    "rule_number",
    "title",
    "content",
    "category",
    "created_at",
}
RELEVANT_TERMS = (
    "declaration",
    "manufacturer",
    "packer",
    "importer",
    "net quantity",
    "maximum retail price",
    "mrp",
    "date of manufacture",
    "date of packing",
    "best before",
    "consumer care",
    "customer care",
    "unit sale price",
    "retail sale",
    "package",
    "commodities",
)
CATEGORY_TERMS = {
    "declarations": ("declaration", "package shall bear", "label"),
    "manufacturer_packer_importer": ("manufacturer", "packer", "importer"),
    "quantity_and_pricing": ("net quantity", "maximum retail price", "mrp", "unit sale price"),
    "dates": ("date of manufacture", "date of packing", "best before", "expiry"),
    "consumer_information": ("consumer care", "customer care", "complaint"),
}
RULE_START = re.compile(
    r"(?m)^\s*([1-9]\d?)\.\s+([A-Z][^\n]*?)\s*$"
)


@dataclass(frozen=True)
class RuleChunk:
    rule_number: str
    title: str
    content: str
    category: str

    def row(self, source: str) -> dict[str, str]:
        return {
            "source": source,
            "rule_number": self.rule_number,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


def extract_pdf_text(pdf_path: Path) -> tuple[str, list[int]]:
    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    failed_pages: list[int] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if not text.strip():
            failed_pages.append(page_number)
        pages.append(text)
    return "\n\n".join(pages), failed_pages


def normalize(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def category_for(text: str) -> str:
    lowered = text.lower()
    scores = {
        category: sum(lowered.count(term) for term in terms)
        for category, terms in CATEGORY_TERMS.items()
    }
    category, score = max(scores.items(), key=lambda item: item[1])
    return category if score else "packaged_commodities"


def parse_rule_chunks(text: str) -> list[RuleChunk]:
    text = normalize(text)
    body_start = text.find("NOTIFICATION")
    if body_start >= 0:
        text = text[body_start:]
    matches = list(RULE_START.finditer(text))
    chunks: list[RuleChunk] = []
    for index, match in enumerate(matches):
        rule_number = match.group(1)
        title = normalize(match.group(2)).rstrip(".:;")
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = normalize(text[start:end])
        if re.search(r"\s-\d+$", title) or len(content.splitlines()) < 3:
            continue
        lowered = content.lower()
        if not any(term in lowered for term in RELEVANT_TERMS):
            continue
        if len(content) < 80:
            continue
        chunks.append(
            RuleChunk(
                rule_number=rule_number,
                title=title,
                content=content,
                category=category_for(content),
            )
        )
    return chunks


def supabase_request(url: str, key: str, method: str = "GET", **kwargs: Any) -> requests.Response:
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    headers.update(kwargs.pop("headers", {}))
    response = requests.request(
        method,
        f"{url.rstrip('/')}/rest/v1/legal_rules",
        headers=headers,
        timeout=60,
        **kwargs,
    )
    if not response.ok:
        raise RuntimeError(f"Supabase legal_rules request failed ({response.status_code}): {response.text}")
    return response


def validate_schema(url: str, key: str) -> None:
    response = supabase_request(
        url,
        key,
        params={"select": ",".join(sorted(EXPECTED_COLUMNS)), "limit": "1"},
    )
    if response.status_code != 200:
        raise RuntimeError("legal_rules schema validation did not return HTTP 200")


def insert_chunks(url: str, key: str, rows: list[dict[str, str]], batch_size: int = 100) -> int:
    inserted = 0
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        response = supabase_request(
            url,
            key,
            method="POST",
            params={"select": "source,rule_number"},
            headers={"Prefer": "return=representation"},
            json=batch,
        )
        body = response.json()
        inserted += len(body) if isinstance(body, list) else len(batch)
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path("assets/Book_on_Legal_Metrology_Packaged_Commodities_Rules,2011_with_all_amendments_whatsnews.pdf"),
    )
    parser.add_argument("--url", default=os.getenv("SUPABASE_URL"))
    parser.add_argument("--key", default=os.getenv("SUPABASE_KEY"))
    parser.add_argument("--insert", action="store_true", help="Insert rows; otherwise print a dry-run report.")
    parser.add_argument("--dry-run", action="store_true", help="Print the extraction report without inserting rows.")
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"Source PDF not found: {args.pdf}", file=sys.stderr)
        return 2

    text, failed_pages = extract_pdf_text(args.pdf)
    chunks = parse_rule_chunks(text)
    source = args.pdf.name
    rows = [chunk.row(source) for chunk in chunks]

    print(json.dumps({
        "source": source,
        "extracted_characters": len(text),
        "rule_chunks": len(rows),
        "unextractable_pages": failed_pages,
        "preview": [
            {"rule_number": row["rule_number"], "title": row["title"], "category": row["category"]}
            for row in rows[:10]
        ],
    }, indent=2))

    if not args.insert:
        print("Dry run only: no legal_rules rows inserted.")
        return 0
    if not args.url or not args.key:
        print("--url/--key or SUPABASE_URL/SUPABASE_KEY are required with --insert.", file=sys.stderr)
        return 2

    validate_schema(args.url, args.key)
    inserted = insert_chunks(args.url, args.key, rows)
    print(f"Successfully inserted {inserted} legal rule chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
