import 'package:flutter/foundation.dart';

import 'package:flutter_application_1/features/inspections/inspection_record.dart';

/// A stable, URL-safe product key DERIVED from a product name.
///
/// Normalizes the name (trim + lower-case) then hashes it with a bounded
/// polynomial rolling hash (mod 2^32) so every intermediate value stays inside
/// the 53-bit safe-integer range (same technique as `ReportReference`), giving
/// a deterministic `p-<8 hex>` key. The same name — regardless of surrounding
/// whitespace or case — always resolves to the same key, so `/products/:id`
/// round-trips.
String productKeyFor(String productName) {
  final normalized = productName.trim().toLowerCase();
  var hash = 0;
  for (final unit in normalized.codeUnits) {
    hash = (hash * 31 + unit) % 0x100000000;
  }
  return 'p-${hash.toRadixString(16).padLeft(8, '0')}';
}

/// A DERIVED product: a group of inspections sharing a normalized product name.
///
/// VERIQOO stores no backend product entity (D8); this is synthesized by
/// grouping inspections, so the UI must label the association DERIVED.
@immutable
class ProductSummary {
  const ProductSummary({
    required this.key,
    required this.productName,
    required this.inspectionCount,
    required this.lastInspectedAt,
    required this.latestScore,
    required this.bestScore,
    required this.inspections,
  });

  /// Stable `p-<8 hex>` key (see [productKeyFor]).
  final String key;

  /// Display name taken from the group's newest inspection.
  final String productName;

  /// Number of inspections in the group.
  final int inspectionCount;

  /// Timestamp of the newest inspection, or null when all are undated.
  final DateTime? lastInspectedAt;

  /// Score of the newest inspection.
  final int latestScore;

  /// Highest score across the group.
  final int bestScore;

  /// Member inspections, newest-first.
  final List<InspectionRecord> inspections;
}

/// Groups [records] by [productKeyFor], newest-first within each group, with
/// the groups themselves ordered by [ProductSummary.lastInspectedAt] descending
/// (undated groups last). Pure and order-deterministic.
List<ProductSummary> deriveProducts(List<InspectionRecord> records) {
  final orderedKeys = <String>[];
  final buckets = <String, List<InspectionRecord>>{};

  for (final record in records) {
    final key = productKeyFor(record.productName);
    (buckets[key] ??= <InspectionRecord>[]).add(record);
    if (!orderedKeys.contains(key)) {
      orderedKeys.add(key);
    }
  }

  final summaries = <ProductSummary>[];
  for (final key in orderedKeys) {
    final members = _sortedNewestFirst(buckets[key]!);
    final newest = members.first;
    final best = members
        .map((r) => r.score)
        .fold<int>(0, (max, score) => score > max ? score : max);
    summaries.add(
      ProductSummary(
        key: key,
        productName: newest.productName,
        inspectionCount: members.length,
        lastInspectedAt: newest.inspectedAt,
        latestScore: newest.score,
        bestScore: best,
        inspections: List<InspectionRecord>.unmodifiable(members),
      ),
    );
  }

  // Stable-sort the groups by recency (undated last), keeping first-appearance
  // order on ties.
  final decorated = summaries.indexed.toList();
  decorated.sort((a, b) {
    final primary = _compareDateDesc(a.$2.lastInspectedAt, b.$2.lastInspectedAt);
    return primary != 0 ? primary : a.$1.compareTo(b.$1);
  });
  return List<ProductSummary>.unmodifiable(decorated.map((entry) => entry.$2));
}

/// Finds the product with [key], or null when absent.
ProductSummary? findProduct(List<ProductSummary> products, String key) {
  for (final product in products) {
    if (product.key == key) {
      return product;
    }
  }
  return null;
}

/// Returns [records] sorted newest-first (undated last), stable on ties.
List<InspectionRecord> _sortedNewestFirst(List<InspectionRecord> records) {
  final decorated = records.indexed.toList();
  decorated.sort((a, b) {
    final primary = _compareDateDesc(a.$2.inspectedAt, b.$2.inspectedAt);
    return primary != 0 ? primary : a.$1.compareTo(b.$1);
  });
  return decorated.map((entry) => entry.$2).toList(growable: false);
}

/// Descending date order (later first) with nulls LAST.
int _compareDateDesc(DateTime? a, DateTime? b) {
  if (a == null && b == null) {
    return 0;
  }
  if (a == null) {
    return 1;
  }
  if (b == null) {
    return -1;
  }
  return b.compareTo(a);
}
