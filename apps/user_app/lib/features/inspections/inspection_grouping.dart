import 'package:flutter/foundation.dart';

import 'package:flutter_application_1/features/history/history_strings.dart';
import 'package:flutter_application_1/features/inspections/inspection_record.dart';

/// A labelled run of inspections sharing a date bucket (TODAY / YESTERDAY /
/// an ISO date / UNDATED). Immutable and data-only.
@immutable
class InspectionDateGroup {
  const InspectionDateGroup({required this.label, required this.records});

  /// Group heading, e.g. `TODAY`, `YESTERDAY`, `2026-01-04`, or `UNDATED`.
  final String label;

  /// Records in this bucket, in the order they arrived (newest-first when the
  /// caller passes a newest-first list).
  final List<InspectionRecord> records;
}

/// Buckets [records] into date groups while PRESERVING their incoming order
/// (the caller supplies a newest-first list). Records dated today/yesterday
/// (in local time, relative to [now]) get the TODAY/YESTERDAY labels; older
/// records are labelled by their local ISO date; records with a null
/// `inspectedAt` collect into a trailing UNDATED group.
///
/// Pure: [now] is injectable so tests pin the TODAY/YESTERDAY boundary.
List<InspectionDateGroup> groupByDate(
  List<InspectionRecord> records, {
  DateTime? now,
}) {
  final today = _dateOnly(now ?? DateTime.now());
  final yesterday = today.subtract(const Duration(days: 1));

  final orderedLabels = <String>[];
  final buckets = <String, List<InspectionRecord>>{};

  for (final record in records) {
    final label = _labelFor(record.inspectedAt, today, yesterday);
    (buckets[label] ??= <InspectionRecord>[]).add(record);
    if (!orderedLabels.contains(label)) {
      orderedLabels.add(label);
    }
  }

  // Force the UNDATED bucket to the very end regardless of arrival order.
  if (orderedLabels.remove(HistoryStrings.groupUndated)) {
    orderedLabels.add(HistoryStrings.groupUndated);
  }

  return orderedLabels
      .map(
        (label) => InspectionDateGroup(
          label: label,
          records: List<InspectionRecord>.unmodifiable(buckets[label]!),
        ),
      )
      .toList(growable: false);
}

String _labelFor(DateTime? inspectedAt, DateTime today, DateTime yesterday) {
  if (inspectedAt == null) {
    return HistoryStrings.groupUndated;
  }
  final date = _dateOnly(inspectedAt);
  if (date == today) {
    return HistoryStrings.groupToday;
  }
  if (date == yesterday) {
    return HistoryStrings.groupYesterday;
  }
  return _isoDate(date);
}

/// Local midnight of [value], so same-day records compare equal.
DateTime _dateOnly(DateTime value) {
  final local = value.toLocal();
  return DateTime(local.year, local.month, local.day);
}

String _isoDate(DateTime date) {
  final y = date.year.toString().padLeft(4, '0');
  final mo = date.month.toString().padLeft(2, '0');
  final d = date.day.toString().padLeft(2, '0');
  return '$y-$mo-$d';
}
