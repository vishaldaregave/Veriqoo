import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutter_application_1/features/inspections/inspection_detail.dart';
import 'package:flutter_application_1/features/inspections/inspection_record.dart';
import 'package:flutter_application_1/features/inspections/inspections_repository.dart';

/// The inspections read seam. Built WITHOUT touching `Supabase.instance`, so
/// the provider graph is safe to construct in hermetic widget tests; the
/// client is resolved lazily inside each repository call.
///
/// Override this in tests with a fake to drive Home's data states.
final inspectionsRepositoryProvider = Provider<InspectionsRepository>(
  (ref) => SupabaseInspectionsRepository(),
);

/// The most-recent inspections for the Home recent list. `autoDispose` so it
/// refetches when Home is revisited.
final recentInspectionsProvider =
    FutureProvider.autoDispose<List<InspectionRecord>>((ref) {
      return ref.watch(inspectionsRepositoryProvider).recentInspections(
        limit: 5,
      );
    });

/// Aggregate counts for the Home metrics line.
final inspectionSummaryProvider =
    FutureProvider.autoDispose<InspectionSummaryCounts>((ref) {
      return ref.watch(inspectionsRepositoryProvider).summaryCounts();
    });

/// The bounded newest-first corpus used by Search and product derivation.
/// `autoDispose` so it refetches when the surface is revisited.
final allInspectionsProvider =
    FutureProvider.autoDispose<List<InspectionRecord>>((ref) {
      return ref.watch(inspectionsRepositoryProvider).allInspections();
    });

/// A single reconstructed inspection by raw row id, for the read-only detail
/// screen. Resolves null when the row is absent (→ not-found state).
final inspectionDetailProvider =
    FutureProvider.autoDispose.family<InspectionDetail?, String>((ref, id) {
      return ref.watch(inspectionsRepositoryProvider).inspectionById(id);
    });
