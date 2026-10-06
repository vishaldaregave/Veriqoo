# VERIQOO user_app HOME rebuild — real Supabase data behind an editorial command center

Phase 4 replaces the user_app HOME placeholder with an editorial, data-driven command center and introduces an injectable `InspectionsRepository` seam (record model + Riverpod providers) that reads the signed-in client's saved inspections through `Supabase.instance.client`. The data layer maps exactly the columns `SupabaseService.saveInspectionReport` writes to the `inspections` table (`product_name`, `inspected_at`, `is_compliant`, `missing_information`, `possible_issues`), derives `score`/`status` client-side because the table stores neither, and degrades to safe defaults rather than throwing into the UI. The existing Phase 2 `historyProvider` was rewired to delegate to the new repository instead of duplicating data access, and the router / scan branch / auth guard were left untouched. The home surface composes the wordmark top bar, time-of-day greeting, Display hero, inverse/secondary action pair, the VerificationScan-over-ProductOutline motif, a slim mono metrics line, and a recent-inspections ledger with an intelligent empty state, all reduced-motion aware.

Watch for: Home deep-links recent rows with the raw row id while the rewired `historyProvider` hands `history_screen.dart` the human `displayId` — the same detail route receives two id formats (confirmed, non-blocking today because the detail screen only echoes the id). Per-user scoping relies entirely on server-side RLS since the table has no `user_id` column and the repository applies no client filter (confirmed). VIEW HISTORY renders as the `secondary` outline variant where the brief literally said "ghost" (confirmed, design-intent check). `flutter test` / `flutter build web` were deferred, so the hermetic widget tests are unexecuted (confirmed, within the Dart-only bar).

**Verdict**: APPROVED

## High-level view

The data layer is genuinely Supabase-backed and matches the real write schema. `SupabaseInspectionsRepository` reads the `inspections` table through a lazily-resolved client, the record mapper reads every column defensively, and `score`/`status` are derived rather than selected because the table never stores them — real data, not a mock.

Degradation is handled at every layer: a missing `inspected_at` falls back from an ordered query to an unordered one, a missing/failing flagged count collapses to a `—` placeholder instead of a wrong zero, malformed rows resolve to safe defaults, and genuine fetch failures surface as an inline error state with retry while the hero, actions, and top bar keep rendering. Nothing throws into widget build.

Per-user data scoping is the one posture worth confirming: the table carries no `user_id`, so the repository deliberately applies no client-side filter and leans entirely on Supabase row-level security to return only the signed-in user's rows. That is the right client behavior for this schema, but it is only as correct as the server-side RLS policy.

The `historyProvider` rewire is clean (one shared repository, no duplicate access), but it projects `InspectionSummary.id = displayId`, so `history_screen.dart` deep-links `/history/<VRQ-...>` while Home deep-links `/history/<raw id>`. The detail screen is still a placeholder that only prints the id, so nothing breaks now, but Phase 7 must pick one canonical identifier before wiring a real detail lookup.

Design-system discipline is tight: barrel-only imports, tokens via the theme extension, named components/painters/motif, the `VeriqooIcons` facade with no lucide or google_fonts, and `textTertiary` kept off body copy (its one use is the connection meta-label). The hero reads `VERIFY / WHAT'S ON / THE LABEL.` with a combined a11y sentence, and all motion resolves to a static end-state under reduced motion. The only fidelity nuance is VIEW HISTORY using the `secondary` outline variant versus the brief's "ghost" wording.

The verification bar holds on the recorded evidence: `dart pub get` succeeded with no pubspec change and `dart analyze` reports zero issues. The widget tests are hermetic (a `FakeInspectionsRepository` plus `currentUserProvider` / `networkStatusProvider` overrides, never `Supabase.instance`) and cover loading, empty, populated, error, greeting, and the two primary nav actions; `flutter test` / `flutter build web` are explicitly deferred.

<details>
<summary>Issues (6)</summary>

1. **Deep-link id split** — Home navigates `/history/<raw id>` (`visible[i].id`) but `history_providers.dart` sets `InspectionSummary.id = displayId`, so `history_screen.dart` navigates `/history/<VRQ-...>`. Harmless now (the detail screen only echoes the id); Phase 7 must choose one canonical id before adding a real lookup. Non-blocking.
2. **RLS-only per-user scoping** — the repository applies no client-side user filter (correct, since the `inspections` table has no `user_id`), so "the signed-in user's inspections" holds only if RLS is configured on the table. Confirm the server-side policy. Non-blocking.
3. **History rows show real score with a hardcoded `verified` status** — now that `historyProvider` returns real rows, the Phase 2 `history_screen.dart` placeholder (not modified by Phase 4) renders every row as `VeriqooStatusKind.verified` because `InspectionSummary` drops `status`. Phase 7's migration to `InspectionRecord` resolves it. Non-blocking, attributed to the pre-existing placeholder.
4. **VIEW HISTORY variant vs brief** — the brief says "VIEW HISTORY (ghost)" but `home_actions.dart` uses `VeriqooButtonVariant.secondary` (hairline outline); true `ghost` is reserved for the inline "View all". Confirm which the design owner intended. Non-blocking.
5. **Inline loading copy** — `VeriqooLoading(message: 'Loading')` in `home_screen.dart` uses a literal instead of a `HomeStrings` constant, a small gap against the centralized-copy goal. Non-blocking.
6. **Test gaps** — the recent-row tap → `/history/:id`, the offline/unknown connection indicator, and the reduced-motion path are not exercised at the widget level; `flutter test` / `flutter build web` are deferred so no test actually ran. Non-blocking within the Dart-only bar.

</details>

<details>
<summary>Details</summary>

### Real inspections data against the live write schema

`SupabaseInspectionsRepository` reads the `inspections` table and maps each row through `InspectionRecord.fromMap`. Cross-checking against `shared_core/lib/services/supabase_service.dart` — the acceptance anchor — the write path inserts `product_name`, `is_compliant`, `missing_information`, `possible_issues` (a list of `ComplianceIssue.toJson()` maps, each carrying a `severity` string), and `inspected_at`, with no `user_id` and no `score`. Every column the record reads exists on that write path, so the mapping is real rather than aspirational, and `violationCount` keys off `severity in {high, critical}` — a field that genuinely exists in the serialized issue (confirmed in `compliance_analysis.dart`).

`score` and `status` are derived, not selected: `deriveScore` returns 100 for a compliant row and otherwise deducts 15 per issue and 10 per missing declaration, floored at 0 and capped at 95 so a non-compliant row never ties a compliant one; `deriveStatus` resolves verified → violation → flag → missing. Confidence: confirmed.

The three providers (`inspectionsRepositoryProvider`, `recentInspectionsProvider`, `inspectionSummaryProvider`) form the Phase 7 seam. The repository constructor never touches `Supabase.instance`; the client is resolved lazily inside each async call, so an uninitialized Supabase surfaces as an awaited error rather than a build-time crash. Confidence: confirmed.

### Graceful degradation when columns go missing

The failure handling is asymmetric by design and worth stating precisely. `recentInspections` first orders by `inspected_at`; if that column is absent the `PostgrestException` is caught and the query retries unordered, so a schema without the timestamp still returns rows. `summaryCounts` lets the `total` count propagate on failure (it becomes the provider's error state) but wraps the flagged `is_compliant` count in a catch that collapses to `null`, which the metrics line renders as `—` rather than a misleading `0`. `InspectionRecord.fromMap` coerces every field — wrong types, nulls, blank strings — to safe defaults, so a malformed row yields `Unknown product`, a `—` timestamp, and empty lists instead of throwing.

Because the repository methods are `async`, an uninitialized Supabase or a network failure surfaces as an awaited error that Riverpod turns into `AsyncError`; `home_screen.dart` maps that to `VeriqooErrorState` (with retry) for the recent list and to `HomeMetrics(counts: null)` for the metrics, while the hero, actions, and top bar always render. The two providers degrade independently, so a metrics failure does not blank the recent list and vice versa. Confidence: confirmed.

### Per-user scoping leans entirely on RLS

Because the `inspections` table has no `user_id`, the repository intentionally omits any `.eq('user_id', ...)` filter and documents that rows are scoped by Supabase row-level security. That is the correct client-side decision for this schema — adding a filter on a non-existent column would throw — but it means the acceptance phrase "the signed-in user's recent inspections" is only satisfied if an RLS policy actually restricts the table per user. If RLS is absent or permissive, `recentInspections` and `summaryCounts` would read across all users' rows. This is not a code defect in Phase 4; it is a server-side dependency that should be confirmed, and the repository is the right single place to add a guarded filter if a `user_id` column is introduced later. Confidence: confirmed (no client filter; schema has no `user_id`).

### historyProvider rewire and the deep-link id split

The rewire is clean: `historyProvider` now delegates to `inspectionsRepositoryProvider.recentInspections(limit: 50)` and maps down to the slim `InspectionSummary`, so Home and History read through one repository with no duplicated Supabase access, and the `InspectionSummary` type plus the `historyProvider` symbol are preserved so `history_screen.dart` compiles unchanged.

The side effect is an identifier mismatch. `HomeRecentList` navigates with the raw row id — `context.go(AppRoutes.historyDetail(visible[i].id))` — while displaying `displayId` on the card, which is the correct split. But the projection sets `InspectionSummary.id = r.displayId`, so `history_screen.dart` navigates `context.go(AppRoutes.historyDetail(record.id))` with the `VRQ-...` string. The same `/history/:id` route therefore receives a raw id from Home and a formatted id from History. `HistoryDetailScreen` is still a placeholder that only renders the id as a section subtitle, so neither path breaks today — but when Phase 7 implements a real detail lookup it must settle on one canonical identifier, and the raw row id (what `InspectionRecord.id` carries) is the natural key. Confidence: confirmed.

### Design-system discipline and the ghost/secondary nuance

Verified by search, not just inspection: no `lucide` or `google_fonts` import exists anywhere in `apps/user_app`; `Supabase.instance` appears in Phase 4 code only inside the repository's lazy `_client` getter and the guarded `currentUserProvider`, with every other hit confined to pre-existing auth/settings screens; and `textTertiary` in the home feature appears once, on the connection meta-label, never on body copy (the hero supporting line and greeting use `textSecondary`).

Reduced motion is handled at each moving part: the entrance controller is pinned to its end value (`VeriqooMotion.reduceMotion` → `value = 1`), the metrics count-up uses `Duration.zero`, and the signature-scan / empty-state motifs are `BackgroundEffect`-based so they pause automatically. The signature band is wrapped in `IgnorePointer` at reduced opacity and sits beneath the hero column in the stack, matching the "below foreground content" requirement.

The one fidelity nuance: the brief says "VIEW HISTORY (ghost)" but `home_actions.dart` builds it with `VeriqooButtonVariant.secondary` (hairline outline), reserving the true text-only `ghost` for the inline "View all" action. Given the component definitions (`primary` = inverse fill, `secondary` = outline, `ghost` = text only), a full-width text-only secondary CTA under a filled primary would be a weak affordance, so the outline is the defensible reading — but it is a literal deviation from the brief's wording and worth a design-owner confirmation. SCAN PRODUCT correctly uses the default `primary` (inverse). Confidence: confirmed.

### Test coverage

The suite is hermetic by construction: `FakeInspectionsRepository` drives loading (futures that never complete), error (futures that throw), and populated/empty states, and `pumpHome` overrides `inspectionsRepositoryProvider`, `currentUserProvider`, and `networkStatusProvider` so nothing contacts `Supabase.instance`. The widget tests assert the hero and both actions survive every data state, the loading motif and error state appear, the greeting shows the name and degrades to the bare prefix, and SCAN PRODUCT / VIEW HISTORY route to their targets; the logic tests cover `deriveScore`, `deriveStatus`, the greeting helpers, and `fromMap` including wrongly-typed columns. Because the background motion loops forever, the tests pump fixed durations instead of `pumpAndSettle`.

Not tested: the recent-row tap through to `/history/:id` (the harness defines `kHistoryDetailRouteKey` but no test taps a card), the offline and unknown connection-indicator rendering (the harness always passes `online`), and the reduced-motion branch (no `MediaQuery` with `disableAnimations`). And since `flutter test` was deferred, none of these actually executed — the pass is expected from construction but unverified. Confidence: confirmed.

### Write scope, evidence, and the git limitation

`git status` shows no commits were made and that the entire monorepo (`apps/`, `packages/`) is untracked, which means git cannot mechanically isolate what Phase 4 changed — there is no committed baseline for these directories. Scope was therefore verified by reading: `supabase_service.dart` and `compliance_analysis.dart` are the clean canonical write-path files the new data layer reads from, consistent with read-only use of `shared_core`, and the Phase 4 file set lives entirely under `apps/user_app/`. The recorded verification note reports `dart pub get` success (no pubspec change) and `dart analyze` with "No issues found!", and defers `flutter test` / `flutter build web` as required by the Dart-only bar. Per the review constraints these commands were not re-run. Confidence: confirmed (reading + recorded evidence), with the git-isolation limitation noted.

</details>

<details>
<summary>File map</summary>

Data layer (the Phase 7 seam):
- `apps/user_app/lib/features/inspections/inspection_record.dart` — immutable UI record + defensive `fromMap` + `deriveScore`/`deriveStatus`.
- `apps/user_app/lib/features/inspections/inspections_repository.dart` — injectable repo over the `inspections` table with graceful degradation.
- `apps/user_app/lib/features/inspections/inspections_providers.dart` — repository + recent + summary providers.

Home copy + user:
- `apps/user_app/lib/features/home/home_strings.dart` — centralized Home copy.
- `apps/user_app/lib/features/home/home_user.dart` — guarded `currentUserProvider` + pure greeting/name helpers.

Home widgets:
- `apps/user_app/lib/features/home/home_screen.dart` — real Home body (replaced placeholder); state orchestration + entrance motion.
- `apps/user_app/lib/features/home/widgets/home_top_bar.dart` — wordmark, connection indicator (shape + label), notifications/profile.
- `apps/user_app/lib/features/home/widgets/home_greeting.dart` — time-of-day greeting line.
- `apps/user_app/lib/features/home/widgets/home_hero.dart` — Display hero + supporting line.
- `apps/user_app/lib/features/home/widgets/home_actions.dart` — SCAN PRODUCT (primary) / VIEW HISTORY (secondary).
- `apps/user_app/lib/features/home/widgets/home_signature_scan.dart` — VerificationScan over ProductOutline, below content.
- `apps/user_app/lib/features/home/widgets/home_metrics.dart` — slim mono metrics line with `—` placeholders.
- `apps/user_app/lib/features/home/widgets/home_recent_list.dart` — VeriqooInspectionCard ledger rows → `/history/:id`.
- `apps/user_app/lib/features/home/widgets/home_recent_empty.dart` — intelligent empty state.

Modified:
- `apps/user_app/lib/features/history/history_providers.dart` — `historyProvider` rewired to delegate to the repository (id projected as `displayId`).

Tests:
- `apps/user_app/test/home/home_harness.dart` — fake repo + provider overrides + minimal router.
- `apps/user_app/test/home/home_screen_test.dart` — loading/empty/populated/error/greeting/nav.
- `apps/user_app/test/home/home_logic_test.dart` — derive/greeting/`fromMap` unit tests.

Reference (read-only, not changed by Phase 4):
- `packages/shared_core/lib/services/supabase_service.dart` — the write-schema anchor.
- `apps/user_app/lib/app/router.dart`, `apps/user_app/lib/app/routes.dart` — scan branch + auth guard + `/history/:id` route, untouched.

Full change set is uncommitted working-tree state under `apps/user_app/`; the whole monorepo is untracked, so there is no `git diff` baseline to point to.

</details>
