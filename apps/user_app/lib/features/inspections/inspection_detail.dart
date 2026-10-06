import 'package:flutter/foundation.dart';
import 'package:shared_core/services/compliance_analysis.dart';

import 'package:flutter_application_1/features/inspections/inspection_record.dart';

/// A fully-reconstructed saved inspection: the ledger [record], the
/// [ComplianceAnalysis] rebuilt from the stored row, the captured [imageUrl]
/// (if any), and the raw [ocrText].
///
/// This is what the read-only inspection-detail screen renders. It is built
/// entirely from a stored `inspections` row — nothing is re-fetched or
/// re-analyzed — so the detail view can reuse the Phase 6 report widgets
/// (score dial, product-details panel, numbered findings) without re-saving.
@immutable
class InspectionDetail {
  const InspectionDetail({
    required this.record,
    required this.analysis,
    required this.imageUrl,
    required this.ocrText,
  });

  /// Ledger projection (id, display id, derived score/status, timestamp).
  final InspectionRecord record;

  /// Compliance analysis reconstructed from the row (see [fromMap]).
  final ComplianceAnalysis analysis;

  /// The single stored evidence image URL, or null when absent/blank.
  final String? imageUrl;

  /// Stored OCR text, or '' when absent.
  final String ocrText;

  /// Builds a detail from a raw `inspections` row.
  ///
  /// The analysis is reconstructed from `ai_report` (the camelCase
  /// `ComplianceAnalysis.toJson()` round-trip) when present, falling back to
  /// the flat snake_case columns otherwise (D4). Every field is read
  /// defensively so a sparse or wrongly-typed row degrades to safe defaults
  /// instead of throwing into the UI.
  factory InspectionDetail.fromMap(Map<String, dynamic> row, {int index = 0}) {
    return InspectionDetail(
      record: InspectionRecord.fromMap(row, index: index),
      analysis: _reconstructAnalysis(row),
      imageUrl: _nonBlankString(row['image_url']),
      ocrText: _stringOrEmpty(row['ocr_text']),
    );
  }
}

/// Rebuilds the [ComplianceAnalysis] from a stored row.
///
/// Prefers `ai_report` (a Map round-tripping the camelCase `toJson()`); on a
/// missing/wrongly-typed/undecodable `ai_report` it reconstructs from the flat
/// snake_case columns. Both paths are non-throwing.
ComplianceAnalysis _reconstructAnalysis(Map<String, dynamic> row) {
  final aiReport = row['ai_report'];
  if (aiReport is Map) {
    try {
      return ComplianceAnalysis.fromJson(Map<String, dynamic>.from(aiReport));
    } catch (_) {
      // Fall through to the flat-column reconstruction.
    }
  }
  return ComplianceAnalysis(
    productName: _stringOrEmpty(row['product_name']),
    mrp: _stringOrEmpty(row['mrp']),
    netQuantity: _stringOrEmpty(row['net_quantity']),
    manufacturer: _stringOrEmpty(row['manufacturer']),
    address: _stringOrEmpty(row['address']),
    packingDate: _stringOrEmpty(row['packing_date']),
    customerCare: _stringOrEmpty(row['customer_care']),
    missingInformation: _stringList(row['missing_information']),
    possibleIssues: _issues(row['possible_issues']),
  );
}

String _stringOrEmpty(dynamic value) => value is String ? value.trim() : '';

String? _nonBlankString(dynamic value) {
  if (value is String && value.trim().isNotEmpty) {
    return value.trim();
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

List<ComplianceIssue> _issues(dynamic value) {
  if (value is! List) {
    return const <ComplianceIssue>[];
  }
  final issues = <ComplianceIssue>[];
  for (final dynamic item in value) {
    if (item is Map) {
      try {
        issues.add(ComplianceIssue.fromJson(Map<String, dynamic>.from(item)));
      } catch (_) {
        // Skip a malformed issue entry; never throw to the UI.
      }
    }
  }
  return issues;
}
