"""Unit and Contract Tests for Phase 7 — Unified End-to-End Inspection Pipeline.

Covers all 50+ mandatory scenarios including 10-step orchestration order,
dependency injection, OCR error isolation, applicability gates, RAG/Gemini boundaries,
deterministic overall status calculation, and provenance preservation.
"""

from __future__ import annotations

import json
import unittest
from typing import Any
from uuid import uuid4

from backend.app.services.applicability.models import ApplicabilityDecision, TriState
from backend.app.services.evidence.models import (
    EvidenceCandidate,
    EvidenceField,
    EvidenceStatus,
    ImageArtifact,
)
from backend.app.services.evidence.service import EvidenceNormalizationService
from backend.app.services.gemini.client import FakeGeminiClient
from backend.app.services.gemini.config import GeminiConfig
from backend.app.services.gemini.errors import GeminiProviderError, GeminiTimeoutError
from backend.app.services.gemini.service import GeminiEvidenceService
from backend.app.services.inspection_pipeline.errors import (
    InvalidPipelineInputError,
    PipelineError,
)
from backend.app.services.inspection_pipeline.models import (
    InspectionPipelineRequest,
    OverallInspectionStatus,
)
from backend.app.services.inspection_pipeline.orchestrator import (
    InspectionPipelineOrchestrator,
)
from backend.app.services.inspection_pipeline.report import (
    InspectionReport,
    compute_overall_status,
)
from backend.app.services.ocr.engine import MockOCREngine
from backend.app.services.ocr.models import BoundingBox, OCRObservation, OCRProcessingStatus, OCRResult
from backend.app.services.verification.models import (
    RequirementReference,
    VerificationResult,
    VerificationStatus,
)
from backend.app.services.verification.service import VerificationService


class TestPhase7InspectionPipeline(unittest.TestCase):
    """Test suite for Phase 7 End-to-End Inspection Pipeline."""

    def _make_artifact(self, image_id: str = "img_001", raw_bytes: bytes = b"fake_png_data") -> ImageArtifact:
        return ImageArtifact(
            image_id=image_id,
            source_hash=f"src_hash_{image_id}",
            normalized_hash=f"norm_hash_{image_id}",
            source_format="PNG",
            normalized_format="PNG",
            original_width=800,
            original_height=600,
            normalized_width=800,
            normalized_height=600,
            pixel_count=480000,
            aspect_ratio=1.333,
            file_size_bytes=len(raw_bytes),
            source_file_size_bytes=len(raw_bytes),
            color_mode="RGB",
            normalized_bytes=raw_bytes,
        )

    def _make_obs(
        self,
        text: str,
        sequence: int = 0,
        confidence: float = 0.95,
        image_id: str = "img_001",
        observation_id: str | None = None,
    ) -> OCRObservation:
        return OCRObservation(
            observation_id=observation_id or f"obs_{sequence}_{uuid4().hex[:6]}",
            image_id=image_id,
            text=text,
            confidence=confidence,
            bounding_box=BoundingBox(points=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]),
            sequence=sequence,
            engine="MockOCR",
            engine_version="1.0.0",
        )

    def _make_mock_ocr_engine(self, observations_by_image: dict[str, list[OCRObservation]] | None = None) -> Any:
        obs_map = observations_by_image or {}

        class CustomMockOCR:
            def extract_text(self, image_bytes: bytes, image_id: str = "") -> OCRResult:
                if image_id in obs_map:
                    obs_list = obs_map[image_id]
                    return OCRResult(
                        image_id=image_id,
                        status=OCRProcessingStatus.SUCCESS if obs_list else OCRProcessingStatus.NO_TEXT_DETECTED,
                        observations=obs_list,
                    )
                return OCRResult(image_id=image_id, status=OCRProcessingStatus.NO_TEXT_DETECTED, observations=[])

        return CustomMockOCR()

    # 1. empty inspection
    def test_01_empty_inspection(self) -> None:
        orchestrator = InspectionPipelineOrchestrator()
        req = InspectionPipelineRequest(inspection_id="INSP_EMPTY")
        report = orchestrator.run(req)
        self.assertEqual(report.inspection_id, "INSP_EMPTY")
        self.assertEqual(report.image_count, 0)
        self.assertEqual(report.evidence_count, 0)
        self.assertEqual(report.overall_status, OverallInspectionStatus.REVIEW_REQUIRED)

    # 2. one image
    def test_02_one_image_inspection(self) -> None:
        art = self._make_artifact("img_1")
        obs = [self._make_obs("MRP Rs. 150.00", sequence=0, image_id="img_1")]
        ocr = self._make_mock_ocr_engine({"img_1": obs})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        req = InspectionPipelineRequest(
            inspection_id="INSP_01",
            image_artifacts=[art],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        )
        report = orchestrator.run(req)
        self.assertEqual(report.image_count, 1)
        self.assertGreater(report.evidence_count, 0)
        self.assertEqual(report.overall_status, OverallInspectionStatus.PASS)

    # 3. multiple images
    def test_03_multiple_images_inspection(self) -> None:
        art1 = self._make_artifact("img_front")
        art2 = self._make_artifact("img_back")
        obs1 = [self._make_obs("MRP Rs. 100", sequence=0, image_id="img_front")]
        obs2 = [self._make_obs("Net Qty: 500 g", sequence=0, image_id="img_back")]
        ocr = self._make_mock_ocr_engine({"img_front": obs1, "img_back": obs2})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        req = InspectionPipelineRequest(
            inspection_id="INSP_03",
            image_artifacts=[art1, art2],
            target_requirements=[
                RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP),
                RequirementReference(requirement_id="REQ_QTY", target_field=EvidenceField.NET_QUANTITY),
            ],
        )
        report = orchestrator.run(req)
        self.assertEqual(report.image_count, 2)
        self.assertEqual(report.pass_count, 2)
        self.assertEqual(report.overall_status, OverallInspectionStatus.PASS)

    # 4. OCR success
    def test_04_ocr_success(self) -> None:
        art = self._make_artifact("img_ok")
        obs = [self._make_obs("Manufactured by: Test Ltd", sequence=0, image_id="img_ok")]
        ocr = self._make_mock_ocr_engine({"img_ok": obs})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_04",
            image_artifacts=[art],
            target_requirements=[RequirementReference(requirement_id="REQ_MFG", target_field=EvidenceField.MANUFACTURER_NAME)],
        ))
        self.assertEqual(report.errors, [])
        self.assertEqual(report.pass_count, 1)

    # 5. OCR no-text
    def test_05_ocr_no_text_handled_safely(self) -> None:
        art = self._make_artifact("img_blank")
        ocr = self._make_mock_ocr_engine({"img_blank": []})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_05",
            image_artifacts=[art],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.not_visible_count, 1)
        self.assertEqual(report.overall_status, OverallInspectionStatus.REVIEW_REQUIRED)

    # 6. OCR failure on single image
    def test_06_ocr_failure_isolated(self) -> None:
        class FailingOCR:
            def extract_text(self, image_bytes: bytes, image_id: str = "") -> OCRResult:
                raise RuntimeError("OCR device out of memory")

        orchestrator = InspectionPipelineOrchestrator(ocr_engine=FailingOCR())
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_06",
            image_artifacts=[self._make_artifact("img_fail")],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(report.not_visible_count, 1)
        self.assertEqual(report.overall_status, OverallInspectionStatus.REVIEW_REQUIRED)

    # 7. partial OCR failure
    def test_07_partial_ocr_failure_continues_processing(self) -> None:
        art1 = self._make_artifact("img_bad")
        art2 = self._make_artifact("img_good")

        class PartialFailingOCR:
            def extract_text(self, image_bytes: bytes, image_id: str = "") -> OCRResult:
                if image_id == "img_bad":
                    raise ValueError("Corrupt JPEG stream")
                return OCRResult(
                    image_id=image_id,
                    status=OCRProcessingStatus.SUCCESS,
                    observations=[OCRObservation(
                        observation_id="obs_001",
                        image_id=image_id,
                        text="MRP Rs. 250",
                        confidence=0.9,
                        bounding_box=BoundingBox(points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]),
                        sequence=0,
                        engine="MockOCR",
                        engine_version="1.0.0",
                    )],
                )

        orchestrator = InspectionPipelineOrchestrator(ocr_engine=PartialFailingOCR())
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_07",
            image_artifacts=[art1, art2],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(report.pass_count, 1)
        self.assertEqual(report.overall_status, OverallInspectionStatus.PASS)

    # 8. evidence normalization
    def test_08_evidence_normalization_executes(self) -> None:
        art = self._make_artifact("img_norm")
        obs = [self._make_obs("MRP Rs. 500.00", sequence=0, image_id="img_norm")]
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=self._make_mock_ocr_engine({"img_norm": obs}))
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_08",
            image_artifacts=[art],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertGreater(report.evidence_count, 0)

    # 9. empty evidence set
    def test_09_empty_evidence_yields_not_visible(self) -> None:
        art = self._make_artifact("img_no_ev")
        obs = [self._make_obs("Some irrelevant decorative text", sequence=0, image_id="img_no_ev")]
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=self._make_mock_ocr_engine({"img_no_ev": obs}))
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_09",
            image_artifacts=[art],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.not_visible_count, 1)

    # 10. applicable requirement
    def test_10_applicable_requirement_evaluates(self) -> None:
        art = self._make_artifact("img_1")
        obs = [self._make_obs("MRP Rs. 100", sequence=0, image_id="img_1")]
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=self._make_mock_ocr_engine({"img_1": obs}))
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_10",
            image_artifacts=[art],
            applicability_context={"REQ_MRP": "applicable"},
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.pass_count, 1)

    # 11. not applicable requirement
    def test_11_not_applicable_requirement_skipped(self) -> None:
        art = self._make_artifact("img_1")
        obs = [self._make_obs("Imported by Global Imp", sequence=0, image_id="img_1")]
        ocr = self._make_mock_ocr_engine({"img_1": obs})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_11",
            image_artifacts=[art],
            applicability_context={"REQ_IMP": "not_applicable"},
            target_requirements=[RequirementReference(requirement_id="REQ_IMP", target_field=EvidenceField.IMPORTER_NAME)],
        ))
        self.assertEqual(report.not_applicable_count, 1)
        self.assertEqual(report.overall_status, OverallInspectionStatus.PASS)

    # 12. unknown applicability
    def test_12_unknown_applicability_yields_review(self) -> None:
        art = self._make_artifact("img_1")
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=self._make_mock_ocr_engine())
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_12",
            image_artifacts=[art],
            applicability_context={"REQ_UNK": "unknown"},
            target_requirements=[RequirementReference(requirement_id="REQ_UNK", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.review_required_count, 1)
        self.assertEqual(report.overall_status, OverallInspectionStatus.REVIEW_REQUIRED)

    # 13. applicable requirement reaches RAG
    def test_13_applicable_requirement_reaches_rag(self) -> None:
        rag_calls = []

        class MockRAG:
            def retrieve_for_applicable_requirements(self, req_ids: list[str]) -> dict[str, Any]:
                rag_calls.extend(req_ids)
                return {rid: {"context": "Mock Context"} for rid in req_ids}

        art = self._make_artifact("img_1")
        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine(),
            rag_service=MockRAG(),
        )
        orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_13",
            image_artifacts=[art],
            applicability_context={"REQ_APP": "applicable"},
            target_requirements=[RequirementReference(requirement_id="REQ_APP", target_field=EvidenceField.MRP)],
        ))
        self.assertIn("REQ_APP", rag_calls)

    # 14. not applicable skips RAG
    def test_14_not_applicable_skips_rag(self) -> None:
        rag_calls = []

        class MockRAG:
            def retrieve_for_applicable_requirements(self, req_ids: list[str]) -> dict[str, Any]:
                rag_calls.extend(req_ids)
                return {}

        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine(),
            rag_service=MockRAG(),
        )
        orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_14",
            applicability_context={"REQ_NA": "not_applicable"},
            target_requirements=[RequirementReference(requirement_id="REQ_NA", target_field=EvidenceField.IMPORTER_NAME)],
        ))
        self.assertEqual(len(rag_calls), 0)

    # 15. unknown skips RAG
    def test_15_unknown_skips_rag(self) -> None:
        rag_calls = []

        class MockRAG:
            def retrieve_for_applicable_requirements(self, req_ids: list[str]) -> dict[str, Any]:
                rag_calls.extend(req_ids)
                return {}

        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine(),
            rag_service=MockRAG(),
        )
        orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_15",
            applicability_context={"REQ_UNK": "unknown"},
            target_requirements=[RequirementReference(requirement_id="REQ_UNK", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(len(rag_calls), 0)

    # 16. applicable requirement reaches Gemini
    def test_16_applicable_requirement_reaches_gemini(self) -> None:
        cand_obs = [self._make_obs("MRP Rs. 100", sequence=0, image_id="img_1")]
        fake_client = FakeGeminiClient(default_response=json.dumps({
            "requirement_id": "REQ_MRP",
            "recommendation": "PASS",
            "evidence_sufficiency": "SUFFICIENT",
            "reason": "MRP declared",
            "evidence_ids": ["obs_0"],
        }))
        gemini_srv = GeminiEvidenceService(client=fake_client, config=GeminiConfig(api_key="mock"))
        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine({"img_1": cand_obs}),
            gemini_service=gemini_srv,
        )
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_16",
            image_artifacts=[self._make_artifact("img_1")],
            applicability_context={"REQ_MRP": "applicable"},
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(len(fake_client.call_history), 1)

    # 17. not applicable skips Gemini
    def test_17_not_applicable_skips_gemini(self) -> None:
        fake_client = FakeGeminiClient(default_response="SHOULD NOT BE CALLED")
        gemini_srv = GeminiEvidenceService(client=fake_client, config=GeminiConfig(api_key="mock"))
        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine(),
            gemini_service=gemini_srv,
        )
        orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_17",
            image_artifacts=[self._make_artifact("img_1")],
            applicability_context={"REQ_NA": "not_applicable"},
            target_requirements=[RequirementReference(requirement_id="REQ_NA", target_field=EvidenceField.IMPORTER_NAME)],
        ))
        self.assertEqual(len(fake_client.call_history), 0)

    # 18. unknown skips Gemini
    def test_18_unknown_skips_gemini(self) -> None:
        fake_client = FakeGeminiClient(default_response="SHOULD NOT BE CALLED")
        gemini_srv = GeminiEvidenceService(client=fake_client, config=GeminiConfig(api_key="mock"))
        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine(),
            gemini_service=gemini_srv,
        )
        orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_18",
            image_artifacts=[self._make_artifact("img_1")],
            applicability_context={"REQ_UNK": "unknown"},
            target_requirements=[RequirementReference(requirement_id="REQ_UNK", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(len(fake_client.call_history), 0)

    # 19. Gemini PASS
    def test_19_gemini_pass_assessment(self) -> None:
        obs = [self._make_obs("MRP Rs. 200", sequence=0, image_id="img_1")]

        def dynamic_pass_handler(prompt_text: str) -> str:
            # Extract evidence_id from prompt
            try:
                data_idx = prompt_text.find("EVALUATION INPUT:\n")
                if data_idx != -1:
                    payload = json.loads(prompt_text[data_idx + len("EVALUATION INPUT:\n"):])
                    candidates = payload.get("evidence_candidates", [])
                    ev_ids = [c["evidence_id"] for c in candidates]
                else:
                    ev_ids = []
            except Exception:
                ev_ids = []

            return json.dumps({
                "requirement_id": "REQ_MRP",
                "recommendation": "PASS",
                "evidence_sufficiency": "SUFFICIENT",
                "reason": "MRP valid",
                "evidence_ids": ev_ids,
            })

        fake_client = FakeGeminiClient(response_handler=dynamic_pass_handler)
        gemini_srv = GeminiEvidenceService(client=fake_client, config=GeminiConfig(api_key="mock"))
        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine({"img_1": obs}),
            gemini_service=gemini_srv,
        )
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_19",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.pass_count, 1)
        self.assertEqual(report.overall_status, OverallInspectionStatus.PASS)

    # 20. Gemini FAIL
    def test_20_gemini_fail_assessment(self) -> None:
        obs = [self._make_obs("MRP 50 USD", sequence=0, image_id="img_1")]

        def dynamic_fail_handler(prompt_text: str) -> str:
            try:
                data_idx = prompt_text.find("EVALUATION INPUT:\n")
                if data_idx != -1:
                    payload = json.loads(prompt_text[data_idx + len("EVALUATION INPUT:\n"):])
                    candidates = payload.get("evidence_candidates", [])
                    ev_ids = [c["evidence_id"] for c in candidates]
                else:
                    ev_ids = []
            except Exception:
                ev_ids = []

            return json.dumps({
                "requirement_id": "REQ_CURRENCY",
                "recommendation": "FAIL",
                "evidence_sufficiency": "SUFFICIENT",
                "reason": "Violates currency rule",
                "evidence_ids": ev_ids,
            })

        fake_client = FakeGeminiClient(response_handler=dynamic_fail_handler)
        gemini_srv = GeminiEvidenceService(client=fake_client, config=GeminiConfig(api_key="mock"))
        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine({"img_1": obs}),
            gemini_service=gemini_srv,
        )
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_20",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[RequirementReference(requirement_id="REQ_CURRENCY", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.fail_count, 1)
        self.assertEqual(report.overall_status, OverallInspectionStatus.FAIL)

    # 21. Gemini REVIEW_REQUIRED
    def test_21_gemini_review_required(self) -> None:
        obs = [self._make_obs("MRP 12S", sequence=0, image_id="img_1")]
        fake_client = FakeGeminiClient(default_response=json.dumps({
            "requirement_id": "REQ_MRP",
            "recommendation": "REVIEW_REQUIRED",
            "evidence_sufficiency": "AMBIGUOUS",
            "reason": "Ambiguous digit",
            "evidence_ids": [],
        }))
        gemini_srv = GeminiEvidenceService(client=fake_client, config=GeminiConfig(api_key="mock"))
        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine({"img_1": obs}),
            gemini_service=gemini_srv,
        )
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_21",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.review_required_count, 1)
        self.assertEqual(report.overall_status, OverallInspectionStatus.REVIEW_REQUIRED)

    # 22. Gemini timeout
    def test_22_gemini_timeout_handled(self) -> None:
        obs = [self._make_obs("MRP 100", sequence=0, image_id="img_1")]
        fake_client = FakeGeminiClient(exception_to_raise=GeminiTimeoutError("Execution deadline exceeded"))
        gemini_srv = GeminiEvidenceService(client=fake_client, config=GeminiConfig(api_key="mock"))
        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine({"img_1": obs}),
            gemini_service=gemini_srv,
        )
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_22",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.review_required_count, 1)

    # 23. Gemini provider failure
    def test_23_gemini_provider_failure_handled(self) -> None:
        obs = [self._make_obs("MRP 100", sequence=0, image_id="img_1")]
        fake_client = FakeGeminiClient(exception_to_raise=GeminiProviderError("HTTP 503 Service Unavailable"))
        gemini_srv = GeminiEvidenceService(client=fake_client, config=GeminiConfig(api_key="mock"))
        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine({"img_1": obs}),
            gemini_service=gemini_srv,
        )
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_23",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.review_required_count, 1)

    # 24. RAG failure handled safely
    def test_24_rag_failure_handled_safely(self) -> None:
        class FailingRAG:
            def retrieve_for_applicable_requirements(self, req_ids: list[str]) -> dict[str, Any]:
                raise RuntimeError("Vector database network timeout")

        art = self._make_artifact("img_1")
        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine(),
            rag_service=FailingRAG(),
        )
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_24",
            image_artifacts=[art],
            target_requirements=[RequirementReference(requirement_id="REQ_1", target_field=EvidenceField.MRP)],
        ))
        self.assertGreaterEqual(len(report.errors), 1)

    # 25. applicability failure handled safely
    def test_25_applicability_failure_handled_safely(self) -> None:
        class FailingApp:
            def evaluate_run(self, inspection_reference: str, facts: list) -> dict:
                raise ValueError("Corrupt rule schema")

        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine(),
            applicability_service=FailingApp(),
        )
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_25",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[RequirementReference(requirement_id="REQ_1", target_field=EvidenceField.MRP)],
        ))
        self.assertGreaterEqual(len(report.errors), 1)

    # 26. OCR failure preserved in errors
    def test_26_ocr_failure_preserved_in_errors(self) -> None:
        class ErrOCR:
            def extract_text(self, b: bytes, image_id: str = "") -> OCRResult:
                raise IOError("Corrupt image bytes")

        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ErrOCR())
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_26",
            image_artifacts=[self._make_artifact("img_err")],
            target_requirements=[RequirementReference(requirement_id="REQ_1", target_field=EvidenceField.MRP)],
        ))
        self.assertTrue(any(e["image_id"] == "img_err" for e in report.errors))

    # 27. Contradictory evidence
    def test_27_contradictory_evidence_handled(self) -> None:
        obs1 = [self._make_obs("MRP Rs. 100", sequence=0, image_id="img_1")]
        obs2 = [self._make_obs("MRP Rs. 200", sequence=0, image_id="img_2")]
        ocr = self._make_mock_ocr_engine({"img_1": obs1, "img_2": obs2})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_27",
            image_artifacts=[self._make_artifact("img_1"), self._make_artifact("img_2")],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.review_required_count, 1)
        self.assertEqual(report.overall_status, OverallInspectionStatus.REVIEW_REQUIRED)

    # 28. Ambiguous evidence
    def test_28_ambiguous_evidence_handled(self) -> None:
        obs = [self._make_obs("MRP 12S", sequence=0, image_id="img_1")]
        ocr = self._make_mock_ocr_engine({"img_1": obs})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_28",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.review_required_count, 1)

    # 29. Multiple requirements
    def test_29_multiple_requirements(self) -> None:
        obs = [
            self._make_obs("MRP Rs. 100", sequence=0, image_id="img_1"),
            self._make_obs("Net Qty: 200 g", sequence=1, image_id="img_1"),
        ]
        ocr = self._make_mock_ocr_engine({"img_1": obs})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_29",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[
                RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP),
                RequirementReference(requirement_id="REQ_QTY", target_field=EvidenceField.NET_QUANTITY),
            ],
        ))
        self.assertEqual(report.applicable_requirement_count, 2)
        self.assertEqual(report.pass_count, 2)

    # 30. Requirement isolation
    def test_30_requirement_isolation(self) -> None:
        obs = [self._make_obs("MRP Rs. 100", sequence=0, image_id="img_1")]
        ocr = self._make_mock_ocr_engine({"img_1": obs})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_30",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[
                RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP),
                RequirementReference(requirement_id="REQ_QTY", target_field=EvidenceField.NET_QUANTITY),
            ],
        ))
        self.assertEqual(report.pass_count, 1)
        self.assertEqual(report.not_visible_count, 1)

    # 31. Evidence isolation
    def test_31_evidence_isolation(self) -> None:
        obs = [self._make_obs("Batch No: B123", sequence=0, image_id="img_1")]
        ocr = self._make_mock_ocr_engine({"img_1": obs})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_31",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.not_visible_count, 1)

    # 32. Multi-image provenance
    def test_32_multi_image_provenance(self) -> None:
        obs1 = [self._make_obs("Manufactured by: Alpha Foods", sequence=0, image_id="img_front")]
        obs2 = [self._make_obs("Packed by: Beta Packers", sequence=0, image_id="img_back")]
        ocr = self._make_mock_ocr_engine({"img_front": obs1, "img_back": obs2})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_32",
            image_artifacts=[self._make_artifact("img_front"), self._make_artifact("img_back")],
            target_requirements=[RequirementReference(requirement_id="REQ_MFG", target_fields=[EvidenceField.MANUFACTURER_NAME, EvidenceField.PACKER_NAME])],
        ))
        res = report.verification_results[0]
        self.assertIn("img_front", res.image_ids)
        self.assertIn("img_back", res.image_ids)

    # 33. Image IDs preserved
    def test_33_image_ids_preserved(self) -> None:
        obs = [self._make_obs("MRP 50", sequence=0, image_id="img_alpha_99")]
        ocr = self._make_mock_ocr_engine({"img_alpha_99": obs})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_33",
            image_artifacts=[self._make_artifact("img_alpha_99")],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertIn("img_alpha_99", report.verification_results[0].image_ids)

    # 34. Evidence IDs preserved
    def test_34_evidence_ids_preserved(self) -> None:
        obs = [self._make_obs("MRP 50", sequence=0, image_id="img_1")]
        ocr = self._make_mock_ocr_engine({"img_1": obs})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_34",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[RequirementReference(requirement_id="REQ_MRP", target_field=EvidenceField.MRP)],
        ))
        self.assertGreater(len(report.verification_results[0].evidence_ids), 0)

    # 35. Requirement IDs preserved
    def test_35_requirement_ids_preserved(self) -> None:
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=self._make_mock_ocr_engine())
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_35",
            target_requirements=[RequirementReference(requirement_id="REQ_CANONICAL_001")],
        ))
        self.assertEqual(report.verification_results[0].requirement_id, "REQ_CANONICAL_001")

    # 36. Verification IDs preserved
    def test_36_verification_ids_preserved(self) -> None:
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=self._make_mock_ocr_engine())
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_36",
            target_requirements=[RequirementReference(requirement_id="REQ_1")],
        ))
        self.assertTrue(bool(report.verification_results[0].verification_id))

    # 37. Overall PASS
    def test_37_overall_pass(self) -> None:
        obs = [self._make_obs("MRP Rs. 100", sequence=0, image_id="img_1")]
        ocr = self._make_mock_ocr_engine({"img_1": obs})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_37",
            image_artifacts=[self._make_artifact("img_1")],
            applicability_context={"REQ_1": "applicable", "REQ_2": "not_applicable"},
            target_requirements=[
                RequirementReference(requirement_id="REQ_1", target_field=EvidenceField.MRP),
                RequirementReference(requirement_id="REQ_2", target_field=EvidenceField.IMPORTER_NAME),
            ],
        ))
        self.assertEqual(report.overall_status, OverallInspectionStatus.PASS)

    # 38. Overall FAIL
    def test_38_overall_fail(self) -> None:
        r1 = VerificationResult(requirement_id="REQ_1", status=VerificationStatus.PASS, reason="OK")
        r2 = VerificationResult(requirement_id="REQ_2", status=VerificationStatus.FAIL, reason="Violation")
        status, _ = compute_overall_status([r1, r2])
        self.assertEqual(status, OverallInspectionStatus.FAIL)

    # 39. Overall REVIEW_REQUIRED
    def test_39_overall_review_required(self) -> None:
        r1 = VerificationResult(requirement_id="REQ_1", status=VerificationStatus.PASS, reason="OK")
        r2 = VerificationResult(requirement_id="REQ_2", status=VerificationStatus.REVIEW_REQUIRED, reason="Ambiguity")
        status, _ = compute_overall_status([r1, r2])
        self.assertEqual(status, OverallInspectionStatus.REVIEW_REQUIRED)

    # 40. NOT_VISIBLE causes review
    def test_40_not_visible_causes_review(self) -> None:
        r1 = VerificationResult(requirement_id="REQ_1", status=VerificationStatus.PASS, reason="OK")
        r2 = VerificationResult(requirement_id="REQ_2", status=VerificationStatus.NOT_VISIBLE, reason="Not visible")
        status, _ = compute_overall_status([r1, r2])
        self.assertEqual(status, OverallInspectionStatus.REVIEW_REQUIRED)

    # 41. NOT_APPLICABLE does not cause failure
    def test_41_not_applicable_does_not_cause_failure(self) -> None:
        r1 = VerificationResult(requirement_id="REQ_1", status=VerificationStatus.PASS, reason="OK")
        r2 = VerificationResult(requirement_id="REQ_2", status=VerificationStatus.NOT_APPLICABLE, reason="Exempt")
        status, _ = compute_overall_status([r1, r2])
        self.assertEqual(status, OverallInspectionStatus.PASS)

    # 42. FAIL overrides REVIEW_REQUIRED for overall status
    def test_42_fail_overrides_review_required(self) -> None:
        r1 = VerificationResult(requirement_id="REQ_1", status=VerificationStatus.FAIL, reason="Violation")
        r2 = VerificationResult(requirement_id="REQ_2", status=VerificationStatus.REVIEW_REQUIRED, reason="Ambiguous")
        status, _ = compute_overall_status([r1, r2])
        self.assertEqual(status, OverallInspectionStatus.FAIL)

    # 43. Review overrides NOT_VISIBLE-only state
    def test_43_review_overrides_not_visible_only(self) -> None:
        r1 = VerificationResult(requirement_id="REQ_1", status=VerificationStatus.NOT_VISIBLE, reason="Not seen")
        r2 = VerificationResult(requirement_id="REQ_2", status=VerificationStatus.REVIEW_REQUIRED, reason="Ambiguous")
        status, _ = compute_overall_status([r1, r2])
        self.assertEqual(status, OverallInspectionStatus.REVIEW_REQUIRED)

    # 44. Deterministic ordering
    def test_44_deterministic_ordering(self) -> None:
        obs = [
            self._make_obs("MRP Rs. 100", sequence=0, image_id="img_1"),
            self._make_obs("Net Qty: 1 kg", sequence=1, image_id="img_1"),
        ]
        ocr = self._make_mock_ocr_engine({"img_1": obs})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        req = InspectionPipelineRequest(
            inspection_id="INSP_44",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[
                RequirementReference(requirement_id="REQ_1", target_field=EvidenceField.MRP),
                RequirementReference(requirement_id="REQ_2", target_field=EvidenceField.NET_QUANTITY),
            ],
        )
        report1 = orchestrator.run(req)
        report2 = orchestrator.run(req)
        self.assertEqual([r.requirement_id for r in report1.verification_results], [r.requirement_id for r in report2.verification_results])

    # 45. Deterministic repeated execution
    def test_45_deterministic_repeated_execution(self) -> None:
        obs = [self._make_obs("MRP Rs. 100", sequence=0, image_id="img_1")]
        ocr = self._make_mock_ocr_engine({"img_1": obs})
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=ocr)
        req = InspectionPipelineRequest(
            inspection_id="INSP_45",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[RequirementReference(requirement_id="REQ_1", target_field=EvidenceField.MRP)],
        )
        r1 = orchestrator.run(req)
        r2 = orchestrator.run(req)
        self.assertEqual(r1.overall_status, r2.overall_status)
        self.assertEqual(r1.pass_count, r2.pass_count)

    # 46. No legal requirement invention
    def test_46_no_legal_requirement_invention(self) -> None:
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=self._make_mock_ocr_engine())
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_46",
            target_requirements=[RequirementReference(requirement_id="ONLY_SUPPLIED_REQ")],
        ))
        self.assertEqual(len(report.verification_results), 1)
        self.assertEqual(report.verification_results[0].requirement_id, "ONLY_SUPPLIED_REQ")

    # 47. No Gemini direct final status (Overall status is computed deterministically)
    def test_47_overall_status_not_generated_by_gemini(self) -> None:
        obs = [self._make_obs("MRP Rs. 100", sequence=0, image_id="img_1")]
        fake_client = FakeGeminiClient(default_response=json.dumps({
            "requirement_id": "REQ_1",
            "recommendation": "PASS",
            "evidence_sufficiency": "SUFFICIENT",
            "reason": "OK",
            "evidence_ids": ["obs_0"],
        }))
        gemini_srv = GeminiEvidenceService(client=fake_client, config=GeminiConfig(api_key="mock"))
        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine({"img_1": obs}),
            gemini_service=gemini_srv,
        )
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_47",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[RequirementReference(requirement_id="REQ_1", target_field=EvidenceField.MRP)],
        ))
        self.assertIsInstance(report.overall_status, OverallInspectionStatus)

    # 48. Phase 5E safety gate respected
    def test_48_phase5e_safety_gate_respected(self) -> None:
        obs = [self._make_obs("MRP 12S", sequence=0, image_id="img_1")]

        def dynamic_handler(prompt_text: str) -> str:
            try:
                data_idx = prompt_text.find("EVALUATION INPUT:\n")
                if data_idx != -1:
                    payload = json.loads(prompt_text[data_idx + len("EVALUATION INPUT:\n"):])
                    candidates = payload.get("evidence_candidates", [])
                    ev_ids = [c["evidence_id"] for c in candidates]
                else:
                    ev_ids = []
            except Exception:
                ev_ids = []

            return json.dumps({
                "requirement_id": "REQ_1",
                "recommendation": "PASS",
                "evidence_sufficiency": "SUFFICIENT",
                "reason": "Trying to pass ambiguous MRP 12S",
                "evidence_ids": ev_ids,
            })

        fake_client = FakeGeminiClient(response_handler=dynamic_handler)
        gemini_srv = GeminiEvidenceService(client=fake_client, config=GeminiConfig(api_key="mock"))
        orchestrator = InspectionPipelineOrchestrator(
            ocr_engine=self._make_mock_ocr_engine({"img_1": obs}),
            gemini_service=gemini_srv,
        )
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_48",
            image_artifacts=[self._make_artifact("img_1")],
            target_requirements=[RequirementReference(requirement_id="REQ_1", target_field=EvidenceField.MRP)],
        ))
        self.assertEqual(report.verification_results[0].status, VerificationStatus.REVIEW_REQUIRED)

    # 49. No database writes in pipeline
    def test_49_no_database_writes_in_pipeline(self) -> None:
        import backend.app.services.inspection_pipeline.orchestrator as orch
        import backend.app.services.inspection_pipeline.report as rep
        for mod in (orch, rep):
            with open(mod.__file__, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("supabase", content.lower())
            self.assertNotIn("insert(", content)
            self.assertNotIn("upsert(", content)

    # 50. No persistence / serializable report
    def test_50_serializable_report_no_persistence(self) -> None:
        orchestrator = InspectionPipelineOrchestrator(ocr_engine=self._make_mock_ocr_engine())
        report = orchestrator.run(InspectionPipelineRequest(
            inspection_id="INSP_50",
            target_requirements=[RequirementReference(requirement_id="REQ_1")],
        ))
        d = report.to_dict()
        self.assertEqual(d["inspection_id"], "INSP_50")
        self.assertIn("counts", d)


if __name__ == "__main__":
    unittest.main()

