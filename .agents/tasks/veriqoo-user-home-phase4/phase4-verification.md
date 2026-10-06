# PHASE 4 — User-app HOME rebuild — Verification note

Main workspace, NO worktree, NO commits. Write scope: `apps/user_app/**` only.
`shared_core` and `admin_web` were read-only / untouched.

## Acceptance bar (what I ran)

Toolchain constraint: `flutter *` is denied; only `dart` was used.

### `dart pub get` (cwd `apps/user_app`) — SUCCESS

```
Resolving dependencies...
Downloading packages...
Got dependencies!
39 packages have newer versions incompatible with dependency constraints.
```

No pubspec change was required (all needed deps — `flutter_riverpod`,
`go_router`, `supabase_flutter` — were already present). No `dart pub add` was
run.

### `dart analyze` (cwd `apps/user_app`) — 0 ERRORS

```
Analyzing user_app...
No issues found!
```

Baseline before changes was also `No issues found!`, so the clean bar is held.

## Deferred verification (NOT run — `flutter` is denied)

Run these where `flutter` is permitted:

```
cd apps/user_app && flutter test        # runs the kept widget + logic tests (home_* + existing auth/shell suites)
cd apps/user_app && flutter build web   # build smoke check
```

The widget tests are hermetic: they use a `FakeInspectionsRepository` and
override `currentUserProvider` / `networkStatusProvider`, so they never touch
`Supabase.instance`. Background motion loops forever, so the tests pump fixed
durations (never `pumpAndSettle`).

## Files created

Data layer (the Phase 7 seam):
- `lib/features/inspections/inspection_record.dart`
- `lib/features/inspections/inspections_repository.dart`
- `lib/features/inspections/inspections_providers.dart`

Home copy + user:
- `lib/features/home/home_strings.dart`
- `lib/features/home/home_user.dart`

Home section widgets:
- `lib/features/home/widgets/home_top_bar.dart`
- `lib/features/home/widgets/home_greeting.dart`
- `lib/features/home/widgets/home_hero.dart`
- `lib/features/home/widgets/home_actions.dart`
- `lib/features/home/widgets/home_signature_scan.dart`
- `lib/features/home/widgets/home_metrics.dart`
- `lib/features/home/widgets/home_recent_list.dart`
- `lib/features/home/widgets/home_recent_empty.dart`

Tests:
- `test/home/home_harness.dart`
- `test/home/home_screen_test.dart`
- `test/home/home_logic_test.dart`

## Files modified

- `lib/features/home/home_screen.dart` — placeholder body replaced with the real
  Home (class name + `const HomeScreen({super.key})` kept so `router.dart` is
  untouched). The router, scan branch, and auth guard were NOT changed.
- `lib/features/history/history_providers.dart` — `historyProvider` rewired to
  delegate to `inspectionsRepositoryProvider` (the `InspectionSummary` type and
  the `historyProvider` symbol are kept so `history_screen.dart` compiles
  unchanged).

## Inspections repository / provider API (handed to Phase 7)

Pinned data facts (from `shared_core/.../supabase_service.dart`): table is
`inspections`; it writes NO `user_id` and NO `score` column.

```dart
// inspection_record.dart
class InspectionRecord {               // immutable, UI-ready
  final String id;                     // raw row id, or synthesized `row-<index>`
  final String displayId;              // VRQ-YYYYMMDD-####
  final String productName;            // '' -> 'Unknown product'
  final DateTime? inspectedAt;
  final bool? isCompliant;
  final List<String> missingInformation;
  final int issueCount;
  final int violationCount;            // severity in {high, critical}
  final int score;                     // DERIVED, never stored
  final VeriqooStatusKind status;      // DERIVED, never stored
  final String timestampLabel;         // 'YYYY-MM-DD HH:MM' or '—'
  factory InspectionRecord.fromMap(Map<String, dynamic> row, {int index = 0});
}
int deriveScore({required bool? isCompliant, required int issueCount, required int missingCount});
VeriqooStatusKind deriveStatus({required bool? isCompliant, required int issueCount, required int violationCount, required int missingCount});

// inspections_repository.dart
class InspectionSummaryCounts { final int total; final int? flagged; }
abstract interface class InspectionsRepository {
  Future<List<InspectionRecord>> recentInspections({int limit = 5});
  Future<InspectionSummaryCounts> summaryCounts();
}
class SupabaseInspectionsRepository implements InspectionsRepository {
  SupabaseInspectionsRepository({SupabaseClient? client}); // ctor never touches Supabase.instance
  static const String table = 'inspections';
}

// inspections_providers.dart
final inspectionsRepositoryProvider = Provider<InspectionsRepository>(...);
final recentInspectionsProvider = FutureProvider.autoDispose<List<InspectionRecord>>(...);
final inspectionSummaryProvider = FutureProvider.autoDispose<InspectionSummaryCounts>(...);

// history_providers.dart (rewired)
final historyProvider = FutureProvider.autoDispose<List<InspectionSummary>>(...); // delegates to the repo
```

Phase 7 should extend `recentInspections` / add a paged `allInspections(...)` on
the same repository and migrate History onto `InspectionRecord` (retiring the
thin `InspectionSummary` projection).

## How Home degrades when the `inspections` table/columns differ

- No `user_id` column → NO explicit user filter; rows are scoped by Supabase
  RLS. If a later schema adds `user_id`, add a guarded `.eq('user_id', ...)` in
  `SupabaseInspectionsRepository` (the single place that reads the table).
- No `score` column → score is always derived (`deriveScore`); never selected.
- Missing `inspected_at` → the recent query catches `PostgrestException` and
  retries unordered (`select().limit()`).
- Missing/failed `is_compliant` flagged count → `flagged` is null → the metrics
  line renders `'—'` for FLAGGED while INSPECTED still shows.
- Any row with missing / wrongly-typed keys → `InspectionRecord.fromMap` returns
  safe defaults (`'Unknown product'`, null date → `'—'`, empty lists); the UI
  never throws.
- Genuine fetch failure (network, or `Supabase.instance` uninitialized in tests)
  → the repository methods are `async`, so the throw becomes an `AsyncError`;
  the recent section shows `VeriqooErrorState` (with retry) and the metrics
  degrade inline. The hero / actions / top bar always render. The greeting user
  lookup (`currentUserProvider`) is guarded (try/catch → null), so it never
  throws during build.
