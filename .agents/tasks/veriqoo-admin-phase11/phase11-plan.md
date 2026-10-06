# VERIQOO Phase 11 — admin_web Monochrome Regulatory Control Center — IMPLEMENTATION PLAN

This plan sequences the build of the finished, approved design in
`.agents/tasks/veriqoo-admin-phase11/admin-design.md` (Revision 3). The design is final; this
document only orders the work. Where the design and the orchestrator decisions below disagree with
anything else, those win. Nothing here re-decides architecture.

## Build / environment contract (read before starting)

- **Toolchain:** `flutter *` is DENIED in this workspace (verified). Use `dart` only:
  `dart pub add`, `dart pub get`, `dart analyze`. Do NOT run `flutter build` / `flutter test` /
  `flutter run` and do NOT attempt to bypass the deny.
- **Acceptance bar:** `dart pub get` succeeds AND `dart analyze` (run in `apps/admin_web`) reports
  **0 issues**. `flutter test`, `flutter test --update-goldens`, and `flutter build web` are
  **DEFERRED** (blocked by the deny, not failed) — see step 15 for the exact commands a human/CI runs.
- **All commands run from `c:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web`** unless noted.
- **Write scope (STRICT):** modify ONLY `apps/admin_web/**`. Do NOT touch
  `packages/shared_core/**` or `apps/user_app/**`. Consume the design system read-only via
  `import 'package:shared_core/design_system/design_system.dart';`. Do NOT add `google_fonts`
  (fonts are bundled by shared_core) and do NOT add `fl_chart`.
- **No git:** all work is directly in the main workspace. Do NOT create commits or a worktree.
- **Theme entry points are getters:** `VeriqooTheme.dark` / `VeriqooTheme.light`. Tokens via
  `Theme.of(context).extension<VeriqooTokens>()!`.

### Confirmed `dart analyze` baseline (today = 9 issues)

| Count | Severity | Rule | Location | Cleared by |
| --- | --- | --- | --- | --- |
| 1 | error | `creation_with_non_type` (`MyApp` undefined) | `test/widget_test.dart:16` | step 1 (replace broken template test) |
| 4 | info | `depend_on_referenced_packages` (supabase_flutter) | `main.dart`, `dashboard_screen.dart`, old `inspections_screen.dart`, old `products_screen.dart` | step 1 (declare `supabase_flutter` directly) |
| 2 | info | `avoid_print` | `dashboard_screen.dart:22,210` | step 12 (dashboard rewrite drops the two `print()`s) |
| 2 | info | `curly_braces_in_flow_control_structures` | old `products_screen.dart:91,93` | step 14 (old `products_screen.dart` deleted) |

Expected issue-count trajectory as the plan executes:
`9 (baseline) → 4 (after step 1) → 4 (steps 2–11, no new issues) → 2 (step 12) → 2 (step 13) → 0 (step 14) → 0 (step 15)`.
Every step's verification is "`dart analyze` introduces **no new** issues and matches the expected
count"; the final two steps assert an absolute **0**.

## Orchestrator decisions baked into this plan (final)

1. **Clean web URLs.** Declare the SDK dep in `pubspec.yaml`:
   ```yaml
   flutter_web_plugins:
     sdk: flutter
   ```
   and call `usePathUrlStrategy()` in `main()` (step 14). **Fallback:** if adding the import/call
   causes ANY `dart analyze` issue, DROP `usePathUrlStrategy()` and its import (and remove the
   `flutter_web_plugins` dep), reverting to the default hash URL strategy — the analyze-clean gate wins.
2. **Lucide via a single facade.** `apps/admin_web/lib/foundations/admin_icons.dart` is the SOLE file
   in admin_web that imports `lucide_icons_flutter`. Add `lucide_icons_flutter: ^3.1.21`. No other
   admin file imports lucide directly (mirrors shared_core's `VeriqooIcons` sole-importer contract).
3. **Right detail panel is shell state that CLEARS on primary-route change** (closes when navigating
   to a different top-level route). EVERY mock-backed surface — including the mock detail panel — renders
   a persistent `DEMO` badge; a live route must never display an un-badged mock panel.

---

## Reference: pubspec dependency changes (step 1)

Add to `apps/admin_web/pubspec.yaml` `dependencies:` (keep existing `go_router: ^18.0.2`,
`flutter_riverpod: ^3.4.3`, `flutter_dotenv: ^6.0.1`, `shared_core` path dep, `cupertino_icons`):

```yaml
  flutter_web_plugins:
    sdk: flutter          # decision 1 — enables usePathUrlStrategy(); drop if it trips analyze
  supabase_flutter: ^2.17.2   # pinned to shared_core; admin imports it directly (stops depend_on_referenced_packages)
  lucide_icons_flutter: ^3.1.21  # pinned to shared_core; only foundations/admin_icons.dart imports it
```

The two hosted deps may be added with
`dart pub add supabase_flutter:^2.17.2 lucide_icons_flutter:^3.1.21`; the `flutter_web_plugins` SDK
dep must be hand-added to the YAML (SDK deps are awkward via `dart pub add`). Then `dart pub get`.

## Reference: route table (go_router — single `ShellRoute`, `initialLocation: '/dashboard'`)

Created by `createAdminRouter()` in `lib/app/admin_router.dart`. One
`ShellRoute(builder: (_, __, child) => AdminShell(child: child))`.

| Path | Screen widget | File | Backing |
| --- | --- | --- | --- |
| `/` | — (`redirect` → `/dashboard`) | — | — |
| `/dashboard` | `DashboardScreen` | `screens/dashboard/dashboard_screen.dart` (rewrite in place) | **HYBRID** — LIVE KPIs(3)+charts+Top Violations+Recent Inspections; MOCK open-cases KPI, region map, recent cases, system status |
| `/inspections` | `InspectionsScreen` | `screens/inspections/inspections_screen.dart` | **LIVE** |
| `/inspections/:id` | `InspectionDetailsScreen` | `screens/inspections/inspection_details_screen.dart` | **LIVE** (row via `extra`; cold-load null fallback) |
| `/products` | `ProductsScreen` | `screens/products/products_screen.dart` | **LIVE** |
| `/manufacturers` | `ManufacturerManagementScreen` | `screens/manufacturers/manufacturers_screen.dart` | **MOCK** |
| `/cases` | `CaseManagementScreen` | `screens/cases/cases_screen.dart` | **MOCK** (`?view=list\|kanban\|map`, default `list`; invalid → `list`) |
| `/assignments` | `InspectorAssignmentScreen` | `screens/assignments/assignments_screen.dart` | **MOCK** |
| `/audit` | `AuditLogsScreen` | `screens/audit/audit_logs_screen.dart` | **MOCK** |
| `/rbac` | `RbacScreen` | `screens/rbac/rbac_screen.dart` | **MOCK** |

- `errorBuilder` → full-workspace `VeriqooErrorState(title: 'Page not found', onRetry → go('/dashboard'))`.
- Case detail and manufacturer detail open in the **right `AdminDetailPanel`** by object reference —
  **not** a route. There is no `/cases/:vrqId`.

## Reference: live-vs-mock classification (hard boundary)

- **LIVE** (reads `public.inspections` via repositories; must match today's results exactly):
  Dashboard KPI counts (Total, Compliance Rate, Violations), both charts (Inspection Activity,
  Violation Trend), Top Violations, Recent Inspections; the Inspections table; Inspection Details;
  Products (grouped from inspections).
- **MOCK** (isolated under `lib/data/mock/`, every surface `DEMO`-badged): Dashboard Open-Cases KPI,
  region map, Recent Cases, system status; Cases + Kanban + map; Inspector Assignment; Audit Logs;
  RBAC; Manufacturers; the India/region map (bounded graticule placeholder, no India-outline asset).
- No mock type is referenced from a live repository or shares a provider with one. The `AdminMockBadge`
  (`DEMO DATA`) appears on every mock sidebar item, mock route top-bar context, mock panel/section
  header, kanban card, map, **and the detail panel's mock detail views** (decision 3).

## Reference: repository + Riverpod seam (preserve the working Supabase wiring verbatim)

The three live screens today call `Supabase.instance.client.from('inspections')` directly. Move those
exact queries (same table, columns, filters, limits, ordering) into injectable repositories; expose
them through Riverpod. Repositories take an optional `SupabaseClient` (default
`Supabase.instance.client`) so tests inject a fake and `ProviderScope` can override.

`InspectionsRepository({SupabaseClient? client})` methods, each preserving today's query:
- `dashboardMetrics()` → three counts via `Future.wait`: `from('inspections').select('product_name').count(CountOption.exact)` for total; same with `.eq('is_compliant', true)` and `.eq('is_compliant', false)`. Returns `DashboardMetrics` with `double get rate => total == 0 ? 0 : compliant / total` (the `total == 0 → 0` guard is carried forward). The internal `Future.wait` is scoped to this method; a failure blanks only the KPI row.
- `recentInspections({int limit = 50})` → the full column `select(...)` `.order('inspected_at', ascending: false).limit(50)` (today's `_recent()` column list, verbatim).
- `analytics({int days = 30})` → `select('inspected_at, is_compliant, possible_issues').gte('inspected_at', cutoffIso).order('inspected_at', ascending: true)`, bucketed by UTC day. `dailyViolations` = per-day count of `is_compliant == false` (matches the Violations KPI; `null` and `true` excluded). Pure bucketing/tally lives in `data/analytics_math.dart`.
- `inspectionsPage(...)` → count + `.order('inspected_at', ascending: false).limit(200)`; filter/sort/page stay **client-side** over the ≤200 rows (today's semantics). No string interpolation into Supabase filters.
- `inspectionById(String id)` → best-effort `.eq('id', id).maybeSingle()` inside `try`; **returns `null`** on PostgrestException (incl. `42703` missing column), zero-row, or parse error — never a raw `AsyncError`. Missing-column logs `info`; other failures `warning`.

`ProductsRepository({SupabaseClient? client})`:
- `groupedProducts({int limit = 500})` → `.order('inspected_at', ascending: false).limit(500)` then in-memory group by `product_name|manufacturer` into `ProductAggregate` (count + summed `issueCount` + latest row). Carries forward the tolerant `issueCount` (JSON-array length, else 1 for non-empty text, else 0).

Providers (`lib/data/providers.dart`), each loading/erroring/retrying independently:
- `supabaseClientProvider` (in `lib/data/supabase_providers.dart`) → `Supabase.instance.client`.
- `inspectionsRepositoryProvider`, `productsRepositoryProvider`.
- `dashboardDataProvider` `FutureProvider<DashboardMetrics>`; `recentInspectionsProvider` `FutureProvider<List<InspectionRow>>`; `inspectionAnalyticsProvider` `FutureProvider<InspectionAnalytics>` (feeds both charts AND Top Violations); `inspectionsPageProvider`; `productsProvider`.
- `inspectionByIdProvider` `FutureProvider.family<InspectionRow?, String>` → `inspectionById(id)` (null, not error, on the not-found path).
- UI-state notifiers, each a named `Notifier` subclass with both type args (NOT `NotifierProvider<String>`): e.g. `class InspectionsSearch extends Notifier<String> { @override String build() => ''; ... }` → `inspectionsSearchProvider = NotifierProvider<InspectionsSearch, String>(InspectionsSearch.new)`. Same shape for status filter, sort spec, page, pageSize, cases view mode.
- Detail panel (`lib/data/detail_panel.dart`): sealed `AdminDetailPayload` with `.manufacturer(Manufacturer)` / `.caseRecord(CaseRecord)`; `DetailPanelController extends Notifier<AdminDetailPayload?>` with `showManufacturer(...)`, `showCase(...)`, `close()`; `detailPanelProvider = NotifierProvider<DetailPanelController, AdminDetailPayload?>(DetailPanelController.new)` (`null` = closed).

## Reference: widget / test plan (step 15; files written and kept, execution DEFERRED)

Follow design §17. Tests use the repository/provider seam so they never hit Supabase (inject a fake
`SupabaseClient`; override providers in `ProviderScope`). Required coverage, with the three named by
the task called out:
- **Shell (`AdminShell`):** active-nav highlight derived from a given `GoRouterState.uri`; the detail
  panel **clears on route change** (open a case panel on `/cases`, navigate to `/inspections`, assert
  closed); detail panel open/close via `showCase`/`showManufacturer`/`close` with `AdminDetailPanel`
  fed a stub `title`+`child` (proves it is chrome-only) across the §8 breakpoints (docked/overlay vs
  full-screen `Dialog`); every narrow-`Dialog` dismissal path routes through `close()`.
- **Dashboard:** three independent live providers render into their own panels; a failure in only
  `inspectionAnalyticsProvider` shows the charts/Top-Violations error state while the KPI row and
  Recent Inspections stay rendered (`ProviderScope` overrides a fake repo); `AdminKpiCard` value is
  mono at 24px `w500`; every mock panel carries `AdminMockBadge`.
- **Case Management:** `AdminViewToggle` switches list/kanban/map via the `?view=` query param
  (invalid → list); row/card tap calls `detailPanelProvider.notifier.showCase(...)` and opens the
  right panel (no route); the map view binds to the shared `mock_regions.dart` `List<RegionDensity>`,
  not to `CaseRecord`; mock VRQ ids match `^VRQ-\d{8}-\d{4}$` and are reload-stable.
- **Other widget tests:** `AdminDataTable` sort toggle + empty/loading/error; `AdminStatusCell`
  mapping; `AdminPermissionCell`/`AdminHealthIndicator` shape + `Semantics` and ABSENCE of the
  verification labels; `AdminMockBadge` presence on mock surfaces.
- **Unit (pure):** `analytics_math` (daily buckets, rate, `dailyViolations` with an explicit
  `null`-`is_compliant` excluded-from-violations-but-counted-in-totals test); `DashboardMetrics.rate`
  `total == 0 → 0`; `parseFirstNumber` (`"Rs.120"→120`, `"200 g"→200`, `"₹99.9"→99.9`, no-digit→-1);
  product grouping; `status_mapping` incl. `null → missing`; tolerant `issueCount`;
  search/sort/paging/route validators; `chart_axis` transforms; `AdminDataColumn` sort allowlist;
  deterministic reload-stable mock VRQ-id generator; model `fromMap`s.
- **Unit (repositories):** inject a fake `SupabaseClient`; assert exact table/columns/filters/limits
  are preserved (regression guard); assert `inspectionById` returns `null` (not throw) on a
  missing-`id`-column `PostgrestException` and on zero rows.
- **Golden (monochrome):** `AdminLineChart`, `AdminDonut`, `AdminRegionMap`, `admin_bar_mini`,
  `VeriqooStatus` cells. (Golden reference PNGs require `flutter test --update-goldens` → DEFERRED;
  write the test files now — they analyze clean without the reference images.)
- **Integration:** go_router across all routes; `/inspections/:id` via `extra` and the cold-load
  null fallback; top-bar global search seeding `inspectionsSearchProvider` then landing on
  `/inspections` with the term applied; `/cases?view=` toggling.

---

# Implementation Plan

- [ ] 1. Establish a clean build baseline: add dependencies and remove the broken template test.
      Add to `pubspec.yaml` `dependencies`: `flutter_web_plugins` (`sdk: flutter`),
      `supabase_flutter: ^2.17.2`, `lucide_icons_flutter: ^3.1.21` (see pubspec reference above);
      run `dart pub get`. Replace the default `test/widget_test.dart` (it references the nonexistent
      `MyApp`, the one baseline error) with a trivial placeholder test (e.g. `test('placeholder', () { expect(true, isTrue); });`)
      so analyze is error-free from here on; step 15 overwrites it with the real suite.
      Files: `pubspec.yaml`, `test/widget_test.dart`.
      Verify: `dart pub get` succeeds; `dart analyze` reports **4 issues** — the 4
      `depend_on_referenced_packages` infos and the `MyApp` error are gone; the only remaining issues
      are the 2 `avoid_print` (dashboard) + 2 `curly_braces` (old products) that later steps remove.

- [ ] 2. Create the `AdminIcons` facade — the ONLY admin file importing `lucide_icons_flutter`.
      Expose the §12 semantic members (`dashboard, inspections, products, manufacturers, cases, kanban,
      map, assignments, audit, rbac, filter, sort/sortAsc/sortDesc, columns, more, refresh, export,
      menu, chevronLeft/chevronDown, calendar, clock, location, trendUp/trendDown, plus`; `notifications`
      reserved/unused) as `IconData` constants from `LucideIcons.*`; reuse `VeriqooIcons` where a glyph
      already exists. If a Lucide constant name differs in `^3.1.21`, fix it here only.
      Files: `lib/foundations/admin_icons.dart`.
      Verify: `dart analyze` — no new issues (count stays 4); the lucide import resolves.

- [ ] 3. Create the pure data layer: typed models, enums, status mapping, and parsing helpers.
      One coherent set of small data classes (tolerant `fromMap`, carry forward `issueCount`):
      `InspectionRow, DashboardMetrics` (with `rate` + `total == 0 → 0` guard), `InspectionAnalytics,
      ProductAggregate, CaseRecord, Inspector, AuditLogEntry, Role, Permission, Manufacturer,
      RegionDensity, SystemStatusRow`; enums `CasePriority{low,medium,high,critical}`,
      `CaseStatus{new_,triage,assigned,inProgress,resolved,closed}`, `ServiceHealth{operational,degraded,offline}`;
      `status_mapping.dart` (pure: `is_compliant==true→verified`, `==false & issues→violation`,
      `==false & only missing→flag`, `null/unreadable→missing`); `parsing.dart`
      (`parseFirstNumber` = first numeric run with optional decimal, no digit → -1).
      Files: `lib/models/{inspection_row,dashboard_metrics,inspection_analytics,product_aggregate,case_record,inspector,audit_log_entry,role,permission,manufacturer,region_density,system_status_row,status_mapping}.dart`, `lib/utils/parsing.dart`.
      Verify: `dart analyze` — no new issues (count stays 4).

- [ ] 4. Create the live repository + provider seam (preserve the Supabase queries verbatim).
      Implement `InspectionsRepository`, `ProductsRepository`, `analytics_math.dart`,
      `supabase_providers.dart`, `providers.dart` (three independent dashboard `FutureProvider`s +
      `inspectionsPageProvider` + `productsProvider` + `inspectionByIdProvider` family + the named
      UI-state `Notifier`s incl. `inspectionsSearchProvider`), and `detail_panel.dart` (sealed
      `AdminDetailPayload` + `DetailPanelController` + `detailPanelProvider`), exactly per the
      "repository + Riverpod seam" reference above.
      Files: `lib/data/{supabase_providers,inspections_repository,products_repository,analytics_math,providers,detail_panel}.dart`.
      Verify: `dart analyze` — no new issues (count stays 4). (Query/behavior parity is asserted by the
      repository unit tests in step 15.)

- [ ] 5. Create the isolated mock data layer (every surface will be DEMO-badged).
      `admin_mock.dart` (`const kIsMockData = true;`, `AdminMockBadge` export reference, `MockLatency`
      helper routing through the same `AsyncValue` path); mock repositories with the SAME method shapes
      as live repos, each behind its own provider (`casesProvider`, `inspectorsProvider`, …);
      `MockCasesRepository` seeds a deterministic generator so VRQ ids match `^VRQ-\d{8}-\d{4}$` and are
      reload-stable; `mock_regions.dart` (Maharashtra 1,284 / 86 headline);
      `mock_dashboard_supplement.dart` (open-cases KPI, system-status rows, recent cases, region markers).
      Files: `lib/data/mock/{admin_mock,mock_cases_repository,mock_inspectors_repository,mock_audit_repository,mock_rbac_repository,mock_manufacturers_repository,mock_regions,mock_dashboard_supplement}.dart`.
      Verify: `dart analyze` — no new issues (count stays 4).

- [ ] 6. Create the common admin widgets (monochrome, hairline-over-shadow, token-driven).
      `admin_panel` (square, `tokens.surface`, 1px `borderHairline`, no shadow), `admin_kpi_card`
      (`label` uppercased meta; value `VeriqooType.mono.copyWith(fontSize: 24, fontWeight: FontWeight.w500)`;
      all callers pass `trend: null`), `admin_status_cell` (→ `VeriqooStatus` for inspections/products
      only), `admin_permission_cell` (shape-coded + `Semantics`, no verification labels),
      `admin_health_indicator` (`OPERATIONAL/DEGRADED/OFFLINE` + `Semantics`), `admin_priority_indicator`
      (shape, never hue), `admin_tag` (uppercases its own text), `admin_mock_badge` (`DEMO DATA`),
      `admin_section_card`.
      Files: `lib/widgets/common/{admin_panel,admin_kpi_card,admin_status_cell,admin_permission_cell,admin_health_indicator,admin_priority_indicator,admin_tag,admin_mock_badge,admin_section_card}.dart`.
      Verify: `dart analyze` — no new issues (count stays 4).

- [ ] 7. Create the shell widgets (persistent desktop chrome; no mobile `VeriqooNavigationBar`).
      `admin_shell` (sidebar + top bar + routed workspace + optional right panel; owns `LayoutBuilder`
      breakpoints per §8; reads active location from `GoRouterState.of(context).uri`; **watches the
      router location and calls `detailPanelProvider.notifier.close()` on any primary-route change** per
      decision 3; `watch`es `detailPanelProvider` and `switch`es the sealed payload → `(title, child)`
      via `_ManufacturerDetailView`/`_CaseDetailView`, each carrying an `AdminMockBadge`); `admin_sidebar`
      (sections OVERVIEW/COMPLIANCE/CATALOG/GOVERNANCE, inverse-fill active marker, 72px icon rail below
      1024, `DEMO` tag on mock destinations); `admin_top_bar` (breadcrumb + Inspections global search bound
      to `inspectionsSearchProvider` that `go('/inspections')` on submit + per-screen `actions`; no
      notifications/help/profile); `admin_breadcrumb` (`.toUpperCase()` crumbs); `admin_detail_panel`
      (dumb chrome: `title` + `child` + close button + slide/overlay container; full-screen admin-local
      `Dialog` via `showGeneralDialog` below 768, NOT `VeriqooModal`, NOT a route; all dismissals call `onClose`).
      Files: `lib/widgets/shell/{admin_shell,admin_sidebar,admin_top_bar,admin_breadcrumb,admin_detail_panel}.dart`.
      Verify: `dart analyze` — no new issues (count stays 4).

- [ ] 8. Create the dense data-table widgets (presentation-only; receive filtered/sorted/paged rows).
      Generic `AdminDataTable<T>` on `AdminPanel` (hairline row separators, mono for IDs/numbers/dates,
      `density` toggle, horizontal scroll with pinned first column below min width, skeleton/empty/error
      states using static placeholders + `VeriqooEmptyState`/`VeriqooErrorState` — NOT the `VeriqooLoading`
      scan motif); `AdminDataColumn<T>` (`key`+`sortable` form the sort allowlist; optional
      `sortValue`); `AdminTableToolbar` (search + filter chips + density/column controls, callbacks only);
      `AdminPagination` (mono page readout, sizes 10/25/50).
      Files: `lib/widgets/data_table/{admin_data_table,admin_data_column,admin_table_toolbar,admin_pagination}.dart`.
      Verify: `dart analyze` — no new issues (count stays 4).

- [ ] 9. Create the kanban widgets (mock-only; mutations are session-local).
      `AdminKanbanBoard` (fixed column order NEW→TRIAGE→ASSIGNED→IN PROGRESS→RESOLVED→CLOSED, horizontal
      scroll; `onCardMoved` mutates the in-memory `MockCasesRepository`); `AdminKanbanColumn`
      (`VeriqooSectionHeader` + mono count, vertical scroll); `AdminKanbanCard` (square hairline card:
      VRQ id mono, product, manufacturer, `AdminPriorityIndicator`, assignee).
      Files: `lib/widgets/kanban/{admin_kanban_board,admin_kanban_column,admin_kanban_card}.dart`.
      Verify: `dart analyze` — no new issues (count stays 4).

- [ ] 10. Create the greyscale `CustomPainter` chart + map widgets (no `fl_chart`; token colors passed in).
      `AdminLineChart` (activity + violation-trend, dashed secondary series by texture not color),
      `AdminDonut({compliant, nonCompliant})`, `admin_bar_mini` (top-violation bars), `chart_axis.dart`
      (pure data→offset/grid/tick helpers); `AdminRegionMap` (bounded graticule placeholder + density
      markers, consumes `List<RegionDensity>`, `DEMO`-badged) and `AdminViewToggle` (list/kanban/map
      segmented control). All honor `VeriqooMotion.reduceMotion` (collapse to final frame).
      Files: `lib/widgets/charts/{admin_line_chart,admin_donut,admin_bar_mini,chart_axis}.dart`, `lib/widgets/map/{admin_region_map,admin_view_toggle}.dart`.
      Verify: `dart analyze` — no new issues (count stays 4).

- [ ] 11. Create all live + mock screens except the dashboard (in their new directories; old screens
      stay untouched until step 14 so the app keeps compiling).
      LIVE: `InspectionsScreen` (toolbar search bound to `inspectionsSearchProvider` + status filter
      `All|Compliant|Violation` + `AdminDataTable<InspectionRow>` with the §10.2 columns, sort allowlist,
      numeric `sortValue` via `parseFirstNumber` for MRP/Net Qty, pagination default 25; row tap →
      `go('/inspections/:id', extra: row)`); `InspectionDetailsScreen` (today's sections, cold-load null
      fallback via `inspectionByIdProvider`). LIVE: `ProductsScreen` (`AdminDataTable<ProductAggregate>`).
      MOCK (each `DEMO`-badged): `ManufacturerManagementScreen` (row tap → `showManufacturer`),
      `CaseManagementScreen` (`?view=` list/kanban/map; row/card tap → `showCase`; map binds
      `mock_regions`), `InspectorAssignmentScreen`, `AuditLogsScreen`, `RbacScreen` ("Illustrative — not
      enforced" header).
      Files: `lib/screens/inspections/{inspections_screen,inspection_details_screen}.dart`, `lib/screens/products/products_screen.dart`, `lib/screens/manufacturers/manufacturers_screen.dart`, `lib/screens/cases/cases_screen.dart`, `lib/screens/assignments/assignments_screen.dart`, `lib/screens/audit/audit_logs_screen.dart`, `lib/screens/rbac/rbac_screen.dart`.
      Verify: `dart analyze` — no new issues (count stays 4). (New screens compile against the step 3–10 widgets/data.)

- [ ] 12. Rewrite the Dashboard in place into the monochrome hybrid screen.
      Rewrite `screens/dashboard/dashboard_screen.dart` as a `ConsumerWidget` consuming the three
      independent live providers (`dashboardDataProvider`, `recentInspectionsProvider`,
      `inspectionAnalyticsProvider`) + `mockDashboardSupplementProvider`: KPI row (×4, `trend: null`,
      Open Cases MOCK-badged), Inspection Activity + Violation Trend charts, LIVE Top Violations
      (`admin_bar_mini`), LIVE Recent Inspections table, MOCK Recent Cases / region map / system status
      (each badged). Each live panel renders its own `AsyncValue` with per-panel
      `VeriqooErrorState(onRetry → ref.invalidate(thatProvider))`. **Remove the two `print(...)` calls.**
      Files: `lib/screens/dashboard/dashboard_screen.dart`.
      Verify: `dart analyze` reports **2 issues** — both `avoid_print` infos are gone; only the 2
      `curly_braces` infos in the still-present old `products_screen.dart` remain.

- [ ] 13. Create the go_router configuration (and optional root app widget).
      `createAdminRouter()` in `lib/app/admin_router.dart`: `initialLocation: '/dashboard'`, one
      `ShellRoute(builder: (_, __, child) => AdminShell(child: child))` with all routes from the route-table
      reference, `/`→`/dashboard` redirect, `errorBuilder` → not-found `VeriqooErrorState`, `/cases`
      `?view=` validation. Optional `lib/app/admin_app.dart` root `ConsumerWidget`.
      Files: `lib/app/admin_router.dart`, `lib/app/admin_app.dart` (optional).
      Verify: `dart analyze` — no new issues (count stays 2).

- [ ] 14. Flip the entry point and delete the superseded old screens (atomic — do together to stay buildable).
      Rewrite `main.dart`: keep `dotenv.load('.env')`; make `Supabase.initialize` **guarded/idempotent**
      (probe `Supabase.instance` in try/catch; initialize only if not already registered); replace the
      hard `StateError` with `BootstrapErrorApp = MaterialApp(theme: VeriqooTheme.dark, home: Scaffold(body: VeriqooErrorState(...)))`
      naming the missing key; wrap the app in `ProviderScope` + `MaterialApp.router(createAdminRouter(),
      theme/darkTheme: VeriqooTheme.dark, title: 'VERIQOO Admin')`; call `usePathUrlStrategy()` before
      `runApp` (decision 1 — **if `dart analyze` flags the `flutter_web_plugins` import, drop the call+import
      and remove the dep**). Delete the three superseded old screens.
      Files: `lib/main.dart`; DELETE `lib/screens/dashboard/inspections_screen.dart`, `lib/screens/dashboard/products_screen.dart`, `lib/screens/dashboard/inspection_details_screen.dart`.
      Verify: `dart analyze` reports **0 issues** (the 2 `curly_braces` infos vanish with old
      `products_screen.dart`; nothing imports the deleted files) — `lib/` is fully clean. This meets the
      acceptance bar for application code.

- [ ] 15. Write the full test suite (overwrite the placeholder) per the "widget / test plan" reference.
      Overwrite `test/widget_test.dart` and add unit, repository, widget (shell + Dashboard + Case
      Management as called out), golden, and integration tests. Tests inject a fake `SupabaseClient`
      and override providers in `ProviderScope` so none hit Supabase.
      Files: `test/widget_test.dart` and new files under `test/` (e.g. `test/unit/`, `test/widgets/`,
      `test/golden/`, `test/integration/`).
      Verify: `dart analyze` reports **0 issues** (all test files compile). Then record — as DEFERRED,
      blocked by the `flutter *` deny — the exact commands for a human/CI to run from
      `apps/admin_web`: `flutter pub get`, `flutter analyze`, `flutter test`,
      `flutter test --update-goldens` (to generate golden reference PNGs), and
      `flutter build web` (route/DEMO-badge/live-data smoke).

## Gaps / assumptions (made explicit, non-blocking)

- **A1 — inspection `id`:** `public.inspections` is assumed to have a PK `id` the repo can add to its
  `select`. Unverifiable from the repo. Handled non-blockingly: `inspectionById` returns `null` and the
  detail screen shows a graceful error → `/inspections`. If `id` exists, adding it to the `select` is the
  only change needed; if not, the fallback stands.
- **A2 — regional/system-status fixtures:** illustrative mock (no normalized state column or telemetry
  in the live table); badged DEMO.
- **Golden images:** golden test files are written and kept, but their reference PNGs require
  `flutter test --update-goldens` (denied here) — generated by CI/human in step 15's deferred commands.
- **Security (surface, do not silently ship):** admin_web has no auth/authorization and reads with the
  anon key; the RBAC screen enforces nothing. Not in Phase 11 scope, but the build must not be deployed
  to a public origin with production data until Supabase Auth + RLS are added.
