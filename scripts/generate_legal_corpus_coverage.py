from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts.legal_corpus_parser import generate_coverage_report, parse_document


DEFAULT_PDF_PATH = ROOT / "assets" / "Book_on_Legal_Metrology_Packaged_Commodities_Rules,2011_with_all_amendments_whatsnews.pdf"


def main() -> None:
    pdf_path = DEFAULT_PDF_PATH
    document = parse_document(pdf_path)
    report = generate_coverage_report(document)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
