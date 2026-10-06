import 'package:flutter_riverpod/legacy.dart';

import 'package:flutter_application_1/features/inspections/inspection_query.dart';

/// The active ledger query — free-text, status facet, and sort order — for the
/// History screen.
///
/// A plain [StateProvider] over the immutable [InspectionQuery] (mirrors
/// `themeModeProvider`). History reads the inspections corpus via
/// `allInspectionsProvider` and applies this query CLIENT-SIDE (D5), because
/// the searchable fields (derived display id, derived score/status, and issue
/// text buried in JSON) are not server-queryable.
final historyQueryProvider = StateProvider<InspectionQuery>(
  (ref) => const InspectionQuery(),
);
