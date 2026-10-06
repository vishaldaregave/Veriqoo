import 'package:flutter/foundation.dart';
import 'package:shared_core/design_system/design_system.dart' show VeriqooStatusKind;

import 'package:flutter_application_1/features/inspections/inspection_record.dart';

/// Status facets a user can filter the ledger by. [all] disables the facet;
/// the rest map 1:1 onto [VeriqooStatusKind].
enum InspectionStatusFilter { all, verified, flag, missing, violation }

/// Ordering options for the ledger / search results.
enum InspectionSortOrder { newest, oldest, scoreHigh, scoreLow }

/// An immutable, PURE description of a ledger query: free-text search, a status
/// facet, and a sort order.
///
/// [matches] and [apply] are pure functions over [InspectionRecord]s so the
/// whole query surface is unit-testable without Supabase or widgets. Search is
/// deliberately client-side (D5): it spans the DERIVED display id, raw id,
/// timestamp label, product name, and the missing-declaration text — none of
/// which is server-queryable — so the server supplies the newest-first corpus
/// and this type filters/sorts it.
@immutable
class InspectionQuery {
  const InspectionQuery({
    this.text = '',
    this.status = InspectionStatusFilter.all,
    this.sort = InspectionSortOrder.newest,
  });

  /// Free-text query (case-insensitive `contains` across several fields).
  final String text;

  /// Status facet.
  final InspectionStatusFilter status;

  /// Sort order applied after filtering.
  final InspectionSortOrder sort;

  InspectionQuery copyWith({
    String? text,
    InspectionStatusFilter? status,
    InspectionSortOrder? sort,
  }) {
    return InspectionQuery(
      text: text ?? this.text,
      status: status ?? this.status,
      sort: sort ?? this.sort,
    );
  }

  /// True when the query differs from the default (no text, all statuses,
  /// newest-first) — the ledger uses this to switch from paged to load-all.
  bool get isActive =>
      text.trim().isNotEmpty ||
      status != InspectionStatusFilter.all ||
      sort != InspectionSortOrder.newest;

  /// Whether [record] satisfies the status facet AND the free-text query.
  bool matches(InspectionRecord record) {
    if (!_statusMatches(record.status)) {
      return false;
    }
    final needle = text.trim().toLowerCase();
    if (needle.isEmpty) {
      return true;
    }
    final haystack = <String>[
      record.productName,
      record.displayId,
      record.id,
      record.timestampLabel,
      ...record.missingInformation,
    ];
    for (final field in haystack) {
      if (field.toLowerCase().contains(needle)) {
        return true;
      }
    }
    return false;
  }

  /// Filters [records] by [matches] then STABLE-sorts the result by [sort].
  /// The input list is never mutated; the returned list is unmodifiable.
  List<InspectionRecord> apply(List<InspectionRecord> records) {
    final filtered = records.where(matches).toList();
    // Decorate with the original index so equal elements keep their incoming
    // order (Dart's List.sort is not guaranteed stable).
    final decorated = filtered.indexed.toList();
    decorated.sort((a, b) {
      final primary = _compare(a.$2, b.$2);
      return primary != 0 ? primary : a.$1.compareTo(b.$1);
    });
    return List<InspectionRecord>.unmodifiable(
      decorated.map((entry) => entry.$2),
    );
  }

  bool _statusMatches(VeriqooStatusKind kind) {
    switch (status) {
      case InspectionStatusFilter.all:
        return true;
      case InspectionStatusFilter.verified:
        return kind == VeriqooStatusKind.verified;
      case InspectionStatusFilter.flag:
        return kind == VeriqooStatusKind.flag;
      case InspectionStatusFilter.missing:
        return kind == VeriqooStatusKind.missing;
      case InspectionStatusFilter.violation:
        return kind == VeriqooStatusKind.violation;
    }
  }

  int _compare(InspectionRecord a, InspectionRecord b) {
    switch (sort) {
      case InspectionSortOrder.newest:
        return _compareDateDesc(a.inspectedAt, b.inspectedAt);
      case InspectionSortOrder.oldest:
        return _compareDateAsc(a.inspectedAt, b.inspectedAt);
      case InspectionSortOrder.scoreHigh:
        return b.score.compareTo(a.score);
      case InspectionSortOrder.scoreLow:
        return a.score.compareTo(b.score);
    }
  }
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

/// Ascending date order (earlier first) with nulls LAST.
int _compareDateAsc(DateTime? a, DateTime? b) {
  if (a == null && b == null) {
    return 0;
  }
  if (a == null) {
    return 1;
  }
  if (b == null) {
    return -1;
  }
  return a.compareTo(b);
}
