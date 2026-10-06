import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:flutter_application_1/features/inspections/inspection_detail.dart';
import 'package:flutter_application_1/features/inspections/inspection_record.dart';

/// Summary counts for the Home metrics line.
///
/// [flagged] is nullable: when the `is_compliant` column (or its count query)
/// is unavailable the UI renders a `'—'` placeholder instead of a wrong zero.
class InspectionSummaryCounts {
  const InspectionSummaryCounts({required this.total, this.flagged});

  /// Total inspections readable by the signed-in client.
  final int total;

  /// Non-compliant (flagged) count, or null when unavailable.
  final int? flagged;
}

/// Read seam over the saved `inspections` table.
///
/// This is the reusable boundary the History experience extends. Every screen
/// reads the table THROUGH this interface (never `Supabase.instance` directly),
/// so the whole feature is fake-able in hermetic tests. The two implementers
/// are [SupabaseInspectionsRepository] (production) and the test
/// `FakeInspectionsRepository`; adding a method here means updating both.
abstract interface class InspectionsRepository {
  /// The most-recent [limit] inspections, newest first.
  Future<List<InspectionRecord>> recentInspections({int limit = 5});

  /// Aggregate counts for the metrics line.
  Future<InspectionSummaryCounts> summaryCounts();

  /// A newest-first PAGE of inspections for the ledger's default view, drawn
  /// via a postgrest `.range(offset, offset + limit - 1)` window.
  Future<List<InspectionRecord>> pagedInspections({int offset = 0, int limit = 20});

  /// A bounded newest-first CORPUS used by search and product derivation, where
  /// client-side filtering/grouping needs the whole (RLS-scoped) set at once.
  Future<List<InspectionRecord>> allInspections({int limit = 200});

  /// Fetches a single inspection by its raw row [id], fully reconstructed for
  /// the read-only detail view, or null when the row is absent / the table has
  /// no readable `id` column.
  Future<InspectionDetail?> inspectionById(String id);
}

/// Supabase-backed [InspectionsRepository].
///
/// ## Scoping
/// Rows are scoped by Supabase ROW-LEVEL SECURITY, not by an explicit filter:
/// the `inspections` table (see `SupabaseService.saveInspectionReport`) writes
/// no `user_id` column, so adding `.eq('user_id', ...)` would throw. When a
/// later schema adds `user_id`, add a guarded filter here — this class is the
/// single place that reads the table.
///
/// ## Derived fields
/// The table stores neither `score` nor `status`; both are derived in
/// [InspectionRecord] from the stored compliance signals. Never `select`
/// those columns.
///
/// ## Deferred client access
/// The constructor NEVER touches `Supabase.instance`. The client is resolved
/// lazily inside each async method (via [_client]), so an uninitialized
/// Supabase surfaces as an awaited error the provider turns into an error
/// state — never an exception thrown during widget build.
class SupabaseInspectionsRepository implements InspectionsRepository {
  SupabaseInspectionsRepository({SupabaseClient? client}) : _injected = client;

  /// The inspections table name (matches `SupabaseService`).
  static const String table = 'inspections';

  final SupabaseClient? _injected;

  SupabaseClient get _client => _injected ?? Supabase.instance.client;

  @override
  Future<List<InspectionRecord>> recentInspections({int limit = 5}) async {
    List<Map<String, dynamic>> rows;
    try {
      rows = await _client
          .from(table)
          .select()
          .order('inspected_at', ascending: false)
          .limit(limit);
    } on PostgrestException {
      // `inspected_at` not present on this schema — fall back to unordered.
      rows = await _client.from(table).select().limit(limit);
    }

    return rows.indexed
        .map((entry) => InspectionRecord.fromMap(entry.$2, index: entry.$1))
        .toList(growable: false);
  }

  @override
  Future<InspectionSummaryCounts> summaryCounts() async {
    // A failure of the total propagates (becomes the provider's error state).
    final total = await _client.from(table).count(CountOption.exact);

    // The flagged count degrades to null if `is_compliant` is unavailable.
    int? flagged;
    try {
      flagged = await _client
          .from(table)
          .count(CountOption.exact)
          .eq('is_compliant', false);
    } catch (_) {
      flagged = null;
    }

    return InspectionSummaryCounts(total: total, flagged: flagged);
  }

  @override
  Future<List<InspectionRecord>> pagedInspections({
    int offset = 0,
    int limit = 20,
  }) async {
    List<Map<String, dynamic>> rows;
    try {
      rows = await _client
          .from(table)
          .select()
          .order('inspected_at', ascending: false)
          .range(offset, offset + limit - 1);
    } on PostgrestException {
      // `inspected_at` not present on this schema — fall back to unordered.
      rows = await _client
          .from(table)
          .select()
          .range(offset, offset + limit - 1);
    }

    return rows.indexed
        .map(
          (entry) =>
              InspectionRecord.fromMap(entry.$2, index: offset + entry.$1),
        )
        .toList(growable: false);
  }

  @override
  Future<List<InspectionRecord>> allInspections({int limit = 200}) async {
    List<Map<String, dynamic>> rows;
    try {
      rows = await _client
          .from(table)
          .select()
          .order('inspected_at', ascending: false)
          .limit(limit);
    } on PostgrestException {
      rows = await _client.from(table).select().limit(limit);
    }

    return rows.indexed
        .map((entry) => InspectionRecord.fromMap(entry.$2, index: entry.$1))
        .toList(growable: false);
  }

  @override
  Future<InspectionDetail?> inspectionById(String id) async {
    try {
      final rows = await _client.from(table).select().eq('id', id).limit(1);
      if (rows.isEmpty) {
        return null;
      }
      return InspectionDetail.fromMap(rows.first);
    } on PostgrestException {
      // Missing `id` column or no readable match — treat as not-found. Other
      // failures (network / uninitialized Supabase) propagate to the provider.
      return null;
    }
  }
}
