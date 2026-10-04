"""Embedding coverage verification mechanism (Phase 4C).

Compares expected authoritative legal corpus counts against actual rows
in legal_corpus_embeddings across the five canonical entities:
- Requirements: 437
- Provisions: 341
- Schedule Entries: 96
- Tables: 10
- Amendments: 76
Total: 960
"""

from __future__ import annotations

from backend.app.services.legal_rag.retrieval.models import CoverageReport
from backend.app.services.legal_rag.retrieval.repository import LegalCorpusRepository

EXPECTED_LEGAL_ENTITY_COUNTS: dict[str, int] = {
    "requirement": 437,
    "provision": 341,
    "schedule_entry": 96,
    "table": 10,
    "amendment": 76,
}


class EmbeddingCoverageChecker:
    """Verifies embedding population against authoritative legal corpus baseline."""

    def __init__(self, repository: LegalCorpusRepository) -> None:
        self.repository = repository

    def check_coverage(self) -> CoverageReport:
        """Calculate embedding coverage metrics for all 5 canonical legal entities."""
        expected = dict(EXPECTED_LEGAL_ENTITY_COUNTS)
        actual: dict[str, int] = {}
        missing: dict[str, int] = {}
        pcts: dict[str, float] = {}

        total_expected = sum(expected.values())
        total_actual = 0

        for etype, exp_count in expected.items():
            act_count = self.repository.count_embeddings(etype)
            actual[etype] = act_count
            missing[etype] = max(exp_count - act_count, 0)
            pcts[etype] = round((act_count / exp_count * 100), 2) if exp_count > 0 else 0.0
            total_actual += act_count

        is_fully = total_actual >= total_expected and all(m == 0 for m in missing.values())

        return CoverageReport(
            expected_counts=expected,
            actual_counts=actual,
            missing_counts=missing,
            coverage_percentages=pcts,
            total_expected=total_expected,
            total_actual=total_actual,
            is_fully_populated=is_fully,
        )

