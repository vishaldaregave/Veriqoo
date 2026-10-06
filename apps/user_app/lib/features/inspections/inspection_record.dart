import 'package:flutter/foundation.dart';
import 'package:shared_core/design_system/design_system.dart';

/// An immutable, UI-ready view of a single saved inspection row.
///
/// Built from the raw `inspections` table map (see `SupabaseService
/// .saveInspectionReport`) via [InspectionRecord.fromMap], which reads every
/// field defensively so a missing or wrongly-typed column degrades to a safe
/// default instead of throwing into the UI.
///
/// Two values are DERIVED client-side rather than read from the table (the
/// table stores neither): [score] (see [deriveScore]) and [status] (see
/// [deriveStatus]). This is intentional — see the repository doc comment.
@immutable
class InspectionRecord {
  const InspectionRecord({
    required this.id,
    required this.displayId,
    required this.productName,
    required this.inspectedAt,
    required this.isCompliant,
    required this.missingInformation,
    required this.issueCount,
    required this.violationCount,
    required this.score,
    required this.status,
    required this.timestampLabel,
  });

  /// Raw row identifier as a string (used for navigation), or a synthesized
  /// `row-<index>` fallback when the table has no readable `id` column.
  final String id;

  /// Human-facing reference, e.g. `VRQ-20261004-0182` (rendered in mono).
  final String displayId;

  /// Product name, or `'Unknown product'` when absent/blank.
  final String productName;

  /// Parsed `inspected_at`, or null when missing/unparseable.
  final DateTime? inspectedAt;

  /// Raw `is_compliant` flag, or null when the column is absent.
  final bool? isCompliant;

  /// Declared-but-missing fields reported by the analysis.
  final List<String> missingInformation;

  /// Total number of flagged possible issues.
  final int issueCount;

  /// Subset of [issueCount] whose severity is `high` or `critical`.
  final int violationCount;

  /// Derived 0..100 compliance score (never a stored column).
  final int score;

  /// Derived verification outcome chip kind.
  final VeriqooStatusKind status;

  /// Preformatted `YYYY-MM-DD HH:MM` label, or `'—'` when the date is null.
  final String timestampLabel;

  /// Builds a record from a raw `inspections` row.
  ///
  /// [index] is the row's position in the fetched page; it seeds the
  /// synthesized id/displayId when the row carries no `id` column.
  factory InspectionRecord.fromMap(Map<String, dynamic> row, {int index = 0}) {
    final rawId = row['id'];
    final hasId = rawId != null && rawId.toString().trim().isNotEmpty;
    final id = hasId ? rawId.toString().trim() : 'row-$index';

    final productRaw = row['product_name'];
    final productName = (productRaw is String && productRaw.trim().isNotEmpty)
        ? productRaw.trim()
        : 'Unknown product';

    final inspectedAt = _parseDate(row['inspected_at']);
    final isCompliant = row['is_compliant'] is bool
        ? row['is_compliant'] as bool
        : null;

    final missingInformation = _stringList(row['missing_information']);
    final issueCount = _issueCount(row['possible_issues']);
    final violationCount = _violationCount(row['possible_issues']);
    final missingCount = missingInformation.length;

    return InspectionRecord(
      id: id,
      displayId: _displayId(
        inspectedAt: inspectedAt,
        id: hasId ? id : null,
        index: index,
      ),
      productName: productName,
      inspectedAt: inspectedAt,
      isCompliant: isCompliant,
      missingInformation: missingInformation,
      issueCount: issueCount,
      violationCount: violationCount,
      score: deriveScore(
        isCompliant: isCompliant,
        issueCount: issueCount,
        missingCount: missingCount,
      ),
      status: deriveStatus(
        isCompliant: isCompliant,
        issueCount: issueCount,
        violationCount: violationCount,
        missingCount: missingCount,
      ),
      timestampLabel: _timestampLabel(inspectedAt),
    );
  }
}

/// Derives a 0..100 compliance score from the analysis signals.
///
/// A compliant inspection is a perfect 100. Otherwise each flagged issue costs
/// 15 and each missing declaration costs 10, floored at 0 and capped at 95 so a
/// non-compliant record never visually ties a compliant one.
int deriveScore({
  required bool? isCompliant,
  required int issueCount,
  required int missingCount,
}) {
  if (isCompliant == true) {
    return 100;
  }
  return (100 - (issueCount * 15 + missingCount * 10)).clamp(0, 95);
}

/// Derives the verification outcome chip kind from the analysis signals.
///
/// Compliant wins outright; otherwise a severe issue is a violation, a
/// non-severe issue is a flag, and anything else falls back to "not detected".
VeriqooStatusKind deriveStatus({
  required bool? isCompliant,
  required int issueCount,
  required int violationCount,
  required int missingCount,
}) {
  if (isCompliant == true) {
    return VeriqooStatusKind.verified;
  }
  if (violationCount > 0) {
    return VeriqooStatusKind.violation;
  }
  if (issueCount > 0) {
    return VeriqooStatusKind.flag;
  }
  return VeriqooStatusKind.missing;
}

DateTime? _parseDate(dynamic value) {
  if (value is DateTime) {
    return value;
  }
  if (value is String && value.trim().isNotEmpty) {
    return DateTime.tryParse(value.trim());
  }
  return null;
}

List<String> _stringList(dynamic value) {
  if (value is! List) {
    return const <String>[];
  }
  return value
      .where((dynamic e) => e != null)
      .map((dynamic e) => e.toString().trim())
      .where((e) => e.isNotEmpty)
      .toList(growable: false);
}

int _issueCount(dynamic value) => value is List ? value.length : 0;

int _violationCount(dynamic value) {
  if (value is! List) {
    return 0;
  }
  var count = 0;
  for (final dynamic item in value) {
    if (item is Map) {
      final severity = item['severity']?.toString().toLowerCase().trim();
      if (severity == 'high' || severity == 'critical') {
        count++;
      }
    }
  }
  return count;
}

String _displayId({
  required DateTime? inspectedAt,
  required String? id,
  required int index,
}) {
  final String datePart;
  if (inspectedAt == null) {
    datePart = '00000000';
  } else {
    final local = inspectedAt.toLocal();
    datePart =
        '${local.year.toString().padLeft(4, '0')}'
        '${local.month.toString().padLeft(2, '0')}'
        '${local.day.toString().padLeft(2, '0')}';
  }

  final String suffix;
  if (id != null && id.trim().isNotEmpty) {
    final clean = id.replaceAll('-', '');
    suffix = clean.length >= 4
        ? clean.substring(clean.length - 4).toUpperCase()
        : clean.toUpperCase().padLeft(4, '0');
  } else {
    suffix = index.toString().padLeft(4, '0');
  }

  return 'VRQ-$datePart-$suffix';
}

String _timestampLabel(DateTime? value) {
  if (value == null) {
    return '—';
  }
  final local = value.toLocal();
  final y = local.year.toString().padLeft(4, '0');
  final mo = local.month.toString().padLeft(2, '0');
  final d = local.day.toString().padLeft(2, '0');
  final h = local.hour.toString().padLeft(2, '0');
  final mi = local.minute.toString().padLeft(2, '0');
  return '$y-$mo-$d $h:$mi';
}
