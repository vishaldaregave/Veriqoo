"""Generate and store embeddings for public.legal_rules rows.

Requires environment variables:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY (preferred) or SUPABASE_KEY
  GEMINI_API_KEY

The script updates existing rows only. It never inserts or duplicates legal rules.
Run without --write to inspect the pending rows and request shape.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import requests

MODEL = "gemini-embedding-001"
VECTOR_DIMENSION = 3072
TABLE = "legal_rules"


def supabase_headers(key: str, prefer: str | None = None) -> dict[str, str]:
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def load_pending(url: str, key: str) -> list[dict[str, Any]]:
    endpoint = f"{url.rstrip('/')}/rest/v1/{TABLE}"
    params = [
        ("select", "source,rule_number,title,content,category,embedding"),
        # PostgREST's IS NULL predicate is expressed as column=is.null.
        ("embedding", "is.null"),
        ("order", "rule_number.asc"),
    ]
    request = requests.Request(
        "GET",
        endpoint,
        headers=supabase_headers(key, "count=exact"),
        params=params,
    ).prepare()
    print(f"Supabase legal_rules query: {request.url}")
    response = requests.Session().send(
        request,
        timeout=60,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise RuntimeError("Supabase returned an unexpected legal_rules response")
    content_range = response.headers.get("Content-Range", "unknown")
    print(f"Supabase legal_rules Content-Range: {content_range}")
    print(f"Fetched {len(rows)} legal_rules rows where embedding IS NULL.")
    return rows


def embedding_input(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Rule number: {row.get('rule_number') or 'not specified'}",
            f"Title: {row.get('title') or 'not specified'}",
            f"Category: {row.get('category') or 'not specified'}",
            "Content:",
            str(row.get("content") or ""),
        ]
    )


def generate_embedding(api_key: str, text: str) -> list[float]:
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:embedContent",
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json={
            "content": {"parts": [{"text": text}]},
            "taskType": "RETRIEVAL_DOCUMENT",
        },
        timeout=120,
    )
    if not response.ok:
        raise RuntimeError(f"Gemini embedding request failed ({response.status_code}): {response.text}")
    body = response.json()
    values = body.get("embedding", {}).get("values")
    if not isinstance(values, list):
        raise RuntimeError(f"Gemini response did not contain embedding.values: {body}")
    if len(values) != VECTOR_DIMENSION:
        raise RuntimeError(
            f"Expected {VECTOR_DIMENSION} dimensions from {MODEL}, received {len(values)}"
        )
    return [float(value) for value in values]


def update_embedding(url: str, key: str, row: dict[str, Any], values: list[float]) -> int:
    # Match the existing legal-rule identity; this performs no insert.
    params = {
        "source": f"eq.{row['source']}",
        "rule_number": f"eq.{row['rule_number']}",
        "title": f"eq.{row['title']}",
    }
    response = requests.patch(
        f"{url.rstrip('/')}/rest/v1/{TABLE}",
        headers=supabase_headers(key, "return=representation"),
        params=params,
        json={"embedding": values},
        timeout=120,
    )
    if not response.ok:
        raise RuntimeError(f"Supabase embedding update failed ({response.status_code}): {response.text}")
    body = response.json()
    return len(body) if isinstance(body, list) else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Generate and persist embeddings.")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum pending rows to process.")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between Gemini requests in seconds.")
    args = parser.parse_args()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not url or not key or not gemini_key:
        print("Set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY), and GEMINI_API_KEY.", file=sys.stderr)
        return 2

    pending_rows = load_pending(url, key)
    rows = pending_rows[: args.limit]
    print(f"Found {len(pending_rows)} legal_rules rows with missing embeddings.")
    if len(rows) < len(pending_rows):
        print(f"Processing first {len(rows)} rows because --limit={args.limit}.")
    if not args.write:
        print(f"Dry run: model={MODEL}, verified_dimension={VECTOR_DIMENSION}; no rows changed.")
        return 0

    embedded = 0
    updated = 0
    for row in rows:
        values = generate_embedding(gemini_key, embedding_input(row))
        embedded += 1
        updated += update_embedding(url, key, row, values)
        print(f"Embedded rule {row['rule_number']} ({updated} row updates so far).")
        if args.delay:
            time.sleep(args.delay)

    print(f"Successfully embedded {embedded} legal-rule rows; Supabase returned {updated} updates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
