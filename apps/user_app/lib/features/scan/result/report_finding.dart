import 'package:flutter/foundation.dart';
import 'package:shared_core/design_system/design_system.dart' show VeriqooStatusKind;
import 'package:shared_core/services/compliance_analysis.dart';

import 'package:flutter_application_1/features/scan/model/detected_field.dart';

/// What a single inspection [ReportFinding] represents.
enum ReportFindingKind {
  /// A mandatory declaration that was not detected on the label.
  missingDeclaration,

  /// A possible compliance violation surfaced by the analysis.
  potentialViolation,
}

/// One numbered line on the compliance report's FINDINGS section.
///
/// Pure/data-only so it is trivially unit-testable. [status] is the
/// [VeriqooStatusKind] the UI renders ([VeriqooStatusKind.missing] for missing
/// declarations; [VeriqooStatusKind.violation] for legally-verified issues,
/// else [VeriqooStatusKind.flag]).
@immutable
class ReportFinding {
  const ReportFinding({
    required this.number,
    required this.kind,
    required this.title,
    required this.status,
    this.detail,
    this.issue,
    this.missingField,
  });

  /// 1-based position across the combined (missing-then-issues) list.
  final int number;

  /// Finding category.
  final ReportFindingKind kind;

  /// Short, strong title line.
  final String title;

  /// The status marker rendered for this finding.
  final VeriqooStatusKind status;

  /// Optional supporting detail (issue description).
  final String? detail;

  /// The source issue, when [kind] is [ReportFindingKind.potentialViolation].
  final ComplianceIssue? issue;

  /// The source missing-declaration text, when [kind] is
  /// [ReportFindingKind.missingDeclaration].
  final String? missingField;

  /// Zero-padded ordinal for the tile, e.g. `01`, `02`.
  String get twoDigit => number.toString().padLeft(2, '0');

  /// Builds the ordered findings for [analysis]: every missing declaration
  /// first (as [ReportFindingKind.missingDeclaration]), then every possible
  /// issue (as [ReportFindingKind.potentialViolation]), numbered 1-based across
  /// the combined list.
  static List<ReportFinding> fromAnalysis(ComplianceAnalysis analysis) {
    final findings = <ReportFinding>[];
    var number = 1;

    for (final missing in analysis.missingInformation) {
      findings.add(
        ReportFinding(
          number: number++,
          kind: ReportFindingKind.missingDeclaration,
          title: missing,
          status: VeriqooStatusKind.missing,
          missingField: missing,
        ),
      );
    }

    for (final issue in analysis.possibleIssues) {
      findings.add(
        ReportFinding(
          number: number++,
          kind: ReportFindingKind.potentialViolation,
          title: issue.title.trim().isNotEmpty
              ? issue.title.trim()
              : 'Potential violation',
          detail: issue.description.trim().isNotEmpty
              ? issue.description.trim()
              : null,
          status:
              issue.verificationStatus == LegalVerificationStatus.legallyVerified
                  ? VeriqooStatusKind.violation
                  : VeriqooStatusKind.flag,
          issue: issue,
        ),
      );
    }

    return findings;
  }
}

/// A best-effort, DERIVED association between a [ReportFinding] and the evidence
/// it most likely relates to.
///
/// Because the backend does not return per-issue bounding boxes, this never
/// claims backend-authoritative coordinates: [derived] is always `true`, and
/// [reason] explains how the association was synthesized. When a live-detection
/// region matched the finding's keyword, [field] carries that region's rect;
/// otherwise [field] is null and the viewer simply shows the primary image.
@immutable
class EvidenceLink {
  const EvidenceLink({
    required this.imageIndex,
    required this.derived,
    this.field,
    this.reason,
  });

  /// Index into `scanState.evidence` to show (best-effort; defaults to primary).
  final int imageIndex;

  /// Always true — the association is synthesized, never backend-precise.
  final bool derived;

  /// The matched live-detection region, if any.
  final DetectedField? field;

  /// Human-readable note on how the link was derived.
  final String? reason;
}

/// Maps a finding's free text to the most relevant [DetectedFieldLabels] value.
///
/// Keyword rules (first match wins, case-insensitive):
/// * `mrp` / `price` → [DetectedFieldLabels.mrp]
/// * `net` / `qty` / `quantity` → [DetectedFieldLabels.mandatoryDeclaration]
/// * `manufactured` / `mfg` / `marketed` / `packed` →
///   [DetectedFieldLabels.manufacturer]
/// * `batch` / `lot` → [DetectedFieldLabels.batch]
/// * otherwise → [DetectedFieldLabels.productName]
String targetFieldLabel(String text) {
  final t = text.toLowerCase();
  if (t.contains('mrp') || t.contains('price')) {
    return DetectedFieldLabels.mrp;
  }
  if (t.contains('net') || t.contains('qty') || t.contains('quantity')) {
    return DetectedFieldLabels.mandatoryDeclaration;
  }
  if (t.contains('manufactured') ||
      t.contains('mfg') ||
      t.contains('marketed') ||
      t.contains('packed')) {
    return DetectedFieldLabels.manufacturer;
  }
  if (t.contains('batch') || t.contains('lot')) {
    return DetectedFieldLabels.batch;
  }
  return DetectedFieldLabels.productName;
}

/// The text used to keyword-match a [finding] to a detection label.
String _matchText(ReportFinding finding) {
  if (finding.missingField != null) {
    return finding.missingField!;
  }
  final issue = finding.issue;
  if (issue != null) {
    return <String>[
      issue.title,
      issue.description,
      issue.ocrEvidence ?? '',
      ...issue.ruleTitles,
    ].join(' ');
  }
  return finding.title;
}

/// Links a [finding] to the evidence it most likely relates to, on a
/// BEST-EFFORT basis (see [EvidenceLink]).
///
/// Pure: given the same inputs it always returns the same link. When a
/// [detectedFields] entry matches the finding's keyword label its rect is
/// carried; otherwise the primary image (index 0) is shown with no highlight.
/// The association is always flagged [EvidenceLink.derived].
EvidenceLink linkFinding(
  ReportFinding finding, {
  required List<DetectedField> detectedFields,
  required int evidenceCount,
}) {
  final targetLabel = targetFieldLabel(_matchText(finding));

  DetectedField? match;
  for (final field in detectedFields) {
    if (field.label == targetLabel) {
      match = field;
      break;
    }
  }

  // The live-detection fields are not per-image authoritative, so we fall back
  // to the primary image (index 0) in every case; clamp defensively.
  final imageIndex = evidenceCount > 0 ? 0 : 0;

  if (match != null) {
    return EvidenceLink(
      imageIndex: imageIndex,
      derived: true,
      field: match,
      reason: 'Matched the "$targetLabel" region from live detection.',
    );
  }

  return EvidenceLink(
    imageIndex: imageIndex,
    derived: true,
    reason: 'No matching live-detection region; showing the primary image.',
  );
}
