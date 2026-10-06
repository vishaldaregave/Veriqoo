# Phase 11 — admin_web Monochrome Regulatory Control Center — VERIFICATION

Iteration: **FIRST** (no `phase11-impl-review.json` existed at start). Implemented the full
Revision-3 design from scratch per `phase11-plan.md` + `admin-design.md`.

## Environment constraint (honored)

Workspace permissions DENY shell `flutter *`. Only `dart` was used: `dart pub get`, `dart analyze`.
No `flutter build` / `flutter test` / `flutter run` was attempted, and the deny was not bypassed.

## Acceptance bar — what was run and the exact results

All commands run from `c:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web`.

### `dart pub get` — SUCCESS
```
Resolving dependencies...
Downloading packages...
  cross_file 0.3.5+5 (0.4.0 available)
  cupertino_icons 1.0.9 (2.0.0 available)
  google_mlkit_commons 0.12.0 (0.13.0 available)
  google_mlkit_text_recognition 0.16.0 (0.17.1 available)
  material_color_utilities 0.13.0 (0.13.1 available)
  meta 1.18.3 (1.19.0 available)
  test_api 0.7.12 (0.7.14 available)
  vector_math 2.4.0 (2.4.3 available)
Got dependencies!
8 packages have newer versions incompatible with dependency constraints.
```
Key line: **`Got dependencies!`** (the "newer versions available" notices are informational, not errors).

### `dart analyze` — 0 ISSUES
```
Analyzing admin_web...
No issues found!
```
This covers the whole package (`lib/` + `test/`). The pre-existing baseline (1 `creation_with_non_type`
error from the broken `MyApp` template test + info-level `depend_on_referenced_packages`, `avoid_print`,
and `curly_braces_in_flow_control_structures`) is fully resolved: the rewrite dropped the two dashboard
`print()`s, the old `products_screen.dart` (the `curly_braces` source) was deleted, `supabase_flutter`
is now a declared dependency, and the template test was replaced. **Final: 0 errors, 0 warnings, 0 info.**

Issue-count trajectory observed while building: `9 → 4 (after deps + placeholder test) → 2 (after
dashboard rewrite) → 0 (after deleting old screens) → 0 (with full test suite)`.

## Deferred commands (BLOCKED by the `flutter *` deny — not failed)

A human/CI must run these from `c:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web`:
```
flutter pub get
flutter analyze
flutter test
flutter test --update-goldens   # generates the golden reference PNGs under test/golden/goldens/
flutter build web               # route / DEMO-badge / live-data smoke
```
`flutter test --update-goldens` MUST be run before a plain `flutter test`, because the golden test files
are committed without their reference PNGs (the `flutter` toolchain that generates them is denied here).

## Orchestrator decisions (all applied)

1. **Clean web URLs.** `flutter_web_plugins` (`sdk: flutter`) declared in `pubspec.yaml`; `main()` calls
   `usePathUrlStrategy()`. This did NOT trip `dart analyze` (0 issues), so the primary path stands — the
   fallback (drop the call/import) was not needed.
2. **Lucide via a single facade.** `lib/foundations/admin_icons.dart` is the SOLE admin file importing
   `lucide_icons_flutter` (grep-verified). `lucide_icons_flutter: ^3.1.21` added. Every §12 glyph name was
   verified to exist in the installed `3.1.21` package before use (including `factory`).
3. **Right detail panel = shell state that clears on primary-route change.** `AdminShell` watches
   `detailPanelProvider`, maps the sealed `AdminDetailPayload` → (title, child), and calls
   `.close()` on any top-level route change (post-frame). Every mock surface — sidebar items, top-bar
   context, mock panels/sections, kanban cards, the map, and BOTH mock detail views — renders a persistent
   `AdminMockBadge` (`DEMO DATA`). A live route never shows an un-badged mock panel.

## Live-vs-mock boundary (preserved exactly as the design classifies it)

- **LIVE** (`public.inspections` via repositories): Dashboard KPIs (Total / Compliance Rate / Violations)
  + both charts + Top Violations + Recent Inspections; Inspections list; Inspection Details; Products.
- **MOCK** (isolated under `lib/data/mock/`, every surface DEMO-badged): Dashboard Open-Cases KPI, region
  map, Recent Cases, system status; Cases + Kanban + Map; Inspector Assignment; Audit Logs; RBAC;
  Manufacturers; India/region map (bounded graticule placeholder).

The three live screens' Supabase queries were carried forward **verbatim** (same table, columns, filters,
limits, ordering) into `InspectionsRepository` / `ProductsRepository` behind an injectable
`SupabaseClient` seam + Riverpod providers. `main.dart`'s dotenv load + a now-**guarded/idempotent**
`Supabase.initialize` are preserved; the hard `StateError` became a themed `BootstrapErrorApp`.
`packages/shared_core/lib/services/*` was not modified.

## Tests written and KEPT (under `apps/admin_web/test`)

Widget tests for the three called-out surfaces pump the widget and assert no exceptions, using
`ProviderScope`/`UncontrolledProviderScope` overrides so NONE touch Supabase:
- `test/widgets/admin_shell_test.dart` — dumb-chrome detail panel; breadcrumb single-sourced from route;
  panel open/close; **panel clears on a primary-route change**.
- `test/widgets/dashboard_test.dart` — live KPIs + badged mock supplements; **analytics-only failure
  isolates to its region while the KPI row and Recent Inspections stay rendered**.
- `test/widgets/case_management_test.dart` — `?view=` list/kanban/map toggle (invalid → list); map binds
  to `mock_regions` (not the case list); row tap opens the case in the right panel with no route change.

Supporting coverage (all analyze clean; execution deferred with `flutter test`):
- `test/widgets/components_test.dart` — AdminDataTable sort toggle + empty/loading/error; AdminStatusCell
  mapping; AdminPermissionCell/AdminHealthIndicator shape + Semantics + ABSENCE of verification labels;
  AdminKpiCard mono value at 24/`w500`; AdminMockBadge presence.
- `test/unit/*` — `analytics_math` (daily buckets; explicit `null`-`is_compliant` excluded from
  `dailyViolations` but counted in totals; top-violation tally); `groupInspectionsIntoProducts`;
  `DashboardMetrics.rate` `total == 0 → 0`; `parseFirstNumber`/`issueCount`/`issueTitles`;
  `status_mapping` incl. `null → missing`; UI-state validators (status/pageSize/search/pageIndex) +
  `casesViewFromString` + `AdminSort.toggle`; deterministic reload-stable mock VRQ id generator
  (`mockVrqId(0) == VRQ-20261004-0182`, pattern `^VRQ-\d{8}-\d{4}$`) + session-local move/assign; model
  `fromMap`s; repository column/limit regression guards.
- `test/integration/navigation_test.dart` — every route; `/inspections/:id` via `extra`; cold-load
  graceful-null fallback; top-bar search seeding `inspectionsSearchProvider` then landing on
  `/inspections`; not-found error page.
- `test/golden/charts_golden_test.dart` — AdminLineChart, AdminDonut, AdminBarMini, AdminRegionMap,
  VeriqooStatus cells (reduced-motion for stable frames; reference PNGs via deferred `--update-goldens`).
- `test/widget_test.dart` — top-level boot smoke test (replaces the old `MyApp` placeholder).

## Implementation notes / deviations (non-blocking, documented for the reviewer)

- **Supporting helper added:** `lib/widgets/common/admin_workspace_header.dart`
  (`AdminWorkspaceHeader` + `AdminWorkspaceScroll`) composes shared atoms to DRY the per-screen workspace
  layout. It introduces no new visual language.
- **Per-screen actions placement:** the shell top bar carries the global Inspections search + breadcrumb +
  DEMO context; per-screen refresh/export `VeriqooIconButton`s are rendered in each screen's workspace
  header rather than injected up into the shared top bar. This keeps the persistent chrome loop-free and
  avoids build-time provider mutation; the affordances remain present and labelled on every relevant
  screen. No user capability is removed.
- **Repository regression guard (forced by the environment):** the design calls for a fake `SupabaseClient`
  to assert exact query shapes. Because `flutter test` cannot be run here (deny), no mocking library is
  available, and hand-faking Supabase's awaitable fluent builder chain would be unverifiable and risk the
  analyze-clean gate, the regression surface is instead guarded by (a) public column/limit CONSTANTS on
  the repositories asserted in `test/unit/repository_columns_test.dart` and (b) pure-transform unit tests
  (`analytics_math`, `groupInspectionsIntoProducts`, `InspectionRow.fromMap`). The `inspectionById`
  null-on-error contract is implemented and exercised indirectly through the cold-load fallback
  integration test; a fake-client execution test is deferred alongside `flutter test`.

## Security callout (surfaced, not silently shipped)

`admin_web` has NO authentication/authorization and reads `public.inspections` with the anon key; the RBAC
screen enforces nothing (and says so). Out of Phase 11 scope, but the build must not be deployed to a
public origin with production data until Supabase Auth + RLS are added.
