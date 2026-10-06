/// Centralized, localization-ready copy for the Phase 6 processing, compliance
/// report, and evidence-viewer screens.
///
/// Mirrors the `HomeStrings` pattern (plain `static const` fields) so every
/// user-facing string lives in one place and can later be swapped for an
/// `AppLocalizations` lookup without touching the widgets.
abstract final class ResultStrings {
  const ResultStrings._();

  // --- Processing screen -----------------------------------------------------
  static const String processingTitle = 'ANALYZING';
  static const String phaseReadingLabel = 'READING LABEL';
  static const String phaseExtractingDeclarations = 'EXTRACTING DECLARATIONS';
  static const String phaseVerifyingCompliance = 'VERIFYING COMPLIANCE';
  static const String extractedTextHeader = 'EXTRACTED TEXT';
  static const String extractRowReading = 'READING…';
  static const String extractRowPending = '—';
  static const String analysisInterruptedTitle = 'ANALYSIS INTERRUPTED';
  static const String analysisInterruptedMessage =
      'The inspection could not be completed. Check your connection and '
      'try again.';
  static const String tryAgain = 'TRY AGAIN';

  // --- Compliance report -----------------------------------------------------
  static const String reportTitle = 'COMPLIANCE REPORT';
  static const String scoreCaption = 'SCORE';
  static const String unknownProduct = 'UNKNOWN PRODUCT';
  static const String productDetailsHeader = 'PRODUCT DETAILS';
  static const String findingsHeader = 'FINDINGS';
  static const String notDetected = 'Not detected';
  static const String allClear =
      'No mandatory declarations are missing and no potential violations were '
      'detected from the available evidence.';

  // Summary chips.
  static const String summaryVerified = 'VERIFIED';
  static const String summaryFlagged = 'FLAGGED';
  static const String summaryMissing = 'MISSING';

  // Product-detail / extraction row labels.
  static const String labelProduct = 'PRODUCT';
  static const String labelMrp = 'MRP';
  static const String labelNetQuantity = 'NET QUANTITY';
  static const String labelManufacturer = 'MANUFACTURER';
  static const String labelAddress = 'ADDRESS';
  static const String labelPackingDate = 'PACKING DATE';
  static const String labelCustomerCare = 'CUSTOMER CARE';

  // Finding tiles.
  static const String findingMissingDeclaration = 'MISSING DECLARATION';
  static const String findingPotentialViolation = 'POTENTIAL VIOLATION';
  static const String viewEvidence = 'View evidence';
  static const String inspect = 'Inspect';

  // Actions.
  static const String actionShare = 'Share';
  static const String actionGenerateQr = 'Generate QR';
  static const String actionSave = 'Save';
  static const String actionReportIssue = 'Report issue';
  static const String actionViewEvidence = 'VIEW EVIDENCE';

  static const String reportSavedMessage = 'Inspection report saved.';
  static String reportSaveFailedMessage(Object error) =>
      'Could not save inspection report: $error';

  /// Human-readable summary used by the Share action.
  static String shareSummary({
    required String productName,
    required int score,
    required int verified,
    required int flagged,
    required int missing,
    required String id,
  }) {
    return 'VERIQOO Compliance Report\n'
        '$productName\n'
        'Score: $score/100\n'
        'Verified: $verified · Flagged: $flagged · Missing: $missing\n'
        'Ref: $id';
  }

  // QR sheet.
  static const String qrTitle = 'REPORT QR';
  static const String qrHint =
      'Scan to carry this report reference and summary.';

  // --- Evidence viewer -------------------------------------------------------
  static const String evidenceTitle = 'EVIDENCE';
  static const String evidenceEmptyTitle = 'NO EVIDENCE';
  static const String evidenceEmptyMessage =
      'Captured product images will appear here after a scan.';
  static const String whyThisMatters = 'WHY THIS MATTERS';
  static const String whyThisMattersAction = 'WHY THIS MATTERS';

  /// Shown beneath a derived (best-effort) evidence association so the user
  /// knows the box/region is inferred, not a backend-authoritative coordinate.
  static const String derivedNote =
      'DERIVED — region inferred from live detection, not an exact backend '
      'coordinate.';

  /// Plain-language fallback explanation for a missing mandatory declaration.
  static String whyMissingDeclaration(String field) =>
      'A $field declaration is required on the package but was not detected in '
      'the captured evidence. Missing mandatory declarations are a common '
      'labelling compliance gap.';

  /// Plain-language fallback when an issue carries no description.
  static const String whyGenericViolation =
      'This finding was flagged as a potential compliance concern based on the '
      'extracted label text. Review the highlighted region against the '
      'applicable rule.';
}
