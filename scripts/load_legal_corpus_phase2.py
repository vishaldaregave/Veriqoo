from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.legal_corpus_db_adapter import CANONICAL_FIELDS_NOT_PERSISTED, preview_serialized_groups
from scripts.legal_corpus_phase2 import build_phase2_corpus, corpus_coverage, load_groups_to_supabase


DEFAULT_PDF = ROOT / "assets" / "Book_on_Legal_Metrology_Packaged_Commodities_Rules,2011_with_all_amendments_whatsnews.pdf"


def main() -> int:
    parser = argparse.ArgumentParser(description="Load the source-grounded Phase 1 corpus into the Phase 2 Supabase schema.")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--load", action="store_true", help="Upsert corpus rows. Without this flag, the command is a dry run.")
    parser.add_argument("--url", default=os.getenv("SUPABASE_URL"))
    parser.add_argument("--key", default=os.getenv("SUPABASE_KEY"))
    args = parser.parse_args()

    try:
        corpus = build_phase2_corpus(args.pdf)
        report = corpus_coverage(corpus)
        serialized_groups = preview_serialized_groups(corpus)
        if not args.load:
            report["mode"] = "dry_run"
            report["planned_rows"] = {table: len(rows) for table, rows in serialized_groups}
            report["outgoing_columns_by_table"] = {
                table: sorted(rows[0]) if rows else [] for table, rows in serialized_groups
            }
            report["provenance_coverage"] = {
                "requirements_total": report["requirements"],
                "requirements_with_provenance": report["requirements_with_provenance"],
                "requirements_without_provenance": report["requirements_without_provenance"],
                "phase1_provisions_have_raw_and_source_location": True,
            }
            report["canonical_fields_intentionally_not_persisted"] = CANONICAL_FIELDS_NOT_PERSISTED
            report["phase1_identity_mapping"] = {
                "legal_documents": "lookup/insert by source_hash; omit UUID canonical id and use returned bigint id",
                "legal_provisions": "lookup/insert by deterministic source_location; map canonical UUIDs to returned bigint ids",
            }
            report["unresolved_structures"] = corpus.unresolved_structures
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0
        if not args.url or not args.key:
            print("--url/--key or SUPABASE_URL/SUPABASE_KEY are required with --load.", file=sys.stderr)
            return 2
        report["mode"] = "upsert"
        report["loaded_rows"] = load_groups_to_supabase(args.url, args.key, corpus)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())