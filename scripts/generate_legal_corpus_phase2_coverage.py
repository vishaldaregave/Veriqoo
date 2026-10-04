from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.legal_corpus_phase2 import build_phase2_corpus, corpus_coverage


DEFAULT_PDF = ROOT / "assets" / "Book_on_Legal_Metrology_Packaged_Commodities_Rules,2011_with_all_amendments_whatsnews.pdf"


def main() -> int:
    parser = argparse.ArgumentParser(description="Report source-grounded Phase 2 legal corpus coverage.")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    args = parser.parse_args()
    try:
        corpus = build_phase2_corpus(args.pdf)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    report = corpus_coverage(corpus)
    report["source_file"] = corpus.document["source_file"]
    report["source_hash"] = corpus.document["source_hash"]
    report["phase1_title_mismatches"] = corpus.document["metadata"]["phase1_title_mismatches"]
    report["unresolved_structure_details"] = corpus.unresolved_structures
    report["normalization_warning_details"] = corpus.normalization_warnings
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())