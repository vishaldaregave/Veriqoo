/// The ordered live-scan states surfaced to the user as the inspection
/// progresses, from framing the product through to a finished analysis.
///
/// These drive the subtle `ScanPhaseBanner` motion (no giant spinners). The
/// ordinal order is meaningful — [nextScanPhase] only advances forward.
enum ScanPhase {
  positionProduct,
  productDetected,
  readingLabel,
  extractingDeclarations,
  verifyingCompliance,
  analysisComplete,
}

/// Uppercase display copy for a [ScanPhase].
extension ScanPhaseCaption on ScanPhase {
  /// Short caption rendered in the scan-phase banner.
  String get caption {
    switch (this) {
      case ScanPhase.positionProduct:
        return 'POSITION PRODUCT';
      case ScanPhase.productDetected:
        return 'PRODUCT DETECTED';
      case ScanPhase.readingLabel:
        return 'READING LABEL';
      case ScanPhase.extractingDeclarations:
        return 'EXTRACTING DECLARATIONS';
      case ScanPhase.verifyingCompliance:
        return 'VERIFYING COMPLIANCE';
      case ScanPhase.analysisComplete:
        return 'ANALYSIS COMPLETE';
    }
  }

  /// Alias kept for call sites that read `.label`.
  String get label => caption;
}

/// Pure transition for the live-scan phase machine.
///
/// Given the current [current] phase and the live signals below, returns the
/// phase that should be shown. The function is monotonic: it never moves
/// backward (so a dropped detection does not flicker the banner), with the one
/// exception that an idle camera with no evidence resets to
/// [ScanPhase.positionProduct].
///
/// Signals:
/// * [detectedFieldCount] — live OCR field boxes currently detected.
/// * [hasText] — any recognized text in the latest frame.
/// * [capturing] — a still capture is in progress / at least one image taken.
/// * [analyzing] — the analysis pipeline is running.
/// * [complete] — the pipeline finished and a result is ready.
ScanPhase nextScanPhase(
  ScanPhase current, {
  required int detectedFieldCount,
  required bool hasText,
  required bool capturing,
  required bool analyzing,
  required bool complete,
}) {
  final ScanPhase target;
  if (complete) {
    target = ScanPhase.analysisComplete;
  } else if (analyzing) {
    target = ScanPhase.verifyingCompliance;
  } else if (capturing) {
    target = ScanPhase.extractingDeclarations;
  } else if (detectedFieldCount > 0) {
    target = ScanPhase.readingLabel;
  } else if (hasText) {
    target = ScanPhase.productDetected;
  } else {
    target = ScanPhase.positionProduct;
  }

  // Monotonic forward progress once we are mid-pipeline: capturing/analyzing/
  // complete are latching, so transient detection loss cannot regress them.
  final latched = current == ScanPhase.verifyingCompliance ||
      current == ScanPhase.analysisComplete ||
      current == ScanPhase.extractingDeclarations;
  if (latched && target.index < current.index && !complete && !analyzing) {
    return current;
  }
  return target;
}
