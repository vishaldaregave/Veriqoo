# admin_web Phase 11 — Monochrome Regulatory Control Center — IMPLEMENTATION REVIEW

Behavioral/fidelity review of the local `apps/admin_web` implementation against the approved
Revision-3 design (`admin-design.md`) and the sequencing plan (`phase11-plan.md`). First
implementation-review pass — no prior `phase11-impl-review.json` existed. Judged for correctness and
design fidelity; nothing was re-implemented, and per the step contract `dart pub get` / `dart analyze`
/ any `flutter *` command were **not** re-run (the recorded evidence in `phase11-verification.md` is
treated as authoritative).

The implementation lands the full Revision-3 design: a persistent `AdminShell` (sidebar + top bar +
routed workspace + optional right detail panel) over a go_router `ShellRoute`, the three live screens'
Supabase reads moved verbatim into injectable repositories behind a Riverpod seam, and every
backend-less surface rendered from an isolated, DEMO-badged mock layer. All six acceptance checks
pass. The three orchestrator decisions are applied as written, the live-vs-mock boundary matches the
classification exactly, and the live Supabase queries are preserved byte-for-byte against the
superseded screens. The findings below are all non-blocking (deferred-execution and
already-acknowledged-scope items).

Watch for: (1) the test suite is present and analyze-clean but **unexecuted** — only `dart analyze`
ran; `flutter test`, goldens, and `flutter build web` are blocked by the workspace `flutter *` deny
and deferred to CI/human (confirmed). (2) `admin_web` ships with **no auth/authorization**, reads with
the anon key, and the RBAC screen enforces nothing — out of Phase 11 scope and explicitly surfaced,
but it is a network-exposed data surface that must not be deployed to a public origin with production
data (confirmed). (3) Six `apps/user_app/**` source files were modified *after* this step's recorded
session ended, in the shared uncommitted working tree — not attributable to the Phase 11 coder, but
flagged so the orchestrator confirms cross-task isolation (possible).

**Verdict**: APPROVED

## High-level view

The acceptance bar is met on the recorded evidence: `dart pub get` resolved (`Got dependencies!`) and
`dart analyze` reported `No issues found!` across `lib/` + `test/`. The build began from a 9-issue
baseline and the recorded trajectory (9 → 4 → 2 → 0) matches the plan's predicted path.

The clean-URL decision took its primary path, not the fallback: `flutter_web_plugins` is declared as
an SDK dep and `main()` calls `usePathUrlStrategy()` before bootstrap, and since analyze stayed clean
the import/call were kept. Icons go through a single `AdminIcons` facade that is the sole admin
importer of `lucide_icons_flutter` (grep-confirmed), mirroring shared_core's `VeriqooIcons` contract.

The right detail panel is shell-owned state that clears on any top-level route change, and every
mock-backed surface — sidebar items, top-bar context, mock panels, KPI card, kanban cards, the map,
and both mock detail views inside the panel — carries a `DEMO DATA` badge. A live route never shows an
un-badged mock panel.

The live data seam is the strongest part of the change: the three live screens' Supabase reads were
lifted verbatim (same table, columns, filters, limits, ordering) into `InspectionsRepository` /
`ProductsRepository` behind an injectable `SupabaseClient`, exposed through independent Riverpod
providers. A direct comparison against the superseded root-level screens confirms no query drift, so
live Dashboard/Inspections/Products behavior is preserved. Mock data lives under `lib/data/mock/` with
its own providers; no live repository or the live providers file imports it.

Write scope holds for the Phase 11 work: no commits, no worktree, shared_core untouched, and the
admin_web tree is self-contained. The test seam is real — the harness overrides every live provider
with deterministic fakes, so no widget/repository test touches Supabase — but the suite's runtime
behavior is unverified because the toolchain that runs it is denied here.

<details>
<summary>Issues (5)</summary>

1. **Tests unexecuted (toolchain deny)** — the full unit/widget/golden/integration suite is written
   and analyze-clean, but only `dart analyze` ran; `flutter test` / `--update-goldens` / `flutter
   build web` are deferred to CI/human. Runtime pass/fail is unproven. Non-blocking (matches the
   agreed acceptance bar); CI must run them.
2. **Golden reference PNGs absent** — `test/golden/charts_golden_test.dart` ships without baseline
   images; a plain `flutter test` will fail until `flutter test --update-goldens` is run first.
   Non-blocking; sequence documented in the verification evidence.
3. **Repository fake-client execution test deferred** — the design's preferred fake-`SupabaseClient`
   query-shape assertion is replaced by public column/limit constants + pure-transform tests. Verbatim
   parity was instead confirmed by manual comparison in this review. Non-blocking; add the fake-client
   test when `flutter test` is runnable.
4. **Security posture** — no authentication/authorization; reads use the anon key; RBAC is
   illustrative and enforces nothing. Out of Phase 11 scope and surfaced in both design and
   verification, but do not deploy to a public origin with production data until Supabase Auth + RLS
   land. Non-blocking for this gate.
5. **user_app working-tree edits post-date this session** — six `apps/user_app/lib/**` source files
   were modified at 03:41–03:43, after the coder's last admin_web write (03:34) and verification doc
   (03:37). Not attributable to the Phase 11 coder; flagged so the orchestrator confirms the shared
   uncommitted tree isn't cross-contaminating tasks. Possible; non-blocking.

</details>

<details>
<summary>Details</summary>

### Acceptance bar — evidence read, not re-run

`phase11-verification.md` records `dart pub get` → `Got dependencies!` (the trailing "newer versions
available" lines are informational, not errors) and `dart analyze` → `No issues found!` over the whole
package. The evidence is specific and internally consistent: it narrates the 9 → 4 → 2 → 0 issue
trajectory that the plan predicted (deps + placeholder test clears the `MyApp` error and the four
`depend_on_referenced_packages` infos; the dashboard rewrite drops two `avoid_print`s; deleting the old
`products_screen.dart` clears two `curly_braces` infos). Per the step contract this evidence is
authoritative and was not re-run. The deferred `flutter` commands are correctly characterized as
blocked by the deny, not failed (confirmed).

### Decision 1 — clean web URLs took the primary path (confirmed)

`pubspec.yaml` declares the SDK dep (`flutter_web_plugins: sdk: flutter`) and `main.dart` calls
`usePathUrlStrategy()` from `package:flutter_web_plugins/url_strategy.dart` before `_bootstrap()`.
Because analyze stayed clean, the documented fallback (drop the call/import and the dep) was correctly
not taken. `main.dart` also preserves the dotenv load, reads `SUPABASE_URL` + `SUPABASE_ANON_KEY`/
`SUPABASE_KEY`, and replaces the old hard `StateError` with a themed `BootstrapErrorApp`
(`MaterialApp(theme: VeriqooTheme.dark, …)` wrapping `VeriqooErrorState`) that names the missing key —
so the error surface has the mandatory `VeriqooTheme` ancestor its tokens need. The guarded
`_isSupabaseInitialized()` probe makes `Supabase.initialize` idempotent on retry (R3·#12).

### Decision 2 — AdminIcons single-importer facade (confirmed)

A repository-wide grep for `lucide_icons_flutter` returns exactly one hit:
`lib/foundations/admin_icons.dart`. The facade exposes the §12 semantic glyphs as `IconData`
constants from `LucideIcons.*`, re-aliases the eight glyphs that already exist in `VeriqooIcons`
(search/settings/close/chevronRight/check/alert/verified/violation/back) rather than re-sourcing them,
documents `notifications` as reserved-and-unused, and uses `LucideIcons.factory` for `manufacturers`
(legal — `factory` is a built-in identifier, and analyze is clean). A handful of supplementary glyphs
(inspector/image/report/info/list) were added for mock/detail surfaces; this is additive and within
scope.

### Decision 3 — detail-panel lifecycle and mock badging (confirmed)

`AdminShell` reads the active path from `GoRouterState.of(context).uri`, derives the top-level segment,
and when it changes posts a frame callback that calls `detailPanelProvider.notifier.close()` — so the
panel clears on a primary-route change but survives same-route changes like a `/cases?view=` toggle.
`admin_shell_test.dart` asserts this directly (open a case panel on `/cases`, `go('/inspections')`,
expect `detailPanelProvider == null`). The panel itself is dumb chrome: `AdminShell` `switch`es the
sealed `AdminDetailPayload` (`ManufacturerPayload`/`CasePayload`) to a `(title, child)` pair, and
`AdminDetailPanel` renders only title + child + close. On narrow (<768) the same payload is shown via
`showGeneralDialog` (admin-local `Dialog`, not `VeriqooModal`, not a route), and every dismissal path
routes back through `close()`.

Both in-panel detail views (`_ManufacturerDetailView`, `_CaseDetailView`) render `AdminMockBadge`
first. Badge coverage across the rest of the mock surface is complete: sidebar mock items carry a
`DEMO` `AdminTag` plus a "demo data" `Semantics` label (`admin_sidebar.dart`), the top bar shows a
badge when the active route is mock, and `AdminKpiCard`, `AdminSectionCard`, `AdminWorkspaceHeader`,
`AdminRegionMap`, and `AdminKanbanCard` all badge when mock. `AdminMockBadge` defaults to the
`DEMO DATA` label.

### Live Supabase seam preserved verbatim (confirmed by direct comparison)

The three live screens' reads were moved into `InspectionsRepository` / `ProductsRepository` with an
injectable `SupabaseClient` (default `Supabase.instance.client`). Comparing the new repositories
against the superseded root-level screens (`git show HEAD:lib/screens/dashboard/*.dart`) line by line:

```
dashboard counts   old: from('inspections').select('product_name')[.eq('is_compliant', x)].count(exact)
                   new: InspectionsRepository._count()                                   — identical
recent (50)        old: select(<13-col list>).order('inspected_at', desc).limit(50)
                   new: recentInspections(limit:50)                                      — identical
analytics (30d)    old: select('inspected_at, is_compliant, possible_issues').gte(cutoff).order(asc)
                   new: analytics(days:30)                                               — identical
inspections (200)  old: count(exact) + select(<13 cols>).order(desc).limit(200)
                   new: inspectionsPage(limit:200)                                       — identical
products (500)     old: select(<13-col list>).order(desc).limit(500) + in-memory grouping
                   new: groupedProducts(limit:500)                                       — identical
```

The 13-column list is preserved exactly and pinned as public `columns`/`columnsWithId` constants for a
drift guard. Filtering/sorting/paging stay client-side over the fetched rows (today's semantics; no
string interpolation into Supabase filters). `inspectionById` runs `.eq('id', id).maybeSingle()` inside
a `try` and returns `null` — never a raw error — on `PostgrestException` (logging `42703` at info,
others at warning), zero rows, or a parse failure, which is what feeds the §5.3 cold-load fallback.
The three dashboard reads are exposed as three independent `FutureProvider`s so a failure in one blanks
only its panel; `dashboard_test.dart` proves it (an analytics-only error shows the region's retry
state while the KPI row and Recent Inspections stay rendered). shared_core's `SupabaseService` (the
write path) is untouched.

### Live-vs-mock boundary and isolation (confirmed)

The classification matches the design exactly. LIVE: Dashboard KPIs (Total/Compliance Rate/Violations)
+ both charts + Top Violations + Recent Inspections, the Inspections table, Inspection Details, and
Products — all sourced from the live repositories. MOCK: the Open-Cases KPI, region map, Recent Cases,
and system status on the dashboard; Cases/Kanban/Map; Inspector Assignment; Audit Logs; RBAC;
Manufacturers; the India/region map. The sidebar marks exactly the five mock destinations
(`isMock: true` on Cases, Inspector Assignment, Manufacturers, Audit Logs, Access Control) and leaves
Dashboard/Inspections/Products live.

Isolation is structural: a grep for mock imports shows no live repository and neither `providers.dart`
nor `supabase_providers.dart` importing `lib/data/mock/**`. Mock repositories live behind their own
providers (`casesProvider`, `inspectorsProvider`, `manufacturersProvider`, `auditLogsProvider`,
`mockDashboardSupplementProvider`). The hybrid dashboard is the one surface consuming both, and it
badges each mock panel independently, so live and mock never blur. The Cases map view binds to the
shared `mock_regions` fixture rather than the case list, which `case_management_test.dart` asserts
(`map.regions.length == kMockRegions.length` and `!= generateMockCases().length`).

### Routing fidelity (confirmed)

`createAdminRouter()` builds one `ShellRoute` wrapping `AdminShell` with `initialLocation:
'/dashboard'`, the `/` → `/dashboard` redirect, `/cases` `?view=` validation (invalid →
`/cases?view=list`), and an `errorBuilder` rendering the not-found `VeriqooErrorState` inside the shell.
`/inspections/:id` reads `state.extra` as an `InspectionRow` and falls back to an id lookup on cold
load. The hybrid dashboard wires each region to its own provider with every KPI passing `trend: null`
(no delta is computed in Phase 11), consistent with the independent-loading contract proven by
`dashboard_test.dart`.

### Test coverage — present, seam-correct, but unexecuted

All three task-named widget tests exist and encode the right behavioral assertions:
`admin_shell_test.dart` (dumb-chrome panel, breadcrumb single-sourced from route, open via
`showManufacturer`/close via `close`, and clear-on-primary-route-change), `dashboard_test.dart`
(live KPIs + badged mock supplements, and analytics-only-failure isolation), and
`case_management_test.dart` (`?view=` list/kanban/map toggle, invalid → list, map binds `mock_regions`,
row tap opens the panel with no route change). Supporting unit/repository/golden/integration tests are
present under `test/`. The harness overrides every live provider with deterministic fakes via
`UncontrolledProviderScope`, so no test touches Supabase — the repository/provider seam does its job.

The gap: none of this has actually run. The acceptance bar here is `dart analyze` only, because the
workspace denies `flutter *`; `flutter test`, `flutter test --update-goldens`, and `flutter build web`
are deferred to CI/human (the verification evidence lists the exact commands and notes goldens must be
generated before a plain `flutter test`). So the suite compiles and analyzes clean but its runtime
behavior — including the golden images, which ship without reference PNGs — is unverified. This is
consistent with the agreed, toolchain-constrained acceptance bar, but a reviewer should treat the tests
as unproven at runtime until CI runs them. Relatedly, the design's preferred fake-`SupabaseClient`
repository execution test was swapped for column/limit constants plus pure-transform tests; the
verbatim-preservation risk that test was meant to cover is instead discharged by the direct comparison
above.

### Write scope and the user_app timing observation

For the Phase 11 work the scope holds: HEAD is unchanged (the pre-existing "Organize Veriqoo repository
structure" commit, up to date with origin/main), nothing is staged, `git worktree list` shows only the
main checkout, and shared_core's newest edit (Oct 4 23:53) predates the admin_web build entirely. Every
admin_web file reviewed lives under `apps/admin_web/**` and consumes shared_core read-only through the
barrel.

One observation worth the orchestrator's attention: the whole monorepo (`apps/`, `packages/`) is an
untracked working-tree restructure, so git can't produce a per-step diff — the review read source
directly. Within that shared tree, six `apps/user_app/lib/**` source files
(inspection_record / inspections_repository / inspections_providers / history_providers / home_strings /
home_user) carry modification times of 03:41–03:43, which is *after* the Phase 11 coder's last
admin_web write (`widget_test.dart`, 03:34:56) and after the verification doc (03:37:56). Because they
fall outside the coder's recorded session and belong to an unrelated app, they are most plausibly a
separate task's work rather than a Phase 11 scope violation — but mtimes can't prove authorship, so
this is flagged as a possible cross-task-isolation item, not a defect in this implementation.

### Security posture (surfaced, out of scope)

The build has no authentication or authorization, initializes Supabase with the anon key, and reads
`public.inspections` directly; the RBAC screen is mock and gates nothing (its header says so). This is
a network-exposed regulatory-data surface shipping without access control. It is explicitly out of
Phase 11 scope and is surfaced in both the design (§13) and the coder's verification, with the
remediation path recorded (Supabase Auth via a go_router redirect guard + RLS on `public.inspections`).
Restated here because the change touches a trust boundary: the build must not be deployed to a public
origin with production data until that lands.

</details>

<details>
<summary>File map</summary>

Entire `apps/admin_web/**` is effectively new relative to git (untracked monorepo restructure); the
review read sources directly rather than from a `git diff`. Key areas:

- `lib/main.dart`, `lib/app/{admin_app,admin_router}.dart` — bootstrap (usePathUrlStrategy, guarded
  init, themed error app), root `MaterialApp.router`, single `ShellRoute` + routes.
- `lib/foundations/admin_icons.dart` — sole `lucide_icons_flutter` importer; §12 glyph facade.
- `lib/data/{inspections_repository,products_repository,analytics_math}.dart` — live reads carried
  forward verbatim behind an injectable client.
- `lib/data/{providers,supabase_providers,detail_panel}.dart` — three independent dashboard providers,
  UI-state notifiers, sealed detail-panel payload + controller.
- `lib/data/mock/**` — isolated mock repositories/fixtures, each behind its own provider; DEMO-badged
  at every surface.
- `lib/widgets/shell/**` — `AdminShell` (route-change panel clearing, breakpoints, payload→chrome),
  sidebar/top-bar/breadcrumb/detail-panel.
- `lib/widgets/{data_table,kanban,charts,map,common}/**` — presentation widgets (bespoke
  CustomPainter charts/map, no fl_chart).
- `lib/screens/**` — live Inspections/Inspection Details/Products, rewritten hybrid Dashboard, and the
  five mock screens.
- `test/**` — shell/dashboard/case-management widget tests (task-named), plus unit/repository/golden/
  integration suites and a network-free harness.

Changed outside admin_web: none attributable to this step (see the write-scope section for the
user_app mtime note).

</details>
