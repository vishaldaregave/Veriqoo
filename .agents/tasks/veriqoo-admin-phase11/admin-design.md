# VERIQOO Phase 11 — admin_web Monochrome Regulatory Control Center — DESIGN

Status: Revision 3 — a second design review is present (`C:\WorkSpace\Ajinkya\Veriqoo\.agents\tasks\veriqoo-admin-phase11\design-review.json`, verdict `CHANGES_REQUESTED`: 0 HIGH, 3 MEDIUM, 14 NIT, **0 ground-truth errors** — the reviewer independently verified every atom/token/type/icon/query/schema/dependency claim as accurate). All 17 findings are resolved in place; see §21 Review responses for the per-finding disposition. (Revision 2 had resolved the first review's 0 HIGH / 3 MEDIUM / 8 NIT; those inline `M#`/`N#` annotations are retained as design rationale. New-review findings are cited inline as `R3·#1`…`R3·#17`.)
Target app: `C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web`
Design system (read-only, consumed): `C:\WorkSpace\Ajinkya\Veriqoo\packages\shared_core\lib\design_system\design_system.dart`

---

## 1. Overview

Phase 11 converts `admin_web` from the current blue/green Material prototype into a dark-first, strictly monochrome **desktop regulatory control center** for Legal Metrology (Packaged Commodities) Rules, 2011 enforcement. The app keeps a persistent left sidebar, a contextual top header with global search, a scrolling main workspace, and an optional right detail panel. It renders every surface from the shared VERIQOO tokens, type ramp, icon facade, and atoms — no new visual language is invented, and no color is used to carry meaning.

Three screens are **live-wired** today against a single flat Supabase table (`public.inspections`): Dashboard KPIs/charts, Inspections, and Products. The remaining control-center surfaces (Cases, Kanban, Inspector Assignment, Audit Logs, RBAC, Manufacturer Management, the regional map, and the "Open Cases" KPI) have **no backend** and are rendered from a clearly isolated, clearly labelled demo data source. The design's central jobs are: (a) define the admin-only shell/table/kanban/chart/map widgets composed from shared atoms; (b) lock the route table and the live-vs-mock boundary; (c) carry the existing working Supabase queries forward into a testable repository + Riverpod seam without regressing them; and (d) guarantee mock data is never presented as live.

The output is concrete enough that a planner can order the build without making further architecture decisions. The technology stack in §2 is locked once this design is approved.

---

## 2. Technology stack (LOCKED)

| Concern | Choice | Notes |
| --- | --- | --- |
| UI framework | Flutter, Material 3 under `VeriqooTheme` | Dark scheme is primary (`VeriqooTheme.dark`). |
| Dart SDK | `^3.13.3` (admin_web current) | Unchanged. |
| Routing | `go_router: ^18.0.2` | `MaterialApp.router` + a single `ShellRoute`. Already in `pubspec.yaml`. |
| State management | `flutter_riverpod: ^3.4.3` | `ProviderScope`, `FutureProvider`, `NotifierProvider`. **No** codegen. Already in `pubspec.yaml`. |
| Data / backend | `supabase_flutter: ^2.17.2` (direct dependency, pinned to match `shared_core`) | Admin performs **reads only**, wrapped in repositories. Declared **directly** (not relied on transitively) because admin files import `package:supabase_flutter/...` directly; without the declaration `depend_on_referenced_packages` fires under `flutter_lints`. See §18. |
| Charts & map | Bespoke `CustomPainter` widgets | **No** `fl_chart`. Justified in §7. |
| Icons | `VeriqooIcons` + admin-local `AdminIcons` facade | `AdminIcons` is the **only** admin file importing `lucide_icons_flutter`; add it as a direct dep pinned `^3.1.21` to match `shared_core`. The "no direct lucide import" constraint is satisfied by the **single-importer-facade** interpretation — the governing decision is stated and justified in §12 (R3·#3). |
| Config | `flutter_dotenv` (`.env`) | Carried forward from current `main.dart`. |
| Design system | `package:shared_core/design_system/design_system.dart` | Read-only barrel. |

Non-goals for this phase (see §16 Out of scope): authentication, server-side RLS enforcement, writing to Supabase from admin, light-theme toggle, real backends for Cases/Audit/RBAC/Manufacturers.

---

## 3. Ground truth from the codebase

### 3.1 Shared design system (verified names — consume, do not modify)

- Barrel import: `package:shared_core/design_system/design_system.dart`.
- Tokens via `Theme.of(context).extension<VeriqooTokens>()!`. Fields: `brightness, bg, bgTrue, surface, surfaceRaised, borderHairline, borderStrong, textPrimary, textSecondary, textTertiary, inverseBg, inverseText`. Two schemes: `VeriqooTokens.dark` (primary), `VeriqooTokens.light`.
- Primitive ramp `VeriqooColors`: `black, deepBlack, charcoal, graphite, borderStrongDark, midGrey, lightGrey, borderGrey, offWhite, white`. Monochrome only — no accent hue exists.
- Type `VeriqooType` (color is null; widgets apply token color): `display, h1, h2, h3, bodyL, body, caption, meta` (small-label style — letter-spaced, but it does **not** transform text, so admin call sites that use raw `meta` must `.toUpperCase()` themselves, per N4), `mono` (IBM Plex Mono, `FontFeature.tabularFigures()` — use for all IDs/numbers/dates/counts so columns align).
- Spacing `VeriqooSpacing`: `s4 s8 s12 s16 s24 s32 s48 s64 s80 s96`. No arbitrary values.
- Radius `VeriqooRadius`: `none(0) sm(6) md(10) lg(20)` + `noneAll smAll mdAll lgAll` + `top(r)`. Tables, panels, technical surfaces, status chips use **`none`** (square).
- Elevation `VeriqooElevation`: `softShadow` (nav/modal only) and `translucentSurface`. **Prefer hairline borders over shadows everywhere else.**
- Motion `VeriqooMotion`: `fast(160) base(240) slow(320) cinematic(700)`, curves `enter/move/press`, `pressSpring`, and `reduceMotion(context)` — every sweeping/looping animation (charts count-up, scanning markers, panel slide) must resolve to a static end state when it returns true.
- Theme `VeriqooTheme.dark` / `.light` builds `ThemeData` with the tokens extension, Inter font, Material tint disabled.

**Verified atom constructors** (compose these; do not re-skin by hand):

- `VeriqooButton({required label, onPressed, variant: primary|secondary|ghost, size: small(44)|medium(48)|large(56), icon, loading, expand, semanticLabel})`.
- `VeriqooIconButton({required icon, required semanticLabel, onPressed, variant: ghost|outline, iconSize=20, size=44})`.
- `VeriqooTextField({controller, label, hintText, helperText, errorText, obscureText, keyboardType, textInputAction, enabled, onChanged, onSubmitted, focusNode, prefixIcon, suffixIcon})` — hairline underline that strengthens on focus; label is uppercased.
- `VeriqooStatus({required kind: verified|flag|missing|violation, markerSize=16, showLabel=true})` — meaning encoded by **shape + glyph + label**, never color. Labels: `VERIFIED / FLAG / NOT DETECTED / VIOLATION`.
- `VeriqooScore({required value, maxValue=100, size=120, strokeWidth=6, duration, caption})` — monochrome radial dial, mono readout, honors reduced motion.
- `VeriqooDivider({height, indent, endIndent})` and `VeriqooDivider.vertical({...})` — hairline.
- `VeriqooSectionHeader({required title, action, subtitle})` — uppercase meta label with optional trailing action.
- `VeriqooEmptyState({required icon, required title, message, action})`.
- `VeriqooErrorState({title, message, onRetry, retryLabel, icon})` — defaults to a retry button when `onRetry` is set.
- `VeriqooModal({required title, required child, actions, showClose})` + static `VeriqooModal.show<T>(context, {title, child, actions, showClose, barrierDismissible})` — centered, maxWidth 420, md radius, the one permitted soft shadow.
- `VeriqooBottomSheet` — mobile-oriented; **not used** in admin (right detail panel replaces it on desktop).
- `VeriqooAppBar`, `VeriqooNavigationBar` (mobile floating nav), `VeriqooInspectionCard`, `VeriqooLoading`, `VeriqooScannerOverlay` — **not used** in admin per the shell requirement; admin builds its own desktop chrome from tokens + atoms.

`VeriqooIcons` facade currently exposes only: `home, scan, history, profile, back, close, chevronRight, settings, search, check, alert, verified, violation, camera, upload`. This is insufficient for admin navigation and toolbars → see the `AdminIcons` plan in §12.

### 3.2 Existing admin screens (preserve behavior, reskin surface)

Files: `C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web\lib\main.dart`, and under `C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web\lib\screens\dashboard\`: `dashboard_screen.dart`, `inspections_screen.dart`, `inspection_details_screen.dart`, `products_screen.dart`.

What they do today (the working data wiring to carry forward):

- `main.dart`: `WidgetsFlutterBinding.ensureInitialized()` → `dotenv.load('.env')` → read `SUPABASE_URL` + `SUPABASE_ANON_KEY`/`SUPABASE_KEY` → `Supabase.initialize(url:, publishableKey:)` → `runApp`. Throws `StateError` if env missing. `MaterialApp` with named routes `/`, `/inspections`, `/products` and a bespoke blue/green `ColorScheme.fromSeed` theme (to be removed).
- Data access is **direct** `Supabase.instance.client.from('inspections')` in each screen. The shared `SupabaseService` (`C:\WorkSpace\Ajinkya\Veriqoo\packages\shared_core\lib\services\supabase_service.dart`) only exposes **writes** (`saveInspectionReport`, `uploadInspectionImage`, `testConnection`) — it has no read API the admin can reuse, so the admin's reads must live in admin-side repositories (§6). `SupabaseService` is left untouched and remains the write path used by the capture apps.
- `dashboard_screen.dart`: five parallel queries via `Future.wait` — total count, compliant count (`is_compliant = true`), violation count (`is_compliant = false`), recent 50 (`order inspected_at desc`), and a 30-day analytics pass (`inspected_at >= now-30d`) that buckets by day into a compliance-rate trend and tallies `possible_issues` into top-violation counts. Compliance rate = `compliant/total`.
- `inspections_screen.dart`: count + 200 rows (`order inspected_at desc, limit 200`), then **client-side** search (product/manufacturer substring) + status filter (`All|Compliant|Violation`) + client paging of 10. Row action → `InspectionDetailsScreen(inspection: row)`.
- `products_screen.dart`: 500 rows grouped in memory by `product_name|manufacturer` into product aggregates (inspection count + summed issue count + latest row); same search/filter/paging; action → details of the latest inspection.
- `inspection_details_screen.dart`: pure presentation of one `Map<String,dynamic>` row — Product Information grid, Information Missing, Possible Issues, AI Compliance Report, Product Image (with graceful image-unavailable fallback). No network.
- Shared helper `issueCount(possible_issues)`: JSON-array length, else `1` for non-empty text, else `0` — tolerant of malformed JSON (never throws).

### 3.3 The one live table: `public.inspections`

The admin's only live source is a **flat** `public.inspections` table. It is **not** in `C:\WorkSpace\Ajinkya\Veriqoo\final_schema.sql` nor in the committed migrations (the Phase 8B migration `C:\WorkSpace\Ajinkya\Veriqoo\supabase\migrations\20261004000000_phase8b_inspection_persistence.sql` defines a different, normalized `inspection_sessions/_images/_ocr_observations/_evidence/_requirement_results/_reports` set that admin does **not** use). The flat table is written by `shared_core` `SupabaseService.saveInspectionReport` and the Python backend. Its columns, as used by the live queries and the insert, are:

| Column | Type (observed) | Admin usage |
| --- | --- | --- |
| `product_name` | text | table/detail title, search |
| `mrp` | text (e.g. `Rs.120`) | detail, table |
| `net_quantity` | text (e.g. `200 g`) | detail, table |
| `manufacturer` | text | search, product grouping |
| `address` | text (often contains a state name) | detail |
| `packing_date` | text | detail |
| `customer_care` | text | detail |
| `missing_information` | text or jsonb array of strings | detail, status nuance |
| `possible_issues` | jsonb array of issue objects, or text | violation counts, detail |
| `is_compliant` | boolean | KPIs, status chip, filter |
| `ocr_text` | text | not surfaced |
| `ai_report` | jsonb (`ComplianceAnalysis.toJson`) | detail (AI report) |
| `inspected_at` | timestamptz | ordering, charts, dates |
| `image_url` | text | detail image |

There is **no** stable row id in the current `select`, **no** VRQ id, **no** normalized location/state, **no** priority / case status / assigned inspector / created / last-updated columns. Everything the control center needs beyond the table above is therefore mock-backed (§8). The `ComplianceAnalysis`/`ComplianceIssue` models in `C:\WorkSpace\Ajinkya\Veriqoo\packages\shared_core\lib\services\compliance_analysis.dart` are the real shapes behind `ai_report`/`possible_issues` and are reused for parsing in the detail screen and for mock fixtures.

**Deep-link assumption (A1):** the flat table almost certainly has a default primary key `id`, but it is not currently selected and cannot be confirmed from the repo. The design does not block on it — see the detail-route fallback in §5.3.

---

## 4. Decision 1 — Shell layout and admin widget set

### 4.1 Shell anatomy

A single `AdminShell` composes four regions and is used as the `builder` of the go_router `ShellRoute`, so navigating between screens never rebuilds the chrome:

```
┌───────────────────────────────────────────────────────────────┐
│  AdminTopBar (64)  breadcrumb/title · global search · actions   │
│                    (notifications/profile omitted — §4.2)       │
├──────────┬────────────────────────────────────┬────────────────┤
│          │                                     │                │
│ Admin    │   MAIN WORKSPACE (routed child)     │  AdminDetail   │
│ Sidebar  │   scrolls independently             │  Panel         │
│ (248/72) │                                     │  (optional,    │
│          │                                     │   360–420)     │
└──────────┴────────────────────────────────────┴────────────────┘
```

- Background: `tokens.bg` (deep black `#0A0A0A` in dark). Sidebar and top bar sit on `tokens.surface` (`#111111`) separated from the workspace by `VeriqooDivider` hairlines — **no drop shadows** on the chrome.
- The sidebar is persistent (never a floating mobile bar). The shared `VeriqooNavigationBar` is explicitly **not** used.
- **Detail-surface rule (exactly one mechanism per interaction — resolves M2).** A *deep-linkable full record* is a **route** rendered inside the MAIN WORKSPACE; in Phase 11 the only such record is Inspection Details (`/inspections/:id`). It is **never** shown in the right panel. *Contextual / secondary detail* — a manufacturer or a case — opens in the **right `AdminDetailPanel`**, driven by shell-level state. The panel docks on wide screens, overlays on medium, and becomes a full-screen admin overlay on narrow (§8). It is **never** a route, and no single row/card interaction ever uses both a route and the panel.
  - **Payload + provider type (R3·#6).** The panel state is a sealed union `AdminDetailPayload` with two factory constructors — `AdminDetailPayload.manufacturer(Manufacturer m)` and `AdminDetailPayload.caseRecord(CaseRecord c)` — each carrying the in-memory **object reference** (never an id). The controller is `DetailPanelController extends Notifier<AdminDetailPayload?>`, exposed as `final detailPanelProvider = NotifierProvider<DetailPanelController, AdminDetailPayload?>(DetailPanelController.new)`; initial/`null` state means the panel is closed.
  - **Typed open/close API (R3·#6).** Dart has no method overloading, so the controller exposes two named methods — `void showManufacturer(Manufacturer m)` and `void showCase(CaseRecord c)`, each setting state to the matching factory — plus `void close()` (sets state back to `null`). Screens call `ref.read(detailPanelProvider.notifier).showCase(record)` or `.showManufacturer(m)`; they never build the payload inline. (There is deliberately no generic `show(payload)` — the earlier §4.1 wording that implied one is superseded by these two methods.)
  - **Responsibility split (R3·#6).** `AdminShell` `watch`es `detailPanelProvider` and `switch`es over the sealed payload to produce a `(String title, Widget child)` pair — a `_ManufacturerDetailView` or a `_CaseDetailView`. `AdminDetailPanel` is **dumb chrome**: it renders only the passed `title`, `child`, and close button plus the slide/overlay container, and has no knowledge of `Manufacturer`/`CaseRecord`. This keeps the panel reusable and unit-testable with a stub child.

### 4.2 Admin widgets to build (all under `C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web\lib\widgets\`)

Composed strictly from `VeriqooTokens`/`VeriqooType`/`VeriqooSpacing`/`VeriqooRadius` + the atoms above. No raw hex except inside `CustomPainter`s, which receive token colors as constructor params (never hardcoded).

Shell (`widgets/shell/`)
- `admin_shell.dart` — `AdminShell({required Widget child})`; lays out sidebar + top bar + workspace + optional detail panel; owns breakpoint logic (§6) and reads the active location from `GoRouterState.of(context).uri`.
- `admin_sidebar.dart` — `AdminSidebar`, `AdminNavSection(title)`, `AdminNavItem({icon, label, route, isMock})`. Active item: inverse-fill marker (`tokens.inverseBg`/`inverseText`) or a strong left hairline bar + `textPrimary` label; inactive uses `textSecondary`. Mock destinations carry an inline `DEMO` tag (see `AdminMockBadge`, §8). Collapses to a 72px icon rail (labels become tooltips) below 1024.
- `admin_top_bar.dart` — `AdminTopBar({title, breadcrumb, actions})`. Composes `AdminBreadcrumb`, the **global Inspections quick-search**, and the per-screen `actions` (e.g. refresh/export `VeriqooIconButton`s passed in by each screen). 64px tall, hairline bottom border.
  - **Global search behavior (R3·#2) — one defined target: Inspections.** The field is a `VeriqooTextField(prefixIcon: VeriqooIcons.search)` bound to `inspectionsSearchProvider` (a `NotifierProvider<String>`, §6.1). On submit (`onSubmitted`) it writes the trimmed term to that provider and calls `context.go('/inspections')`; the Inspections toolbar's own search field binds to the **same** provider, so the term arrives pre-seeded and drives the existing client-side product/manufacturer `contains` filter over the ≤200 fetched rows. It is intentionally **scoped to Inspections** (the live, searchable table) — Phase 11 has no shared cross-entity index across inspections/products/cases, so a truly "global" search is not feasible and is listed out of scope (§16). The control stays enabled on every route because its action is always well-defined (jump-to-Inspections-search), never a no-op; an empty submit just navigates to `/inspections` with no filter. Validation in §15.
  - **Notifications / help / profile (R3·#15):** **omitted** in Phase 11. With no auth and no user/notification source they would have no behavior, so the top bar ships without them, consistent with the §13 no-auth posture. The `actions` slot carries only per-screen, well-defined controls (refresh, export). These affordances return, with real backing, if a later phase adds Supabase Auth (§13).
- `admin_breadcrumb.dart` — `AdminBreadcrumb(List<AdminCrumb>)` using `VeriqooType.meta` + `VeriqooIcons.chevronRight` separators. Crumb text is `.toUpperCase()`d at this call site — `VeriqooType.meta` does **not** auto-uppercase (N4).
- `admin_detail_panel.dart` — `AdminDetailPanel({required String title, required Widget child, required VoidCallback onClose})`; **dumb chrome only** — renders the `title`, the `child`, and a close button, and owns the slide/overlay container. It does **not** know about `Manufacturer`/`CaseRecord`; `AdminShell` maps the `AdminDetailPayload` → `(title, child)` and passes them in (§4.1, R3·#6). Slide-in from right using `VeriqooMotion.move` (static when `reduceMotion`), hairline left border, `VeriqooIconButton(icon: VeriqooIcons.close, semanticLabel: 'Close', onPressed: onClose)` header. On narrow (<768) the same `title`+`child` are presented as a full-screen **admin-local `Dialog`** (built from tokens, shown via `showGeneralDialog`) — **not** the shared `VeriqooModal` atom (capped at `maxWidth: 420`, read-only) and **not** a route (N1, §8).

Data table (`widgets/data_table/`)
- `admin_data_table.dart` — generic `AdminDataTable<T>({required rows, required columns, sort, onSortChanged, onRowTap, density})`.
- `admin_data_column.dart` — `AdminDataColumn<T>({required key, required label, required Widget Function(T) cell, bool numeric=false, bool sortable=false, double? width, int flex=1, Comparable Function(T)? sortValue})`. The `key` + `sortable` set the **allowlist** of legal sort columns (invariant, §11).
- `admin_table_toolbar.dart` — search field + filter chips + density/column controls; emits callbacks only (stateless).
- `admin_pagination.dart` — `AdminPagination({page, pageCount, pageSize, onPageChanged, onPageSizeChanged})` with mono page readout.

Kanban (`widgets/kanban/`)
- `admin_kanban_board.dart` — `AdminKanbanBoard({required columns, onCardMoved})`; horizontally scrollable column set.
- `admin_kanban_column.dart` — `AdminKanbanColumn({title, count, children})`; header is a `VeriqooSectionHeader` with a mono count.
- `admin_kanban_card.dart` — `AdminKanbanCard({required CaseRecord})`; square hairline card with VRQ id (mono), product, manufacturer, `AdminPriorityIndicator`, and assignee.

Charts & map (`widgets/charts/`, `widgets/map/`) — all `CustomPainter` (§7)
- `admin_line_chart.dart` — `AdminLineChart({required List<ChartPoint> series, String? caption, ChartAxis axis})` for inspection-activity and violation-trend.
- `admin_donut.dart` — `AdminDonut({compliant, nonCompliant})` compliance split (shape/label-coded, not color-coded).
- `admin_bar_mini.dart` — small horizontal bars for top-violation counts; **placed on the Dashboard "Top Violations" panel** (§10.1, R3·#8).
- `chart_axis.dart` — pure helpers converting data → offsets, grid lines, mono tick labels.
- `map/admin_region_map.dart` — `AdminRegionMap({required List<RegionDensity> regions})`; monochrome **bounded graticule placeholder** (no India-outline asset in Phase 11 — §6.5/N8) + density markers.
- `map/admin_view_toggle.dart` — `AdminViewToggle({current: list|kanban|map, onChanged})` segmented control built from `VeriqooButton`/`VeriqooIconButton`.

Common (`widgets/common/`)
- `admin_panel.dart` — `AdminPanel({child, padding})`: the monochrome successor to the old `_Panel` — `tokens.surface`, `VeriqooRadius.noneAll` (square, technical), 1px `tokens.borderHairline`, no shadow.
- `admin_kpi_card.dart` — `AdminKpiCard({label, value, caption, trend, isMock})`: label `.toUpperCase()`d in `VeriqooType.meta`; value rendered as `VeriqooType.mono.copyWith(fontSize: 24, fontWeight: FontWeight.w500)` — a single merged style (mono family at the 24px h2 size), not two named styles, since a `Text` carries only one `style` (N4). **Weight is `w500`, not `w600` (R3·#17):** `shared_core` bundles IBM Plex Mono only in 400 and 500 (verified in `shared_core/pubspec.yaml` — `IBMPlexMono-Regular.ttf` @400, `IBMPlexMono-Medium.ttf` @500) and mono is not a variable font, so a `w600` request would fall back to ~500 or faux-bold; `VeriqooScore` already uses `w500` for its mono readout, so `w500` matches the system and renders a true bundled weight. The `trend` glyph is optional and shape-coded (`AdminIcons.trendUp`/`trendDown`, never red/green); **in Phase 11 every KPI passes `trend: null`** because no query computes a period-over-period delta (R3·#9) — the parameter stays for a future phase that adds trend data. See §10.1.
- `admin_status_cell.dart` — maps the **live inspection** status enum to `VeriqooStatus(kind: VeriqooStatusKind.…)` (§6.4). Used only where the verification labels (`VERIFIED / FLAG / NOT DETECTED / VIOLATION`) are domain-correct, i.e. inspections and products — **not** RBAC or system status (N3).
- `admin_permission_cell.dart` — `AdminPermissionCell({required bool granted})` for the RBAC matrix: shape-coded (filled square = granted, hollow dashed square = denied) wrapped in `Semantics(label: granted ? 'granted' : 'denied')`. Does **not** reuse `VeriqooStatus` or its verification labels (N3).
- `admin_health_indicator.dart` — `AdminHealthIndicator({required ServiceHealth health})` for mock system-status rows: shape-coded marker + domain label (`OPERATIONAL / DEGRADED / OFFLINE`) + `Semantics`. Does **not** reuse the verification labels (N3).
- `admin_priority_indicator.dart` — `AdminPriorityIndicator(CasePriority)`: shape + label (e.g. hollow square = low, half = medium, filled = high, filled+ring = critical), never hue.
- `admin_tag.dart` — small square hairline tag used for `DEMO`, counts, categories; `.toUpperCase()`s its own text because raw `VeriqooType.meta` does not (N4).
- `admin_mock_badge.dart` — the persistent `DEMO DATA` marker (§8).
- `admin_section_card.dart` — titled `AdminPanel` with a `VeriqooSectionHeader`.

---

## 5. Decision 2 — Information architecture and route table

### 5.1 Sidebar IA

| Section (meta label) | Items (route) | Backing |
| --- | --- | --- |
| OVERVIEW | Dashboard (`/dashboard`) | LIVE + mock supplements |
| COMPLIANCE | Inspections (`/inspections`), Cases (`/cases`), Inspector Assignment (`/assignments`) | LIVE / MOCK / MOCK |
| CATALOG | Products (`/products`), Manufacturers (`/manufacturers`) | LIVE / MOCK |
| GOVERNANCE | Audit Logs (`/audit`), Access Control (`/rbac`) | MOCK / MOCK |

### 5.2 Route table (go_router)

Single `GoRouter` created by `createAdminRouter()` in `C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web\lib\app\admin_router.dart`, `initialLocation: '/dashboard'`, one `ShellRoute(builder: (_, __, child) => AdminShell(child: child))`.

| Path | Screen widget | File | Backing | Notes |
| --- | --- | --- | --- | --- |
| `/` | — | — | — | `redirect` → `/dashboard` |
| `/dashboard` | `DashboardScreen` | `screens/dashboard/dashboard_screen.dart` | **LIVE** KPIs(3)+charts; **MOCK** open-cases KPI, region map, recent cases, system status | hybrid, clearly tagged |
| `/inspections` | `InspectionsScreen` | `screens/inspections/inspections_screen.dart` | **LIVE** | dense sortable/filterable table |
| `/inspections/:id` | `InspectionDetailsScreen` | `screens/inspections/inspection_details_screen.dart` | **LIVE** | row via `extra`; cold-load fallback §5.3 |
| `/products` | `ProductsScreen` | `screens/products/products_screen.dart` | **LIVE** | grouped from inspections |
| `/manufacturers` | `ManufacturerManagementScreen` | `screens/manufacturers/manufacturers_screen.dart` | **MOCK** | DEMO |
| `/cases` | `CaseManagementScreen` | `screens/cases/cases_screen.dart` | **MOCK** | `?view=list\|kanban\|map` (default `list`). Case detail opens in the right `AdminDetailPanel`, **not** a route (M2, §10.5) |
| `/assignments` | `InspectorAssignmentScreen` | `screens/assignments/assignments_screen.dart` | **MOCK** | DEMO |
| `/audit` | `AuditLogsScreen` | `screens/audit/audit_logs_screen.dart` | **MOCK** | DEMO; chronological table |
| `/rbac` | `RbacScreen` | `screens/rbac/rbac_screen.dart` | **MOCK** | DEMO; roles × permissions matrix |

- `errorBuilder` → full-workspace `VeriqooErrorState(title: 'Page not found', onRetry: () => context.go('/dashboard'))`.
- The Cases view mode is a **query parameter** (`?view=kanban`), not a nested route, so the list/kanban/map toggle is deep-linkable and preserves the shell. Invalid `view` values fall back to `list`.
- Legacy named routes (`/`, `/inspections`, `/products`) are superseded by the go_router paths; `main.dart` switches to `MaterialApp.router`.

### 5.3 Inspection detail navigation (concrete)

- **Web URL strategy (R3·#13):** `main()` calls `usePathUrlStrategy()` (from `package:flutter_web_plugins/url_strategy.dart`) so go_router routes render as clean paths (`/inspections/123`) rather than hash-fragment URLs. This is a deliberate choice over the default hash strategy so the cold-load / shared-link / reload paths described below produce human-readable, server-routable URLs. It is a `main.dart`-only change, inside the write scope (§18).
- From the Inspections/Products table, row tap calls `context.go('/inspections/${id ?? "row"}', extra: rowMap)`. The screen reads `GoRouterState.extra` first and renders immediately (preserves today's exact behavior — passing the whole row map).
- **Cold load / refresh** (web reload, shared link) has no `extra`. The screen then watches `inspectionByIdProvider(id)`:
  - If assumption A1 holds (table has `id`, repo adds `id` to the select), it re-fetches the row and renders.
  - If `id` is unavailable (no `id` column, or no matching row), `inspectionById` **catches the error and returns null** (§6.1, R3·#10) — it does not surface a raw `AsyncError` — and the screen shows `VeriqooErrorState(title: 'Inspection not available from a direct link', onRetry → context.go('/inspections'))`. This is a graceful, non-blocking fallback; deep-linkable details are a documented enhancement, not a Phase 11 requirement.

---

## 6. Decision 3 — Data access, data table, kanban, map

### 6.1 Repository + Riverpod seam (carry the working queries forward)

All live reads move verbatim (same table, columns, filters, limits, ordering) into injectable repositories under `C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web\lib\data\`. This is the key testability lever: repositories accept an optional `SupabaseClient` (mirroring `SupabaseService`'s constructor) so unit tests inject a fake, and providers are overridable in `ProviderScope`.

- `data/supabase_providers.dart`
  - `supabaseClientProvider` → `Supabase.instance.client`.
- `data/inspections_repository.dart` — `InspectionsRepository({SupabaseClient? client})`
  - `Future<DashboardMetrics> dashboardMetrics()` — the three counts (total, `is_compliant=true`, `is_compliant=false`) via `Future.wait`, exactly as today. `DashboardMetrics` exposes a `double get rate => total == 0 ? 0 : compliant / total;` — the `total == 0 → 0` guard is carried forward from today's `_DashboardData.rate`/`_RiskPainter` so an empty table never divides by zero (N5). The internal `Future.wait` over the three counts is scoped **inside this method only**: a count failure surfaces as `dashboardDataProvider`'s `AsyncError` and blanks **only the KPI row**, never the charts or Recent Inspections (R3·#1, §14).
  - `Future<List<InspectionRow>> recentInspections({int limit = 50})` — `order inspected_at desc`. **Consumed by the Dashboard's LIVE "Recent Inspections" panel** via `recentInspectionsProvider` (§10.1), carrying forward today's `_recent()` surface — it is not an orphaned query (M3).
  - `Future<InspectionAnalytics> analytics({int days = 30})` — buckets the 30-day window by day; returns `dailyTotals`, `dailyCompliant`, `dailyViolations`, and top-violation tallies from `possible_issues`. **`dailyViolations` is defined precisely as the per-day count of rows with `is_compliant == false`** — the same predicate as the Violations KPI (A4), so `is_compliant == null` and `== true` are **not** counted and the violation-trend chart can never disagree with the KPI (R3·#5). Pure aggregation logic (including this predicate and the `null` case) lives in `data/analytics_math.dart` and is unit-tested, with an explicit test that a `null`-`is_compliant` row contributes to `dailyTotals` but not to `dailyViolations`.
  - `Future<InspectionsPage> inspectionsPage(...)` — count + up to 200 rows (today's semantics). Filtering/sorting/paging stay **client-side** in Phase 11 to preserve current behavior and avoid new query-injection surface; a server-side `ilike`/`range` path is noted as a future enhancement (would use the Supabase client's parameterized `ilike`, never string interpolation).
  - `Future<InspectionRow?> inspectionById(String id)` — best-effort per A1/§5.3. The `.eq('id', id)` select runs inside a `try`, and the method **returns `null`** on any failure: a `PostgrestException` (including Postgres `42703` "column does not exist" when A1 is false), a not-found / zero-row result (via `.maybeSingle()`), or a parse error. This guarantees the §5.3 `VeriqooErrorState` fallback is what the screen sees, rather than a generic `AsyncError` leaking through (R3·#10). A missing-`id`-column failure is logged once at `info` (an absent `id` is an expected schema shape under A1, not a fault); other failures log at `warning`.
- `data/products_repository.dart` — `ProductsRepository({SupabaseClient? client})` → `Future<List<ProductAggregate>> groupedProducts({int limit = 500})` reproducing the in-memory grouping.
- Providers in `data/providers.dart`: **three independent Dashboard providers** — `dashboardDataProvider` (`FutureProvider<DashboardMetrics>`, the KPI counts), `recentInspectionsProvider` (`FutureProvider<List<InspectionRow>>`, the LIVE Recent Inspections panel — §10.1, M3), and `inspectionAnalyticsProvider` (`FutureProvider<InspectionAnalytics>`, feeding both charts and the Top Violations panel) — each **loads, errors, and retries independently** so a failure in one never blanks the others (R3·#1, §14). Plus `inspectionsPageProvider` and `productsProvider`. UI state via small `NotifierProvider`s: `inspectionsSearchProvider` (`NotifierProvider<String>`, bound by **both** the top-bar global search and the Inspections toolbar so they share one term — §4.2, R3·#2), status filter, sort spec, page, pageSize, and cases view mode; and the right-panel `detailPanelProvider` (`NotifierProvider<DetailPanelController, AdminDetailPayload?>` — the sealed `.manufacturer`/`.caseRecord` payload, or `null` when closed — §4.1, M2, R3·#6). Keeping these as providers keeps widgets stateless and testable.
- Typed row models in `C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web\lib\models\`: `InspectionRow` (wraps the raw map with typed getters + `fromMap`), `DashboardMetrics`, `InspectionAnalytics`, `ProductAggregate`. These replace the loose `Map<String,dynamic>` passing while keeping `fromMap` tolerant of nulls/legacy JSON (carry forward the tolerant `issueCount`).

### 6.2 Dense data table pattern

`AdminDataTable<T>` renders a header row of `AdminDataColumn`s and body rows on `AdminPanel` (square, hairline row separators via `VeriqooDivider`, `VeriqooSpacing.s12` vertical cells, `density` toggle switches to `s8`). Numbers/IDs/dates use `VeriqooType.mono`; text uses `VeriqooType.body` with `TextOverflow.ellipsis`. Column headers that are `sortable` show a sort glyph (`AdminIcons.sortAsc/sortDesc/sort`) and toggle `asc → desc → none`. Below the min table width the table scrolls horizontally inside the panel with the first column pinned. Loading → shimmer/`VeriqooLoading`-free skeleton rows (static under reduced motion); empty → `VeriqooEmptyState`; error → `VeriqooErrorState`. The table is presentation-only: it receives already-filtered/sorted/paged rows plus the sort spec and emits `onSortChanged`/`onRowTap`.

### 6.3 Kanban pattern

`AdminKanbanBoard` renders one `AdminKanbanColumn` per `CaseStatus` in a fixed order: `NEW → TRIAGE → ASSIGNED → IN PROGRESS → RESOLVED → CLOSED`. Each column lists `AdminKanbanCard`s for its cases with a mono count in the header. Drag-and-drop (Flutter `Draggable`/`DragTarget`) updates the **in-memory mock store** only (`onCardMoved` mutates the `MockCasesRepository` notifier); because cases are mock, moves are session-local and reset on reload — the DEMO badge makes this explicit. Columns scroll horizontally when they exceed viewport width; each column body scrolls vertically.

### 6.4 Status / priority mapping (shape, never color)

- Live inspection → `VeriqooStatus`: `is_compliant == true` → `verified`; `is_compliant == false` with ≥1 `possible_issues` → `violation`; `is_compliant == false` with only `missing_information` → `flag`; **`is_compliant == null`, or an unreadable/empty analysis → `missing`** (NOT DETECTED). `null` is deliberately neither `verified` nor `violation`: it is not `== true` and not `== false`, so it falls through to `missing` (R3·#14). Centralized in `models/status_mapping.dart` (pure, unit-tested, with a dedicated test asserting `null → missing`).
- Mock case priority → `AdminPriorityIndicator` shapes (low/medium/high/critical) as described in §4.2. Case status → `AdminTag` label; kanban column membership is the primary signal.

### 6.5 Map view

For Phase 11 `AdminRegionMap` paints a **bounded graticule placeholder** — a hairline lat/long grid framing the mock markers within a fixed bounding box. **No India-outline asset ships in Phase 11** (the map is MOCK/DEMO); a real normalized India-outline `Path`/vector asset is a documented future enhancement (§16) and is the only thing that would change this widget's background (N8). On top of the graticule it paints per-state density markers: marker radius/opacity scales with inspection volume, a hairline ring encodes violation share, and a mono label shows counts. It is fed by `mock_regions.dart` (see A2 in §8) and headlined by Maharashtra 1,284 inspections / 86 violations. The map carries a `DEMO DATA` badge because regional breakdown is not in the live table. **The Cases map view (§10.5) binds to this very same `mock_regions.dart` `List<RegionDensity>`** (badged DEMO), **not** to the `CaseRecord` list: `AdminRegionMap` consumes `RegionDensity`, not `CaseRecord`, and because cases are themselves mock a `CaseRecord.location → RegionDensity` aggregation adds no fidelity in Phase 11, so it is deferred (§16). This gives the "map" toggle a concrete, unambiguous data source (R3·#7).

---

## 7. Decision 4 — Monochrome chart strategy: bespoke CustomPainter (CHOSEN)

**Options considered.** (a) `fl_chart` rendered in greyscale. (b) Bespoke `CustomPainter` chart widgets.

**Choice: (b) bespoke `CustomPainter`.** Reasons:

1. **Zero new dependency / smaller surface.** `fl_chart` is not currently a dependency; adding it to a strictly monochrome, hairline-over-shadow system means continuously overriding its colorful defaults, gradients, touch tooltips, and bar rounding to neutralize them — fighting the library instead of using it.
2. **Consistency with the system that already exists.** `VeriqooScore` is already a `CustomPainter` radial, the `painters/` directory is a first-class part of shared_core, and the current dashboard trend/donut are already `CustomPainter`s. We re-skin those proven painters to pull `tokens.textPrimary` (series), `tokens.borderHairline` (grid), and `tokens.textSecondary` (labels) instead of blue/green literals.
3. **Full control of the monochrome grammar.** Hairline grid at 1px, 1.5–2px series stroke, dotted/dashed secondary series to distinguish inspection-activity vs violation-trend **by texture, not color**, mono tabular tick labels that align, and reduced-motion compliance via `VeriqooMotion.reduceMotion` (count-up/draw-on animation collapses to the final frame).
4. **Testability.** Data→geometry transforms live in `chart_axis.dart` as pure functions (unit-tested); painters are thin and golden-tested.

Chart inventory: Dashboard inspection-activity (`AdminLineChart`, daily counts), violation-trend (`AdminLineChart`, daily non-compliance, dashed series), compliance split (`AdminDonut({compliant, nonCompliant})`), top-violations (`admin_bar_mini`). **Decision (N2):** the compliant/non-compliant *split* renders with `AdminDonut`; `VeriqooScore(value: ratePercent)` is **not** used on the Phase 11 dashboard — the Compliance Rate KPI card already shows the mono percentage, so a radial rate dial would duplicate it. `VeriqooScore` is reserved for a possible future single overall-rate dial only. All greyscale, hairlines, no fills heavier than a 10–15% tint, no drop shadows.

---

## 8. Decision 5 — Responsiveness

Admin is desktop-first; it degrades gracefully rather than optimizing for mobile. Breakpoints owned by `AdminShell` via `LayoutBuilder`:

| Width | Sidebar | Detail panel | KPI row | Dashboard charts | Tables |
| --- | --- | --- | --- | --- | --- |
| ≥ 1440 (large) | Expanded 248 | Docks persistently while a case/manufacturer is open | 4-up | side-by-side | full width |
| 1024–1439 (desktop) | Expanded 248 | Overlays (slide-in) while open | 4-up | side-by-side | full width |
| 768–1023 (compact) | Icon rail 72 (tooltips) | Overlays while open | 2×2 | stacked | horizontal scroll, pinned first col |
| < 768 (narrow, graceful) | Drawer via `AdminIcons.menu` in top bar | Full-screen admin-local `Dialog` (**not** the ≤420 `VeriqooModal` atom, **not** a route) | 1-col | stacked | horizontal scroll |

The right detail panel renders the same `AdminDetailPanel` payload (§4.1) at every breakpoint; only its container changes — a docked/overlaid side panel at ≥768, and a full-screen admin-local `Dialog` (via `showGeneralDialog`, built from `VeriqooTokens`) below 768. It never becomes the shared `VeriqooModal` atom and never a route. Kanban columns always scroll horizontally; the map scales to its container with min 320px height. The global search (an Inspections quick-search whose target is defined in §4.2/§15, R3·#2) collapses to a `VeriqooIconButton` that expands into an overlay field below 1024.

---

## 9. Decision 6 — Mock data isolation

Hard rule: **mock data is never presented as live.** Enforced structurally and visually.

Structure — everything mock lives under `C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web\lib\data\mock\` with a `Mock` prefix and a shared marker:
- `mock/admin_mock.dart` — `const bool kIsMockData = true;` + `AdminMockBadge` export + a `MockLatency` helper (`Future.delayed`) so mock repos exhibit realistic loading states through the same `AsyncValue` path as live data.
- `mock/mock_cases_repository.dart`, `mock/mock_inspectors_repository.dart`, `mock/mock_audit_repository.dart`, `mock/mock_rbac_repository.dart`, `mock/mock_manufacturers_repository.dart`, `mock/mock_regions.dart`, `mock/mock_dashboard_supplement.dart` (open-cases KPI, system-status rows, recent-cases list, region markers).
- Mock repositories implement the **same method shapes** as live repositories and are exposed through their own providers (`casesProvider`, `inspectorsProvider`, …). No mock type is ever referenced from a live repository and vice versa; the two never share a provider.
- `MockCasesRepository` seeds a fixed set of cases from a **deterministic seeded generator**, so every mock VRQ id matches `^VRQ-\d{8}-\d{4}$` (e.g. `VRQ-20261004-0182`) and is **stable across reloads** — ids shown in tables, kanban cards, and the detail panel stay consistent even though mutations (drag-moves, assignments) are session-local and reset on reload (N7). Because case detail is opened by handing the panel the in-memory `CaseRecord` object (no route, no id lookup — §10.5), the "pattern-valid id that does not exist after a cold load" problem cannot arise.

Visual — the `AdminMockBadge` (`DEMO DATA`, a square hairline `AdminTag` using `VeriqooType.meta`) appears:
- in the sidebar on every mock destination,
- in the top-bar context area whenever the active route is mock,
- in the header of every mock panel/section (including the Dashboard's open-cases KPI, region map, recent cases, and system status), and
- on each kanban card and map, since those surfaces are entirely mock.

Models (`C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web\lib\models\`): `CaseRecord`, `Inspector`, `AuditLogEntry`, `Role`, `Permission`, `Manufacturer`, `RegionDensity`, `SystemStatusRow`, with enums `CasePriority {low, medium, high, critical}`, `CaseStatus {new_, triage, assigned, inProgress, resolved, closed}`, and `ServiceHealth {operational, degraded, offline}` (drives `AdminHealthIndicator`, §10.1).

**Assumption A2:** regional density/markers and system-status health are illustrative fixtures (the live table has no normalized state column or service telemetry). Documented and badged DEMO; deriving regions from `address` text is a future enhancement.

---

## 10. Screen specifications

Every screen is a `ConsumerWidget`/`ConsumerStatefulWidget` rendered inside `AdminShell`. Each sets the top-bar title/breadcrumb and (when mock) shows the `AdminMockBadge`. Loading/empty/error states use `VeriqooLoading`-style skeletons / `VeriqooEmptyState` / `VeriqooErrorState` consistently.

### 10.1 Dashboard (`/dashboard`) — HYBRID
- **KPI row** (`AdminKpiCard` ×4): Total Inspections (LIVE total count), Compliance Rate (LIVE, `DashboardMetrics.rate` = `compliant/total` with the `total == 0 → 0` guard, shown as %, N5), Violations (LIVE non-compliant count), Open Cases (**MOCK**, badged). KPI values render as `VeriqooType.mono.copyWith(fontSize: 24, fontWeight: FontWeight.w500)` (N4, R3·#17 — `w500` is a bundled mono weight; `w600` is not). **All four pass `trend: null`** — no period-over-period delta is computed in Phase 11, so no card implies a trend that does not exist (R3·#9).
- **Charts**: Inspection Activity (`AdminLineChart`, LIVE daily counts, 30d) and Violation Trend (`AdminLineChart`, LIVE `dailyViolations` = daily `is_compliant == false` count, 30d, dashed — matches the Violations KPI, R3·#5). Compliance split via `AdminDonut({compliant, nonCompliant})` (LIVE); no `VeriqooScore` here (N2). **Deliberate presentation change (R3·#16):** today's dashboard draws a single per-day *compliance-rate* line; Phase 11 intentionally replaces it with these two activity/violation lines plus the compliance-split donut and the Compliance Rate KPI. The underlying 30-day aggregation and queries are preserved — rate is still shown (via the KPI and donut) — so this is a visualization change, not a data regression.
- **Top Violations** (**LIVE**) — `admin_bar_mini` horizontal bars of the top `possible_issues` tallies from `inspectionAnalyticsProvider` (the same analytics pass that feeds the charts). This **places the previously-computed-but-unplaced top-violation tally** (R3·#8) and shares the analytics provider, so it loads/errors/retries together with the charts as one analytics region.
- **Regional map** (`AdminRegionMap`, **MOCK**, badged) — Maharashtra 1,284 / 86 headline; bounded graticule placeholder (N8).
- **Recent Inspections** (**LIVE**) — compact `AdminDataTable<InspectionRow>` consuming `recentInspectionsProvider` (`recentInspections(limit: 50)`). This **preserves today's live recent-inspections surface** (the current `dashboard_screen.dart` `_recent()` table), not a regression to mock (M3).
- **Recent Cases** (**MOCK**, badged) — compact `AdminDataTable<CaseRecord>` of latest mock cases, sitting **beside** the live Recent Inspections panel so the live and demo surfaces are visibly distinct and separately badged.
- **System status** (**MOCK**, badged) — service rows with shape-coded health via `AdminHealthIndicator` (`OPERATIONAL / DEGRADED / OFFLINE`), never color and never the inspection verification labels (N3).
- **Data & independent loading (R3·#1).** The dashboard consumes three independent LIVE providers — `dashboardDataProvider` (KPI counts), `recentInspectionsProvider` (Recent Inspections), and `inspectionAnalyticsProvider` (both charts **and** Top Violations) — plus `mockDashboardSupplementProvider` (MOCK: open-cases KPI, region markers, recent cases, system status). Each LIVE provider renders its own `AsyncValue` into its own panel: a failure shows a **per-panel `VeriqooErrorState(onRetry → ref.invalidate(thatProvider))`** and **never blanks the other panels** — e.g. an analytics failure hides only the charts + Top Violations region, while the live KPI row and Recent Inspections stay up. Every panel is independently and separately badged so live and mock never blur.

### 10.2 Inspections (`/inspections`) — LIVE
- `AdminTableToolbar` (search product/manufacturer; status filter `All|Compliant|Violation`) + `AdminDataTable<InspectionRow>` columns: Product, MRP (mono), Net Qty (mono), Manufacturer, Inspected (mono date), Result (`AdminStatusCell` → `VeriqooStatus(kind: …)`), Violations (mono count), action. Sort allowlist: `product_name, mrp, net_quantity, manufacturer, inspected_at, is_compliant, violation_count`; default `inspected_at desc`. **MRP and Net Qty are free text (`"Rs.120"`, `"200 g"`); their `AdminDataColumn.sortValue` returns `parseFirstNumber(raw)` so they sort numerically rather than lexically (N5, R3·#4).** `parseFirstNumber` is defined as *the first numeric run — one or more digits with an optional single decimal point — found anywhere in the string* (not a strict leading-character parse, which would return `-1` for every `Rs.`-prefixed MRP): `"Rs.120" → 120`, `"200 g" → 200`, `"₹99.9" → 99.9`; a string with **no digit returns `-1`** so unparseable values sort to the bottom. Documented limitation, acceptable for Phase 11: mixed units are not normalized and thousands separators are not interpreted, so `"1 kg"` sorts below `"200 g"` by raw magnitude (1 < 200) — unit-aware sorting is a future enhancement (§16). `AdminPagination` (10/25/50; default 25). Row tap → `context.go('/inspections/:id', extra: row)`. Behavior (filter/sort/page) is client-side over the ≤200 fetched rows, preserving today's semantics.

### 10.3 Inspection Details (`/inspections/:id`) — LIVE
- Full record view in the workspace (not a modal), reusing today's sections: header (title + `VeriqooStatus` + inspected timestamp), Product Information grid (MRP, Net Qty, Manufacturer, Address, Packing Date, Customer Care), Information Missing, Possible Issues (parsed via `ComplianceIssue`), AI Compliance Report (`ai_report`), Product Image (graceful fallback). Back via breadcrumb/`AdminIcons`. Cold-load fallback per §5.3.

### 10.4 Products (`/products`) + Manufacturers (`/manufacturers`)
- Products (**LIVE**): `AdminDataTable<ProductAggregate>` grouped from inspections — Product, Manufacturer, Inspections (mono), Latest (mono date), Status (`VeriqooStatus`), Violations (mono). Row → latest inspection detail. Same toolbar/sort/paging pattern.
- Manufacturers (**MOCK**, badged): `AdminDataTable<Manufacturer>` — name, location, product count, open violations, risk indicator (shape-coded); row tap calls `ref.read(detailPanelProvider.notifier).showManufacturer(manufacturer)`, opening the **right `AdminDetailPanel`** with that `Manufacturer` object — **no route** (M2, §4.1, R3·#6). Pure mock CRUD affordances are visual-only (no persistence) and labelled DEMO.

### 10.5 Case Management (`/cases?view=list|kanban|map`) — MOCK (badged)
- `AdminViewToggle` switches view (query param). List = `AdminDataTable<CaseRecord>`; Kanban = `AdminKanbanBoard`; Map = `AdminRegionMap` **fed by the shared `mock_regions.dart` `List<RegionDensity>`** — the same DEMO fixture the Dashboard map uses — **not** by the `CaseRecord` list; the map and the case list are decoupled in Phase 11 (R3·#7, §6.5). Case fields: VRQ id (mono), product, manufacturer, location, issue, priority (`AdminPriorityIndicator`), status, assigned inspector, created, last-updated (mono dates).
- **Row/card tap opens the case in the right `AdminDetailPanel`** by calling `ref.read(detailPanelProvider.notifier).showCase(caseRecord)` with that in-memory `CaseRecord` object — **not** a route; there is no `/cases/:vrqId` (M2, R3·#6). Because the panel receives the object by reference, there is no id resolution or cold-load lookup, so no "unknown id" state exists (N7). VRQ ids are deterministic and reload-stable (§9); deep-linkable cases are deferred to the real cases backend (§16).

### 10.6 Inspector Assignment (`/assignments`) — MOCK (badged)
- Two-pane: unassigned/open cases list on the left, inspectors (`Inspector` cards with current load) on the right; assigning updates the in-memory mock store and reflects on the kanban. All session-local, DEMO.

### 10.7 Audit Logs (`/audit`) — MOCK (badged)
- Chronological `AdminDataTable<AuditLogEntry>` sorted `timestamp desc`: timestamp (mono), actor, role, action, target (VRQ/entity), result. Filter by actor/action/date range (client-side over fixtures).

### 10.8 RBAC (`/rbac`) — MOCK (badged)
- Roles list + a roles × permissions **matrix** whose cells are `AdminPermissionCell(granted: bool)` — shape-coded (filled square = granted, hollow dashed square = denied) with a `granted`/`denied` `Semantics` label. It does **not** use `VeriqooStatus` or its verification labels (`VERIFIED/FLAG/NOT DETECTED/VIOLATION`), which do not fit granted/denied (N3), and never encodes meaning by color. Toggles are visual-only and change nothing in the backend — the panel header states "Illustrative — not enforced" alongside the DEMO badge (ties to the security callout, §13).

---

## 11. Invariants and ownership

| Invariant | Owner / layer | Why there |
| --- | --- | --- |
| Monochrome only; status/priority never encoded by color | Shared atoms (`VeriqooStatus`) + admin rule: widgets resolve colors from `VeriqooTokens`; painters receive token colors as params | Single source of color truth; grayscale/color-blind safety |
| Mock data never presented as live | `data/mock/` boundary (separate providers) + `AdminMockBadge` on every mock surface | Structural + visual double guard |
| Active nav state is single-sourced | `AdminShell` reads `GoRouterState.uri` | No duplicated selection state |
| Tables never sort/order by an arbitrary string | `AdminDataColumn` allowlist (only `sortable` keys) | Prevents invalid sorts and future query-injection if moved server-side |
| Theme always applied (dark primary) | `main.dart` `MaterialApp.router(theme/darkTheme: VeriqooTheme.dark)` | Guarantees tokens resolve app-wide |
| Reduced motion respected | Each animating widget calls `VeriqooMotion.reduceMotion` | Accessibility |
| Admin never writes to Supabase | Repositories expose read methods only | Admin is a monitoring surface |

---

## 12. Icon facade plan — `AdminIcons`

**Governing decision on the "no direct lucide import" constraint (R3·#3) — this is the interpretation the approver accepts when approving this design.** The project rule is read as *"no component/screen imports `lucide_icons_flutter` directly; icons are consumed only through a facade,"* and it is satisfied by the **single-importer-facade pattern** — the exact pattern `shared_core` itself uses. `VeriqooIcons` is, by its own in-source documentation, *"the ONLY file in the design system that imports the icon package directly … so swapping the underlying package (e.g. to `phosphor_flutter`) is a single-file change."* `AdminIcons` mirrors that contract one-for-one in `admin_web`: it is the **sole** admin file that imports lucide, so every admin screen/widget still references glyphs only through a facade, and swapping the icon package stays a single-file change per app. This is chosen over the two alternatives because:

- `shared_core` is **read-only** in this phase, and `VeriqooIcons` exposes only 15 glyphs (`home, scan, history, profile, back, close, chevronRight, settings, search, check, alert, verified, violation, camera, upload`) — none of the dashboard/inspections/products/cases/kanban/map/assignment/audit/rbac/filter/sort/export glyphs the control center needs. Extending `VeriqooIcons` in `shared_core` is therefore out of the current write scope (it would be the cleaner long-term fix and is recorded as a future enhancement in §16).
- Sourcing the extra glyphs from Material `Icons.*` would mix a second, visually heavier icon language into a system built entirely on Lucide line icons, breaking the monochrome hairline aesthetic. Rejected on consistency grounds.

If the approver instead reads the constraint literally as *"no lucide dependency anywhere in `admin_web`,"* the fallback is to re-skin §12 onto Material `Icons.*` (accepting the aesthetic compromise) or to escalate extending `VeriqooIcons` in `shared_core`. The design proceeds on the single-importer-facade interpretation; this paragraph is the explicit flag so it does not ship on a silent assumption.

Mechanics: add `AdminIcons` at `C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web\lib\foundations\admin_icons.dart`; it is the **only** file in `admin_web` that imports `lucide_icons_flutter`, preserving the single-point-of-swap intent. Add a direct dependency `lucide_icons_flutter: ^3.1.21` (matching shared_core) to `C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web\pubspec.yaml`. Reuse `VeriqooIcons` wherever a glyph already exists (`search, settings, close, chevronRight, check, alert, verified, violation`); `AdminIcons` adds the rest.

Intended semantic glyphs (implementer confirms the exact Lucide constant exists in `^3.1.21`; if a name differs, this one file is the only edit):

| `AdminIcons` member | Intended Lucide | Use |
| --- | --- | --- |
| `dashboard` | `layoutDashboard` | Dashboard nav |
| `inspections` | `clipboardCheck` | Inspections nav |
| `products` | `package` | Products nav |
| `manufacturers` | `factory` | Manufacturers nav |
| `cases` | `folderOpen` | Cases nav |
| `kanban` | `columns3` (or `kanbanSquare`) | Kanban view |
| `map` | `map` | Map view |
| `assignments` | `userCheck` | Inspector assignment |
| `audit` | `scrollText` (or `fileClock`) | Audit logs |
| `rbac` | `shieldCheck` | Access control |
| `filter` | `filter` | Table filter |
| `sort` / `sortAsc` / `sortDesc` | `arrowUpDown` / `arrowUp` / `arrowDown` | Column sort |
| `columns` | `columns3` | Column controls |
| `more` | `ellipsisVertical` | Row/overflow menu |
| `refresh` | `refreshCw` | Reload |
| `export` | `download` | Export |
| `notifications` | `bell` | Reserved — **not used in Phase 11** (top-bar notifications omitted, R3·#15); returns if auth is added (§13) |
| `menu` | `menu` | Narrow drawer toggle |
| `chevronLeft` / `chevronDown` | `chevronLeft` / `chevronDown` | Pagination/expanders |
| `calendar` / `clock` | `calendar` / `clock` | Date/time filters |
| `location` | `mapPin` | Case location |
| `trendUp` / `trendDown` | `trendingUp` / `trendingDown` | KPI trend (shape, not color) |
| `plus` | `plus` | Create affordances (mock) |

---

## 13. Security callout (must surface, not silently ship)

`admin_web` has **no authentication or authorization**. It initializes Supabase with the anon key and reads regulatory compliance data directly; anyone who can load the web build can read it. The RBAC screen is **mock and enforces nothing**. This is a network-exposed data surface shipping without access control.

Phase 11 does not add auth (out of scope), but the design records the risk and the remediation path: add Supabase Auth (admin sign-in) in front of the shell via a go_router `redirect` guard, and enforce Row Level Security on `public.inspections` server-side so the anon key cannot read it. Until then, the build must not be deployed to a public origin with production data. The RBAC panel explicitly states it is illustrative so no operator assumes it gates anything.

---

## 14. Error handling (per operation)

| Operation | Failure condition | Recoverable? | Caller receives | Logged |
| --- | --- | --- | --- | --- |
| App bootstrap (`main`) | `.env` missing / empty `SUPABASE_URL`/key | Fatal (config) | A `BootstrapErrorApp` = `MaterialApp(theme: VeriqooTheme.dark, home: Scaffold(body: VeriqooErrorState(title:'Supabase is not configured', message: which key is missing by name)))`, instead of a raw `StateError` crash. **The `MaterialApp(theme: VeriqooTheme.dark)` ancestor is mandatory: `VeriqooErrorState` (like every atom) resolves `Theme.of(context).extension<VeriqooTokens>()!` with a non-null `!` and throws if rendered without a `VeriqooTheme` ancestor — which would reintroduce the very crash it replaces (N6).** | `developer.log` (warning); never print key values |
| `Supabase.initialize` | Network/handshake failure at startup | Fatal for session | Same themed `BootstrapErrorApp`; its **Retry re-runs the dotenv/config read then a _guarded_ init** — the init helper first probes `Supabase.instance` in a `try`/`catch` and calls `Supabase.initialize` **only if the singleton is not already registered**, so a partial first init cannot double-register and throw on retry (R3·#12) | warning |
| `dashboardMetrics` (KPI counts; internal `Future.wait` of the three counts) | `PostgrestException`, auth/network error | Recoverable | `dashboardDataProvider` emits `AsyncError`; **only the KPI row** shows `VeriqooErrorState(onRetry → ref.invalidate(dashboardDataProvider))`; charts, Top Violations, Recent Inspections, and mock panels are unaffected (R3·#1) | warning via `developer.log(name:'admin_dashboard')`, carry forward existing logging |
| `recentInspections` | `PostgrestException`, auth/network error | Recoverable | `recentInspectionsProvider` emits `AsyncError`; **only the Recent Inspections panel** shows `VeriqooErrorState(onRetry → ref.invalidate(recentInspectionsProvider))`; the rest of the dashboard is unaffected (R3·#1) | warning |
| `analytics` | `PostgrestException`, auth/network error | Recoverable | `inspectionAnalyticsProvider` emits `AsyncError`; **only the analytics region (both charts + Top Violations)** shows `VeriqooErrorState(onRetry → ref.invalidate(inspectionAnalyticsProvider))`; the live KPI row and Recent Inspections stay rendered (R3·#1) | warning |
| `inspectionsPage` / `groupedProducts` | same | Recoverable | per-panel `VeriqooErrorState` + retry | warning |
| Empty result set | zero rows | n/a (not an error) | `VeriqooEmptyState` with context-appropriate copy | none |
| `inspectionById` cold load | no `extra`, and `id` column absent or row not found | Recoverable | repo **catches and returns `null`** (never a raw `AsyncError`); screen shows `VeriqooErrorState` → `/inspections` (per §5.3, §6.1, R3·#10) | info (missing-column: expected under A1) / warning (other) |
| Malformed `possible_issues` / `missing_information` JSON | non-JSON text or unexpected shape | Recoverable | treated as single issue / raw text (carry forward tolerant `issueCount`); never throws | none |
| Product image load | bad/empty `image_url`, network 404 | Recoverable | `Image.network errorBuilder` → "Image unavailable" placeholder (carry forward) | none |
| Mock repositories | — | n/a (deterministic) | always succeed after simulated latency; still flow through `AsyncValue` for consistent loading UI | none |
| Kanban/assignment mutations | — | session-local | update in-memory notifier; reset on reload (DEMO) | none |
| Unknown route | bad path | Recoverable | `errorBuilder` → not-found `VeriqooErrorState` → `/dashboard` | info |

Principle: live reads are recoverable and always offer retry via `ref.invalidate`; configuration failures are fatal but shown through a themed error surface, never a raw exception screen; parsing is always tolerant.

---

## 15. Input validation (per external input)

| Input | Required? | Type / rules | On invalid |
| --- | --- | --- | --- |
| Table / global-search text | optional | trimmed; lowercased for compare; max 120 chars; debounce 250 ms; empty = no filter. **Target (R3·#2): `inspectionsSearchProvider` → the Inspections table's client-side product/manufacturer `contains` filter.** The top-bar field writes that provider and calls `go('/inspections')`; the Inspections toolbar reads/writes the same provider (§4.2). Scoped to Inspections only — not a cross-entity search. | over-max truncated; never interpolated into a Supabase filter (client-side `contains` only in Phase 11) |
| Status filter | optional | enum `All\|Compliant\|Violation` | unknown → `All` |
| Sort column | optional | must be in the `AdminDataColumn` allowlist; direction `asc\|desc` | unknown key → default `inspected_at desc` |
| Page / pageSize | optional | page clamped `[0, pageCount-1]`; pageSize ∈ `{10,25,50}` | out-of-range clamped; bad size → 25 |
| `cases` `view` query param | optional | `list\|kanban\|map` | else `list` |
| Route `:id` (inspection) | required in path | non-empty string | empty → redirect `/inspections` |
| Case selection | n/a — **not a route** | opened by passing an in-memory `CaseRecord` object to `detailPanelProvider` (no `:vrqId` path param exists; M2/N7) | no id parsing/validation needed — the panel always receives a valid object |
| Date-range filters (audit) | optional | valid ISO dates, `from <= to` | invalid/omitted → no range bound |

Validation of search/sort/paging/route params is owned by the respective `NotifierProvider`/router `redirect`; the `AdminDataColumn` allowlist owns the sort-key invariant.

---

## 16. Out of scope (Phase 11)

- Authentication, authorization, and RLS enforcement (recorded as the §13 remediation path).
- Any **write** from admin to Supabase (admin stays read-only; mock mutations are session-local).
- Real backends for Cases, Kanban, Inspector Assignment, Audit Logs, RBAC, Manufacturers, regional map data, and system-status telemetry.
- Deriving regional/state breakdowns from `address` text, and true deep-linkable inspection details requiring a schema change (both noted as future enhancements).
- A real normalized **India-outline `Path`/vector asset** for the regional map — Phase 11 uses a bounded graticule placeholder (§6.5; future enhancement per N8).
- **Deep-linkable cases** (a `/cases/:vrqId` route) — deferred until cases have a real backend; in Phase 11 a case opens only in the right panel by object reference (§10.5; M2/N7).
- **True cross-entity global search** (a shared index across inspections/products/cases) — Phase 11's top-bar search is scoped to Inspections only (§4.2; future enhancement per R3·#2).
- **Period-over-period KPI trends** — no delta is computed in Phase 11, so every KPI card passes `trend: null` (§10.1; future enhancement per R3·#9).
- **Unit-aware MRP/Net-Qty sorting** — Phase 11 sorts by the first numeric run only, not by normalized units (§10.2; future enhancement per R3·#4).
- **Extending `VeriqooIcons` in `shared_core`** to cover admin glyphs — out of the read-only write scope this phase; admin uses the `AdminIcons` single-importer facade instead (§12; future enhancement per R3·#3).
- Light-theme toggle (dark is primary; light scheme remains available but not surfaced).
- Changing the shared design system or the `public.inspections` schema.
- `fl_chart` or any new charting dependency.

---

## 17. Testability

- **Unit (pure):** `analytics_math.dart` (daily buckets, rate, `dailyViolations` = per-day `is_compliant == false` count **with an explicit test that a `null`-`is_compliant` row is excluded from `dailyViolations` yet counted in `dailyTotals`**, R3·#5; top-violation tally), `DashboardMetrics.rate` `total == 0 → 0` guard (N5), `parseFirstNumber` for MRP/Net-Qty numeric sort incl. the no-digit → `-1`, decimal, and embedded-run cases (N5, R3·#4), product grouping, `status_mapping.dart` **incl. a `null → missing` case** (R3·#14), tolerant `issueCount`, validators (search/sort/paging/route), `chart_axis.dart` transforms, `AdminDataColumn` allowlist, deterministic reload-stable mock VRQ-id generator (N7), model `fromMap`s.
- **Unit (repositories):** inject a fake `SupabaseClient` into `InspectionsRepository`/`ProductsRepository` (constructor seam) and assert the exact table/columns/filters/limits are preserved (regression guard against drifting from today's queries); assert `inspectionById` **returns `null` rather than throwing** when the fake raises a missing-`id`-column `PostgrestException` or yields zero rows (R3·#10). Mock repositories asserted deterministic.
- **Widget:** `AdminShell` active-nav from a given route; `AdminDataTable` sort toggle + empty/loading/error; `AdminKpiCard` (mono value at 24/`w500`, R3·#17); `AdminStatusCell` mapping; `AdminPermissionCell`/`AdminHealthIndicator` shape + `Semantics` and absence of the verification labels (N3); `AdminMockBadge` presence on mock surfaces; opening/closing the detail panel via `showCase`/`showManufacturer`/`close` (with `AdminDetailPanel` fed a stub `title`+`child` to prove it is chrome-only, R3·#6) across the §8 breakpoints (side panel vs full-screen `Dialog`).
- **Golden (monochrome):** `AdminLineChart`, `AdminDonut`, `AdminRegionMap`, `admin_bar_mini`, `VeriqooStatus` cells — verify greyscale, hairlines, no shadows.
- **Integration:** go_router navigation across all routes; `/inspections/:id` via `extra` and the cold-load graceful-null fallback (R3·#10); the top-bar global search seeding `inspectionsSearchProvider` and landing on `/inspections` with the term applied (R3·#2); `/cases?view=` toggling; `ProviderScope` overrides swap a live repo for a fake to drive the Dashboard deterministically, **including a test that failing only `inspectionAnalyticsProvider` shows the charts/Top-Violations error state while the KPI row and Recent Inspections stay rendered** (R3·#1).
- The repository + provider seam and the pure-function extraction are deliberate so screens are testable without a network; a design that forced widget tests to hit Supabase would be reworked.

---

## 18. File manifest

Create (admin_web):
- `lib/app/admin_router.dart`, `lib/app/admin_app.dart` (optional root widget)
- `lib/foundations/admin_icons.dart`
- `lib/widgets/shell/{admin_shell,admin_sidebar,admin_top_bar,admin_breadcrumb,admin_detail_panel}.dart`
- `lib/widgets/data_table/{admin_data_table,admin_data_column,admin_table_toolbar,admin_pagination}.dart`
- `lib/widgets/kanban/{admin_kanban_board,admin_kanban_column,admin_kanban_card}.dart`
- `lib/widgets/charts/{admin_line_chart,admin_donut,admin_bar_mini,chart_axis}.dart`
- `lib/widgets/map/{admin_region_map,admin_view_toggle}.dart`
- `lib/widgets/common/{admin_panel,admin_kpi_card,admin_status_cell,admin_permission_cell,admin_health_indicator,admin_priority_indicator,admin_tag,admin_mock_badge,admin_section_card}.dart`
- `lib/data/{supabase_providers,inspections_repository,products_repository,analytics_math,providers,detail_panel}.dart` — `detail_panel.dart` holds the sealed `AdminDetailPayload` (`.manufacturer`/`.caseRecord`), `DetailPanelController extends Notifier<AdminDetailPayload?>`, and `detailPanelProvider` (§4.1, R3·#6); `providers.dart` holds the three independent dashboard `FutureProvider`s (R3·#1) plus the UI-state notifiers including `inspectionsSearchProvider` (R3·#2)
- `lib/utils/parsing.dart` — `parseFirstNumber(String)` for the MRP/Net-Qty numeric `sortValue` (§10.2, N5, R3·#4)
- `lib/data/mock/{admin_mock,mock_cases_repository,mock_inspectors_repository,mock_audit_repository,mock_rbac_repository,mock_manufacturers_repository,mock_regions,mock_dashboard_supplement}.dart`
- `lib/models/{inspection_row,dashboard_metrics,inspection_analytics,product_aggregate,case_record,inspector,audit_log_entry,role,permission,manufacturer,region_density,system_status_row,status_mapping}.dart`
- `lib/screens/inspections/{inspections_screen,inspection_details_screen}.dart`, `lib/screens/products/products_screen.dart`, `lib/screens/manufacturers/manufacturers_screen.dart`, `lib/screens/cases/cases_screen.dart`, `lib/screens/assignments/assignments_screen.dart`, `lib/screens/audit/audit_logs_screen.dart`, `lib/screens/rbac/rbac_screen.dart` (no `case_details_screen.dart` — case detail is the right panel, not a routed screen; M2). **Note: `lib/screens/dashboard/dashboard_screen.dart` is a _rewrite_ of the existing file at the same path, so it is listed under Modify below, not Create (R3·#11).**

Modify:
- `lib/main.dart` — `ProviderScope` + `MaterialApp.router(createAdminRouter(), theme/darkTheme: VeriqooTheme.dark, title:'VERIQOO Admin')`; **call `usePathUrlStrategy()` (from `package:flutter_web_plugins/url_strategy.dart`) before `runApp` for clean web paths (R3·#13, §5.3)**; keep dotenv + a **guarded, idempotent-on-retry** `Supabase.initialize` (R3·#12, §14); replace the hard `StateError` with `BootstrapErrorApp` = `MaterialApp(theme: VeriqooTheme.dark, home: Scaffold(body: VeriqooErrorState(...)))` so the error surface has a `VeriqooTheme` ancestor (N6).
- `lib/screens/dashboard/dashboard_screen.dart` — **rewrite in place** (same path) into the monochrome `DashboardScreen` that consumes the three independent live providers + the mock supplement (§10.1). The rewrite **removes the two bare `print(...)` calls present today** (`'DASHBOARD SCREEN LOADED'` and `'DASHBOARD BUILD'`), which would otherwise trip the active `avoid_print` lint (it is only commented-out in `apps/admin_web/analysis_options.yaml`, so it is live via `flutter_lints`); its query logic moves into `InspectionsRepository` (§6.1). This is what makes the §19 "analyze clean" goal actually achievable (R3·#11).
- `pubspec.yaml` — add `supabase_flutter: ^2.17.2` (match `shared_core`; admin imports the package directly, so it must be a declared dependency or `depend_on_referenced_packages` fires — M1) **and** `lucide_icons_flutter: ^3.1.21`.

Delete (R3·#11) — explicitly remove the three old screens so the new `screens/` tree is the only one and nothing orphaned trips analyze:
- `lib/screens/dashboard/inspections_screen.dart` — superseded by `lib/screens/inspections/inspections_screen.dart` (its query logic preserved in `InspectionsRepository`).
- `lib/screens/dashboard/products_screen.dart` — superseded by `lib/screens/products/products_screen.dart` (grouping preserved in `ProductsRepository`).
- `lib/screens/dashboard/inspection_details_screen.dart` — superseded by `lib/screens/inspections/inspection_details_screen.dart`.

Remove/replace: the old blue/green `_Panel`/`_Nav`/`_TopBar`/painter code inside the current `screens/dashboard/*` is superseded by the monochrome widgets; `dashboard_screen.dart` is rewritten in place (above) and the other three old `screens/dashboard/*.dart` files are deleted (see Delete), with their query/grouping logic preserved in repositories (§6.1).

---

## 19. Build & verify plan

- `flutter pub get` in `C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web` after the pubspec edit.
- `flutter analyze` clean — this requires both (a) declaring `supabase_flutter` directly (M1) so `depend_on_referenced_packages` does not fire on the admin files that `import 'package:supabase_flutter/...'`, and (b) **the dashboard rewrite dropping the two bare `print(...)` calls that trip the active `avoid_print` lint today** (R3·#11, §18) — note today's app does *not* analyze clean until that rewrite lands. The `AdminIcons` single-import rule is a convention to review (R3·#3, §12).
- `flutter test` for unit/widget/golden suites above.
- `flutter run -d chrome` (or `flutter build web`) smoke: navigate every route, confirm dark monochrome, confirm DEMO badges on all mock surfaces, confirm live Dashboard/Inspections/Products still read `public.inspections` with the same results as today.

---

## 20. Open assumptions (flagged for the design review)

- **A1 — inspection `id`:** `public.inspections` is assumed to have a default PK `id` that the repository can add to its `select` for deep-linkable details. Unverifiable from the repo (the flat table is defined nowhere in the committed schema/migrations). The design review concurred this is correctly hedged and non-blocking: §5.3 provides a redirect fallback; adding `id` to the select is the only change needed if the column exists.
- **A2 — regional/system-status data:** regional density and system-status are illustrative mock fixtures (no normalized state column or telemetry in the live table). Badged DEMO.
- **A3 — `AdminIcons` dependency (now VERIFIED):** `admin_web` gains a direct `lucide_icons_flutter: ^3.1.21` dep (previously transitive). The design review checked all §12 Lucide constant names against the installed `lucide_icons_flutter-3.1.21` and confirmed every one exists, including `factory` (a Dart *built-in identifier*, not a reserved word, so `LucideIcons.factory` / `AdminIcons.manufacturers` is legal). No remaining risk; §12 stands as written.
- **A4 — Violations KPI semantics:** carried forward as the count of `is_compliant = false` inspections (today's behavior), not the sum of `possible_issues`. Switchable in one place if the reviewer prefers total-issue counts.
- **A5 — setup notes absent:** the referenced `C:\WorkSpace\Ajinkya\Veriqoo\.agents\tasks\veriqoo-admin-phase11\setup-notes.md` does not exist; dependency availability (`go_router ^18.0.2`, `flutter_riverpod ^3.4.3`) was instead verified directly from `C:\WorkSpace\Ajinkya\Veriqoo\apps\admin_web\pubspec.yaml`.

---

## 21. Review responses

This section records the per-finding disposition for **both** design-review passes. §21.2 (current, Revision 3) responds to the latest `design-review.json`; §21.1 is retained as the historical record for the first review, because the inline `M#`/`N#` annotations throughout this document refer to it.

### 21.1 First review — resolved in Revision 2 (historical)

First-review verdict: `CHANGES_REQUESTED` — 0 HIGH, 3 MEDIUM, 8 NIT. The review verified every atom/token/icon/query/schema claim as accurate; the findings were integration-level, not ground-truth errors. **All 11 were addressed** (none backlogged, none ignored). Each resolution stayed inside the original requirements and the stated write scope (`apps/admin_web/lib/**` + `apps/admin_web/pubspec.yaml`), and did not touch the read-only design system.

> Historical note: a few concrete values quoted in the table below reflect the Revision 2 state and were **later superseded by the second review** — the KPI mono weight (`w600` here) became `w500` (R3·#17), and `parseLeadingNumber` was renamed `parseFirstNumber` (R3·#4). The current spec lives in the document body and §21.2; read this subsection as an audit trail, not the live specification.

| ID | Sev | Disposition | Resolution (where) |
| --- | --- | --- | --- |
| M1 | MED | **Addressed** | `supabase_flutter: ^2.17.2` (pinned to `shared_core`, confirmed in its pubspec) added as a direct admin dependency so the direct imports stop tripping `depend_on_referenced_packages`. Updated §2 (stack table), §18 (pubspec "Modify" line now lists both supabase_flutter and lucide), §19 (analyze-clean note). |
| M2 | MED | **Addressed** | One detail-surface rule stated in §4.1: deep-linkable full records (only Inspection Details) are **routes** in the workspace; manufacturer and case detail open in the **right `AdminDetailPanel`** via `detailPanelProvider` (object reference, no route). Chose to **remove** `/cases/:vrqId` + `CaseDetailsScreen`. Aligned §5.2 (route row removed), §8 (panel column reworded), §10.4 (manufacturer → `show(manufacturer)`), §10.5 (case → `show(caseRecord)`), §6.1 (`detailPanelProvider` listed), §15 and §18 (route + screen file removed). |
| M3 | MED | **Addressed** | Chose option (a): the Dashboard keeps a **LIVE "Recent Inspections"** panel consuming `recentInspectionsProvider` (carries forward today's `_recent()` surface), with **MOCK "Recent Cases"** beside it, badged. `recentInspections` is no longer orphaned. Updated §10.1, §6.1. |
| N1 | NIT | **Addressed** | §8 narrow detail surface is now a "full-screen admin-local `Dialog` (not the ≤420 `VeriqooModal`, not a route)"; §4.2 `admin_detail_panel` and the §8 trailing paragraph describe `showGeneralDialog` built from tokens. No read-only atom change implied. |
| N2 | NIT | **Addressed** | §7 and §10.1 fix the choice: compliant/non-compliant **split → `AdminDonut({compliant, nonCompliant})`**; `VeriqooScore` is not used on the dashboard (reserved for a future single-rate dial). |
| N3 | NIT | **Addressed** | Valid Dart `VeriqooStatus(kind: VeriqooStatusKind.…)` used for inspections/products only. New `AdminPermissionCell(granted)` (RBAC) and `AdminHealthIndicator(ServiceHealth)` (system status) are shape + domain-label + `Semantics`, never the verification labels. Updated §4.2, §10.1, §10.8, §18. |
| N4 | NIT | **Addressed** | KPI value is a single merged `VeriqooType.mono.copyWith(fontSize: 24, fontWeight: FontWeight.w600)` (§4.2, §10.1). `AdminBreadcrumb`/`AdminTag` `.toUpperCase()` their own text since `VeriqooType.meta` does not (§4.2). |
| N5 | NIT | **Addressed** | `DashboardMetrics.rate` carries forward the `total == 0 → 0` guard (§6.1, §10.1). MRP/Net-Qty get a numeric `sortValue` via `parseLeadingNumber` in `lib/utils/parsing.dart` (§10.2, §17, §18). |
| N6 | NIT | **Addressed** | `BootstrapErrorApp` is now explicitly `MaterialApp(theme: VeriqooTheme.dark, home: Scaffold(body: VeriqooErrorState(...)))` so the atom's `extension<VeriqooTokens>()!` resolves (§14, §18). |
| N7 | NIT | **Addressed** | Resolved via M2: no `/cases/:vrqId` route, so there is no cold-load id lookup. Mock VRQ ids are deterministic and reload-stable (`^VRQ-\d{8}-\d{4}$`) for consistent display (§9, §10.5, §17); deep-linkable cases deferred to §16. |
| N8 | NIT | **Addressed** | Committed to the **bounded graticule placeholder** for Phase 11; the real India-outline `Path`/asset is listed as a future enhancement (§6.5, §10.1, §16). No asset ships this phase. |

Net new files from Revision 2: `lib/widgets/common/admin_permission_cell.dart`, `lib/widgets/common/admin_health_indicator.dart`, `lib/utils/parsing.dart`, `lib/models/system_status_row.dart`. Net removed: `lib/screens/cases/case_details_screen.dart` and the `/cases/:vrqId` route. Dependency added: `supabase_flutter: ^2.17.2`.

### 21.2 Second review — resolved in Revision 3 (current)

Second-review verdict: `CHANGES_REQUESTED` — 0 HIGH, 3 MEDIUM, 14 NIT, **0 ground-truth errors** (`C:\WorkSpace\Ajinkya\Veriqoo\.agents\tasks\veriqoo-admin-phase11\design-review.json`). The reviewer independently re-verified every atom/token/type/icon/query/schema/dependency claim and found none inaccurate; all 17 findings are integration-level — one internal contradiction, two undefined behaviors, a constraint-interpretation flag, and consistency/edge-case nits. **All 17 are addressed in place** — none backlogged, none ignored — and each stays inside the original requirements and the write scope (`apps/admin_web/lib/**` + `apps/admin_web/pubspec.yaml`) without touching the read-only design system. Findings are cited inline as `R3·#1`…`R3·#17`.

| # | Sev | Disposition | Resolution (where) |
| --- | --- | --- | --- |
| 1 | MED | **Addressed** | Reconciled to **three independent providers** with per-panel error/retry (the recommended option). §6.1 providers line, §10.1 "Data & independent loading", and §14 now split `dashboardMetrics`/`recentInspections`/`analytics` into three rows — a failure in one shows only that panel's `VeriqooErrorState(onRetry → ref.invalidate(thatProvider))` and never blanks the live KPI row. The single-`Future.wait`/whole-load-fails language is removed; the three KPI counts' internal `Future.wait` is scoped inside `dashboardMetrics()` only. |
| 2 | MED | **Addressed** | Global search given one concrete target: it binds to `inspectionsSearchProvider` and, on submit, navigates to `/inspections` with the term seeded into the existing client-side inspections filter; scoped to Inspections (no cross-entity index in Phase 11). §4.2 (behavior), §6.1 (provider), §8 (collapse pointer), §15 (exact target named), §16 (cross-entity search deferred). |
| 3 | MED | **Addressed — justified, flagged for sign-off** | §12 now states the **governing decision**: the "no direct lucide import" rule is satisfied by the single-importer-facade pattern — `AdminIcons` mirrors `shared_core`'s own `VeriqooIcons`, which is documented in-source as the sole lucide importer. Rationale (read-only shared_core, 15-glyph gap) stated; literal-reading fallbacks (Material `Icons.*` / escalate extending `VeriqooIcons`) named; shared_core-extension added to §16. §2 row points at the §12 decision. |
| 4 | NIT | **Addressed** | Renamed `parseLeadingNumber` → `parseFirstNumber`, redefined as "first numeric run (optional decimal) anywhere in the string; no digits → `-1`"; mixed-unit limitation documented. §10.2, §17, §18, §16. |
| 5 | NIT | **Addressed** | `dailyViolations` defined as the per-day count of `is_compliant == false` (matching the Violations KPI, A4); `null` excluded; the null case unit-tested in `analytics_math.dart`. §6.1, §10.1, §17. |
| 6 | NIT | **Addressed** | Sealed `AdminDetailPayload.manufacturer(...)` / `.caseRecord(...)` + named methods `showManufacturer`/`showCase`/`close`; `AdminShell` maps payload → `(title, child)` and `AdminDetailPanel` is dumb chrome; provider typed `NotifierProvider<DetailPanelController, AdminDetailPayload?>` in `lib/data/detail_panel.dart`. §4.1, §4.2, §6.1, §10.4, §10.5, §17, §18. |
| 7 | NIT | **Addressed** | Cases map binds to the shared `mock_regions.dart` `List<RegionDensity>` (same DEMO fixture as the dashboard map), not to `CaseRecord`; `CaseRecord → RegionDensity` aggregation deferred. §10.5, §6.5, §16. |
| 8 | NIT | **Addressed** | Added a **LIVE "Top Violations" panel** to §10.1 that renders the analytics tally via `admin_bar_mini` (sharing `inspectionAnalyticsProvider`), so the computed tally and the inventoried `admin_bar_mini` are now placed. §10.1, §17 (golden). |
| 9 | NIT | **Addressed** | Live KPI trends omitted in Phase 11 — every `AdminKpiCard` passes `trend: null` (no delta query exists). §4.2, §10.1, §16. |
| 10 | NIT | **Addressed** | `inspectionById` catches missing-column / not-found / zero-row and **returns `null`**, so the §5.3 error state shows instead of a raw `AsyncError`; repository test asserts null-not-throw. §6.1, §5.3, §14, §17. |
| 11 | NIT | **Addressed** | Dashboard file relabeled a **rewrite** (Modify, same path); the three old `screens/dashboard/{inspections,products,inspection_details}_screen.dart` listed under **Delete**; the rewrite removes the two bare `print(...)` calls so `avoid_print` passes. §18, §19. |
| 12 | NIT | **Addressed** | `BootstrapErrorApp` retry re-runs the config read + a **guarded** init that calls `Supabase.initialize` only if the singleton is not already registered (idempotent). §14, §18. |
| 13 | NIT | **Addressed** | `main()` calls `usePathUrlStrategy()` for clean web paths behind the §5.3 deep-link/reload flows. §5.3, §18. |
| 14 | NIT | **Addressed** | `is_compliant == null → missing` documented and unit-tested in `status_mapping.dart`. §6.4, §17. |
| 15 | NIT | **Addressed** | Top-bar notifications/help/profile **omitted** in Phase 11 (no auth/data source); only well-defined per-screen `actions` remain. §4.1 diagram, §4.2. |
| 16 | NIT | **Addressed — confirmed deliberate** | §10.1 states explicitly that replacing today's per-day compliance-rate line with the activity + violation lines + compliance donut (rate still shown via KPI/donut) is an intentional presentation change, not a data regression. §10.1. |
| 17 | NIT | **Addressed** | KPI value weight changed `w600` → **`w500`** (a bundled IBM Plex Mono weight; matches `VeriqooScore`). §4.2, §10.1, §17. |

Scope check: no requirement from the original brief is dropped and no new backend is introduced. New artifacts this revision: a LIVE **Top Violations** dashboard panel (reusing the existing analytics tally + the already-inventoried `admin_bar_mini`), the `inspectionsSearchProvider` wiring for the global search, and the sealed `AdminDetailPayload` + typed detail-panel API in `lib/data/detail_panel.dart`. Removed: the self-contradictory single-`Future.wait` whole-dashboard-load description, and (in the dashboard rewrite) the two `print(...)` calls. Renamed: `parseLeadingNumber` → `parseFirstNumber`. No dependency change beyond those already recorded in §21.1 (`supabase_flutter`, `lucide_icons_flutter`).
