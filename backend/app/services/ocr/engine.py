"""OCR Engine abstractions and PaddleOCR implementation for Phase 5C."""

from __future__ import annotations

import inspect
import io
from abc import ABC, abstractmethod
from typing import Any

from PIL import Image

from backend.app.services.ocr.config import OCRConfig
from backend.app.services.ocr.errors import (
    OCRInitializationError,
    OCRModelUnavailableError,
    OCRProcessingError,
)


class OCREngine(ABC):
    """Abstract interface for statutory legal OCR extraction engines."""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def engine_version(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def predict(
        self,
        image_bytes: bytes,
        config: OCRConfig,
    ) -> list[tuple[list[list[float]], tuple[str, float]]]:
        """Execute text detection and recognition on normalized image bytes.

        Returns list of tuples: (quadrilateral_points, (raw_text, confidence_score))
        where quadrilateral_points is 4 coordinate pairs [[x1, y1], [x2, y2], [x3, y3], [x4, y4]].
        """
        raise NotImplementedError


class PaddleOCREngine(OCREngine):
    """Production wrapper for PaddleOCR."""

    def __init__(self, config: OCRConfig | None = None) -> None:
        self.config = config or OCRConfig()
        self._ocr_instance: Any = None
        self._version: str = "unavailable"
        self._initialize()

    def _initialize(self) -> None:
        """Dynamically load and verify PaddleOCR package."""
        try:
            import paddleocr
            self._version = getattr(paddleocr, "__version__", "unknown")
            from paddleocr import PaddleOCR

            init_sig = inspect.signature(PaddleOCR.__init__)
            params = init_sig.parameters

            init_kwargs: dict[str, Any] = {"lang": self.config.language}
            if "device" in params or "kwargs" in params:
                # PaddleOCR 3.x / PaddleX API
                device = "gpu" if self.config.use_gpu else "cpu"
                init_kwargs["device"] = device
                if "use_textline_orientation" in params:
                    init_kwargs["use_textline_orientation"] = self.config.use_angle_cls
                init_kwargs["enable_mkldnn"] = self.config.enable_mkldnn
                if "text_det_thresh" in params:
                    init_kwargs["text_det_thresh"] = self.config.det_db_thresh
                if "text_det_box_thresh" in params:
                    init_kwargs["text_det_box_thresh"] = self.config.det_db_box_thresh
                if "text_rec_score_thresh" in params:
                    init_kwargs["text_rec_score_thresh"] = self.config.drop_score
            else:
                # PaddleOCR 2.x API
                if "use_angle_cls" in params:
                    init_kwargs["use_angle_cls"] = self.config.use_angle_cls
                if "use_gpu" in params:
                    init_kwargs["use_gpu"] = self.config.use_gpu
                if "enable_mkldnn" in params:
                    init_kwargs["enable_mkldnn"] = self.config.enable_mkldnn
                if "show_log" in params:
                    init_kwargs["show_log"] = False

            self._ocr_instance = PaddleOCR(**init_kwargs)
        except ImportError:
            self._ocr_instance = None
            self._version = "not_installed"
        except Exception as exc:
            self._ocr_instance = None
            raise OCRInitializationError(f"Failed to initialize PaddleOCR: {exc}") from exc

    @property
    def engine_name(self) -> str:
        return "PaddleOCR"

    @property
    def engine_version(self) -> str:
        return self._version

    def predict(
        self,
        image_bytes: bytes,
        config: OCRConfig | None = None,
    ) -> list[tuple[list[list[float]], tuple[str, float]]]:
        """Execute text prediction using PaddleOCR."""
        if self._ocr_instance is None:
            raise OCRModelUnavailableError(
                f"PaddleOCR is not installed or available in this environment (version: {self._version}). "
                f"Minimal installation requires 'paddleocr' and compatible 'paddlepaddle'."
            )

        cfg = config or self.config

        try:
            # Convert bytes to numpy array via Pillow
            img = Image.open(io.BytesIO(image_bytes))
            import numpy as np
            img_np = np.array(img)

            # Invoke PaddleOCR (compatible with 2.x and 3.x)
            if hasattr(self._ocr_instance, "predict"):
                raw_result = list(self._ocr_instance.predict(img_np))
            elif hasattr(self._ocr_instance, "ocr"):
                raw_result = self._ocr_instance.ocr(img_np, cls=cfg.use_angle_cls)
            else:
                raw_result = []

            if not raw_result:
                return []

            parsed_observations: list[tuple[list[list[float]], tuple[str, float]]] = []

            # PaddleOCR 3.x returns list of dictionaries per image
            if isinstance(raw_result[0], dict):
                for res_dict in raw_result:
                    texts = res_dict.get("rec_texts", [])
                    scores = res_dict.get("rec_scores", [])
                    polys = res_dict.get("rec_polys", [])
                    for poly, text, score in zip(polys, texts, scores):
                        if hasattr(poly, "tolist"):
                            box_pts = poly.tolist()
                        else:
                            box_pts = [list(pt) for pt in poly]
                        parsed_observations.append((box_pts, (str(text), float(score))))
            elif isinstance(raw_result[0], list):
                # PaddleOCR 2.x returns list of pages
                for line in raw_result[0]:
                    if not line or len(line) != 2:
                        continue
                    box_pts = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                    text_info = line[1]  # (text_str, confidence_float)
                    if len(text_info) == 2:
                        text_str = str(text_info[0])
                        conf_val = float(text_info[1])
                        parsed_observations.append((box_pts, (text_str, conf_val)))

            return parsed_observations
        except Exception as exc:
            raise OCRProcessingError(f"PaddleOCR prediction execution failed: {exc}") from exc


class MockOCREngine(OCREngine):
    """Deterministic synthetic OCR engine for unit tests and contract validation."""

    def __init__(
        self,
        observations: list[tuple[list[list[float]], tuple[str, float]]] | None = None,
        engine_version: str = "mock_paddleocr_1.0",
        simulate_failure: bool = False,
    ) -> None:
        self._observations = observations or []
        self._version = engine_version
        self.simulate_failure = simulate_failure
        self.call_count = 0

    @property
    def engine_name(self) -> str:
        return "MockPaddleOCR"

    @property
    def engine_version(self) -> str:
        return self._version

    def set_observations(self, observations: list[tuple[list[list[float]], tuple[str, float]]]) -> None:
        self._observations = observations

    def predict(
        self,
        image_bytes: bytes,
        config: OCRConfig,
    ) -> list[tuple[list[list[float]], tuple[str, float]]]:
        self.call_count += 1
        if self.simulate_failure:
            raise OCRProcessingError("Simulated mock OCR engine prediction failure.")

        return self._observations
