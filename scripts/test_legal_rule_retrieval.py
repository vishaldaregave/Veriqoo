"""Test pgvector retrieval against public.match_legal_rules.

Requires environment variables:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY (preferred) or SUPABASE_KEY
  GEMINI_API_KEY

Example:
  python scripts/test_legal_rule_retrieval.py "What declarations must show the MRP?"
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import requests

MODEL = "gemini-embedding-001"
VECTOR_DIMENSION = 3072
RPC = "match_legal_rules"


def headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def generate_query_embedding(api_key: str, query: str) -> list[float]:
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:embedContent",
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json={
            "content": {"parts": [{"text": query}]},
            "taskType": "RETRIEVAL_QUERY",
        },
        timeout=120,
    )
    if not response.ok:
        raise RuntimeError(
            f"Gemini query embedding failed ({response.status_code}): {response.text}"
        )
    values = response.json().get("embedding", {}).get("values")
    if not isinstance(values, list) or len(values) != VECTOR_DIMENSION:
        actual = len(values) if isinstance(values, list) else "missing"
        raise RuntimeError(
            f"Expected {VECTOR_DIMENSION} dimensions from {MODEL}; received {actual}"
        )
    return [float(value) for value in values]


def retrieve(
    url: str,
    key: str,
    embedding: list[float],
    match_count: int,
) -> list[dict[str, Any]]:
    response = requests.post(
        f"{url.rstrip('/')}/rest/v1/rpc/{RPC}",
        headers=headers(key),
        json={"query_embedding": embedding, "match_count": match_count},
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(
            f"Supabase RPC {RPC} failed ({response.status_code}): {response.text}"
        )
    results = response.json()
    if not isinstance(results, list):
        raise RuntimeError("Supabase RPC returned an unexpected response")
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Natural-language legal compliance query")
    parser.add_argument("--count", type=int, default=5, help="Number of rules to return")
    args = parser.parse_args()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not url or not key or not gemini_key:
        print(
            "Set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY), "
            "and GEMINI_API_KEY.",
            file=sys.stderr,
        )
        return 2
    if args.count < 1:
        parser.error("--count must be at least 1")

    embedding = generate_query_embedding(gemini_key, args.query)
    results = retrieve(url, key, embedding, args.count)
    print(f"Query: {args.query}")
    print(f"Model: {MODEL}; task type: RETRIEVAL_QUERY")
    print(f"Matches: {len(results)}")
    for index, result in enumerate(results, start=1):
        print(
            f"{index}. Rule {result.get('rule_number', 'unknown')} | "
            f"{result.get('title', 'Untitled')} | "
            f"category={result.get('category', 'uncategorized')} | "
            f"similarity={result.get('similarity', 'unknown')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
