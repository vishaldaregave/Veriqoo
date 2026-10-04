"""Configuration parameters for Phase 5C PaddleOCR engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OCRConfig:
    """Configurable parameters for OCR prediction and observation filtering."""
    language: str = "en"                        # Target language model (e.g. 'en', 'hi', 'devanagari')
    use_angle_cls: bool = True                  # Use orientation/angle classification
    use_gpu: bool = False                       # CPU execution default for consistency
    det_db_thresh: float = 0.3                  # Detection binarization threshold
    det_db_box_thresh: float = 0.6              # Detection polygon score threshold
    drop_score: float = 0.0                     # Keep all observations from engine
    min_confidence_threshold: float = 0.0       # Minimum confidence to retain
    enable_mkldnn: bool = False                 # Intel MKL-DNN acceleration toggle
    engine_name: str = "PaddleOCR"              # Descriptive engine identifier

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "use_angle_cls": self.use_angle_cls,
            "use_gpu": self.use_gpu,
            "det_db_thresh": self.det_db_thresh,
            "det_db_box_thresh": self.det_db_box_thresh,
            "drop_score": self.drop_score,
            "min_confidence_threshold": self.min_confidence_threshold,
            "enable_mkldnn": self.enable_mkldnn,
            "engine_name": self.engine_name,
        }

