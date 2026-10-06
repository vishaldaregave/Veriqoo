import 'package:flutter/foundation.dart';
import 'package:shared_core/services/compliance_analysis.dart';

import 'package:flutter_application_1/features/scan/result/compliance_score.dart';

/// A stable, display-only reference for a compliance report plus the compact
/// payload encoded into the "Generate QR" code.
///
/// Pure (no Flutter widget imports). Both fields are deterministic functions of
/// the analysis + score, so re-opening the same report yields the same id and
/// QR payload. This is a PRESENTATION derivation only — nothing here is sent to
/// or persisted by `SupabaseService`.
@immutable
class ReportReference {
  const ReportReference({required this.id, required this.qrPayload});

  /// Human-facing reference id, e.g. `VQ-A1B2C3`.
  final String id;

  /// Compact single-line payload for the QR code, e.g.
  /// `VERIQOO|VQ-A1B2C3|Oat Crunch|score=92|v=7|f=0|m=0`.
  final String qrPayload;

  /// Builds the reference from an [analysis] + its derived [score].
  factory ReportReference.fromAnalysis(
    ComplianceAnalysis analysis,
    ComplianceScore score,
  ) {
    final seed = <String>[
      analysis.productName,
      analysis.mrp,
      analysis.netQuantity,
      analysis.manufacturer,
    ].join('|');

    final id = 'VQ-${_stableHash6(seed)}';
    final product = _sanitize(analysis.productName);
    final qrPayload = 'VERIQOO|$id|$product'
        '|score=${score.score}'
        '|v=${score.verified}'
        '|f=${score.flagged}'
        '|m=${score.missing}';

    return ReportReference(id: id, qrPayload: qrPayload);
  }

  /// A deterministic, web-safe 6-hex-digit hash.
  ///
  /// Uses a bounded polynomial rolling hash (mod 2^24) so every intermediate
  /// value stays inside the 53-bit safe-integer range — unlike `String.hashCode`
  /// (not stable across runs) or a 32-bit FNV multiply (loses precision when
  /// compiled to JavaScript).
  static String _stableHash6(String input) {
    var hash = 0;
    for (final unit in input.codeUnits) {
      hash = (hash * 31 + unit) % 0x1000000;
    }
    return hash.toRadixString(16).toUpperCase().padLeft(6, '0');
  }

  /// Strips payload delimiters/newlines from free text so the single-line QR
  /// payload stays parseable.
  static String _sanitize(String value) =>
      value.replaceAll(RegExp(r'[|\r\n]+'), ' ').trim();
}
