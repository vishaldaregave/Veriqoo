import 'package:flutter/foundation.dart';
import 'package:shared_core/services/compliance_analysis.dart';

/// A deterministic, PRESENTATION-LAYER compliance score derived from a
/// [ComplianceAnalysis].
///
/// This is NOT a backend/service change: the analysis payload is unchanged and
/// `SupabaseService` still persists exactly what it did before. The score only
/// shapes how the existing analysis is *displayed* on the compliance report.
///
/// ## Derivation (D2 — documented so it stays reproducible)
///
/// Over the seven mandatory declaration fields
/// `productName, mrp, netQuantity, manufacturer, address, packingDate,
/// customerCare` (N = [mandatoryTotal] = 7):
///
/// * `presentCount` = number of those fields whose `value.trim()` is non-empty.
/// * `base = (presentCount / 7) * 100`.
/// * `missingPenalty = `[missingPointsEach]` * missingInformation.length`.
/// * `issuePenalty = Σ severityWeight(issue.severity)` across `possibleIssues`,
///   where the weight (on the lower-cased severity string) is:
///   `critical`/`high` → [weightHigh], `medium` → [weightMedium],
///   `low` → [weightLow], anything else → [weightDefault].
/// * `score = (base − missingPenalty − issuePenalty).clamp(0, 100).round()`.
///
/// The function is pure: the same analysis always yields the same score, which
/// the unit tests pin against the three fixtures (all-compliant → 100,
/// missing-only and with-issues → their reduced values).
@immutable
class ComplianceScore {
  const ComplianceScore({
    required this.score,
    required this.verified,
    required this.flagged,
    required this.missing,
    this.mandatoryTotal = mandatoryFieldCount,
  });

  /// Final 0–100 compliance score.
  final int score;

  /// Mandatory fields detected (D3 summary — the "VERIFIED" count).
  final int verified;

  /// Number of potential issues (D3 summary — the "FLAGGED" count).
  final int flagged;

  /// Number of missing mandatory declarations (D3 summary — "MISSING" count).
  final int missing;

  /// The denominator used for [verified] (always [mandatoryFieldCount]).
  final int mandatoryTotal;

  /// Number of mandatory declaration fields considered (N = 7).
  static const int mandatoryFieldCount = 7;

  /// Points subtracted per missing mandatory declaration.
  static const int missingPointsEach = 6;

  /// Severity weights (subtracted per potential issue).
  static const int weightHigh = 12;
  static const int weightMedium = 8;
  static const int weightLow = 5;
  static const int weightDefault = 8;

  /// Weight for a single issue [severity] string (case-insensitive).
  static int severityWeight(String severity) {
    switch (severity.trim().toLowerCase()) {
      case 'critical':
      case 'high':
        return weightHigh;
      case 'medium':
        return weightMedium;
      case 'low':
        return weightLow;
      default:
        return weightDefault;
    }
  }

  /// Derives the [ComplianceScore] from an [analysis] using the D2 formula.
  factory ComplianceScore.fromAnalysis(ComplianceAnalysis analysis) {
    final mandatoryValues = <String>[
      analysis.productName,
      analysis.mrp,
      analysis.netQuantity,
      analysis.manufacturer,
      analysis.address,
      analysis.packingDate,
      analysis.customerCare,
    ];

    final presentCount =
        mandatoryValues.where((value) => value.trim().isNotEmpty).length;

    final base = (presentCount / mandatoryFieldCount) * 100.0;
    final missingPenalty =
        (missingPointsEach * analysis.missingInformation.length).toDouble();
    final issuePenalty = analysis.possibleIssues
        .fold<int>(0, (sum, issue) => sum + severityWeight(issue.severity))
        .toDouble();

    final raw = (base - missingPenalty - issuePenalty).clamp(0.0, 100.0);

    return ComplianceScore(
      score: raw.round(),
      verified: presentCount,
      flagged: analysis.possibleIssues.length,
      missing: analysis.missingInformation.length,
    );
  }
}
