# VERIQOO Phase 11 — admin_web DESIGN REVIEW (fresh / third pass)

Reviewed document: `.agents/tasks/veriqoo-admin-phase11/admin-design.md` (Revision 3).
Reviewer stance: read fresh, without the context that produced it. Every ground-truth claim (atoms, tokens, type, icons, barrel, live queries, schema, dependencies, lints, Lucide constants) was re-verified against the actual source rather than taken on the design's word. Builds and test suites were **not** run (this is a document review); the one lint-level conclusion below (Finding 1) is reasoned from the lint's definition and the design's own M1 precedent, not executed.

**Verdict: CHANGES_REQUESTED** — 0 HIGH, 3 MEDIUM, 5 NIT.
(Mechanical rule: any HIGH/MEDIUM ⇒ CHANGES_REQUESTED.)

This is a strong, meticulous design and it contains **zero ground-truth errors** — I independently confirmed every atom constructor, token, type style, icon name, query, column, dependency pin, and the `avoid_print`/`print()` facts. The three MEDIUMs are integration gaps and one open decision the design itself defers to the approver; none invalidate the architecture. A quick loop-back resolves them.

---

## Findings

### 1. [MEDIUM] `flutter_web_plugins` is imported directly but never declared — fails the §19 "analyze clean" gate

**Where:** §5.3 and §18 (Modify → `lib/main.dart`), vs §18 (Modify → `pubspec.yaml`) and §19.

**Problem:** §5.3/§18 add a new direct import `package:flutter_web_plugins/url_strategy.dart` to call `usePathUrlStrategy()`. The §18 pubspec change adds only `supabase_flutter` and `lucide_icons_flutter`; it does **not** add `flutter_web_plugins`. Today `flutter_web_plugins` is only a *transitive* SDK package (confirmed `dependency: transitive` in `apps/admin_web/pubspec.lock`), and no existing app in the repo imports it directly. This is the **exact** situation the design already reasons about for `supabase_flutter` (M1): a package imported directly must be a declared dependency or `depend_on_referenced_packages` fires under `flutter_lints`. §19 makes `flutter analyze` clean a gating criterion, so leaving this out contradicts the design's own success condition. (It will still *build*, since the package resolves transitively — the failure is the analyze gate, not compilation.)

**Fix:** Add to `apps/admin_web/pubspec.yaml` and to the §18 Modify list:
```yaml
dependencies:
  flutter_web_plugins:
    sdk: flutter
```
This is the standard, documented way to use `usePathUrlStrategy()` and keeps the analyze gate green, consistent with the M1 handling of `supabase_flutter`.

---

### 2. [MEDIUM] The "no direct lucide import" constraint is resolved only by an interpretation the design defers to the approver — this is an open decision, not a settled design

**Where:** §2 (Icons row), §12 (governing decision, R3·#3), §18 (pubspec adds `lucide_icons_flutter`).

**Problem:** The task constraint is "consume the shared design system read-only … VeriqooIcons facade, no lucide direct import." The design's AdminIcons plan **adds a direct `lucide_icons_flutter` dependency and a direct `import 'package:lucide_icons_flutter/...'` in `admin_web`** (in `foundations/admin_icons.dart`). The design argues this satisfies the rule under a *single-importer-facade* reading and explicitly states (§12) "this paragraph is the explicit flag so it does not ship on a silent assumption," labelling it "flagged for sign-off." A design that defers a named constraint's interpretation to the approver is, by definition, not yet resolved on that point — and if the approver intended the literal "no lucide anywhere in admin_web," then §2, §12, and §18 all change materially.

I verified the design's supporting facts and they are accurate: `shared_core`'s `VeriqooIcons` is documented in-source as "the ONLY file in the design system that imports the icon package directly," so the single-importer pattern is the established project precedent, and the 15-glyph facade genuinely lacks the control-center glyphs. The reasoning is sound; the issue is that the decision is still open.

**Fix (a choice the approver must make, then record as resolved):**
- **Option A (design's recommendation):** Ratify the single-importer-facade interpretation — AdminIcons is the sole lucide importer in `admin_web`, mirroring `VeriqooIcons`. Change the §12 wording from "flagged for sign-off" to "approved interpretation" so implementation proceeds unambiguously. (No code change beyond what §12 already specifies.)
- **Option B (literal reading):** No lucide in `admin_web`. Either re-skin §12 onto Material `Icons.*` (accept the heavier icon language) or escalate extending `VeriqooIcons` in `shared_core` (which would breach the read-only/write-scope rule and needs its own approval).

Pick one before build; the design cannot be "ready for implementation" while this is a pending sign-off.

---

### 3. [MEDIUM] Right detail-panel lifecycle across navigation is unspecified, and the (always-mock) panel content is not in the DEMO-badge list — can present mock over a live route

**Where:** §4.1 (detail-surface rule, `detailPanelProvider`), §8 (breakpoint behaviors), §9 (badge locations), §10.4/§10.5.

**Problem:** `detailPanelProvider` is shell-level state owned by `AdminShell` (the `ShellRoute` builder), so it survives route changes. The design never says what happens to an open panel when the user navigates. Concretely: open a **case** (mock) detail panel on `/cases`, then click `Dashboard` or `Inspections` in the sidebar — the panel holds a `CaseRecord` object and would remain docked/overlaid over the live `/inspections` table. Two gaps follow:
- **Lifecycle:** nothing clears the panel on a location change, and for the `<768` full-screen `Dialog` variant (§8) nothing states that barrier/back dismissal funnels back to `DetailPanelController.close()` (so the provider can hold stale state).
- **Mock isolation:** both payloads (`manufacturer`, `caseRecord`) are *always* mock, but §9's badge list (sidebar, top-bar context on mock routes, mock panel/section headers, kanban cards, map) does **not** include the detail panel. A mock case/manufacturer panel floating over a LIVE screen with no `DEMO` marker brushes the §9/§11 hard invariant "mock data is never presented as live."

**Fix:** Specify the panel lifecycle in §4.1/§8: (a) `AdminShell` listens to the router location and calls `ref.read(detailPanelProvider.notifier).close()` on any route change (or only renders the panel on `/cases` and `/manufacturers`); (b) every dismissal path of the narrow full-screen `Dialog` routes through `close()`; and (c) add the detail panel to §9's badge list — the `_ManufacturerDetailView`/`_CaseDetailView` header carries the `AdminMockBadge` since both payloads are mock.

---

### 4. [NIT] `inspectionByIdProvider` is relied on but never declared in the provider inventory or file manifest

**Where:** §5.3, §14, §17 reference `inspectionByIdProvider(id)`; §6.1 provider list and §18 (`data/providers.dart`) do not include it.

**Problem:** The repo method `inspectionById(String id)` is defined, but the Riverpod family provider the detail screen "watches" is never formally declared, so its type/shape is left implicit.

**Fix:** Add to §6.1 and §18, e.g. `final inspectionByIdProvider = FutureProvider.family<InspectionRow?, String>((ref, id) => ref.read(inspectionsRepositoryProvider).inspectionById(id));` and note it returns `null` (not `AsyncError`) on the A1-false / not-found path, consistent with §6.1/§5.3/R3·#10.

---

### 5. [NIT] `NotifierProvider<String>` and the other UI-state notifiers use a type notation that is not instantiable

**Where:** §4.2 and §6.1 (`inspectionsSearchProvider` as "a `NotifierProvider<String>`"; "status filter, sort spec, page, pageSize, and cases view mode" as "small `NotifierProvider`s").

**Problem:** Riverpod's `NotifierProvider<NotifierT, StateT>` takes two type arguments; `NotifierProvider<String>` is not valid (String is not a `Notifier`). Only the detail-panel provider is spelled correctly (`NotifierProvider<DetailPanelController, AdminDetailPayload?>`). The other UI-state notifiers have no `Notifier` subclass named, so the state type and the class are conflated.

**Fix:** For each, name the controller and both type args, e.g. `class InspectionsSearch extends Notifier<String> { @override String build() => ''; … } final inspectionsSearchProvider = NotifierProvider<InspectionsSearch, String>(InspectionsSearch.new);` — and likewise for status filter, sort spec, page, pageSize, cases view mode.

---

### 6. [NIT] Loading-state wording conflicts across sections (§10 vs §3.1/§6.2)

**Where:** §10 ("Loading/empty/error states use `VeriqooLoading`-style skeletons …") vs §3.1 ("`VeriqooLoading` … **not used** in admin") and §6.2 ("`VeriqooLoading`-free skeleton rows").

**Problem:** §10 says loading uses "VeriqooLoading-style skeletons," but §3.1 excludes `VeriqooLoading` from admin and §6.2 says loading is "VeriqooLoading-free." I confirmed in source that `VeriqooLoading` is the branded verification-scan panel (`VerificationScan` motif), not a skeleton at all — so "VeriqooLoading-style skeletons" is doubly misleading and an implementer reading §10 could reach for an atom the design elsewhere forbids.

**Fix:** In §10 replace "`VeriqooLoading`-style skeletons" with "static skeleton placeholders (admin does **not** use the `VeriqooLoading` scan-motif atom — see §3.1/§6.2)." Keep `VeriqooEmptyState`/`VeriqooErrorState` as the empty/error atoms.

---

### 7. [NIT] Inspections status filter (3-way) does not line up with the 4-way status cell; `is_compliant == null` rows are unfilterable

**Where:** §10.2 (filter `All | Compliant | Violation`) vs §6.4 (cell maps to 4 kinds: `VERIFIED / FLAG / NOT DETECTED / VIOLATION`).

**Problem:** The design upgrades the status *cell* to 4 outcomes but keeps today's binary *filter*. A row shown as `FLAG` (is_compliant=false, only missing info) is swept into the `Violation` filter, and a `NOT DETECTED` row (`is_compliant == null`, per R3·#14) matches **neither** `Compliant` (`== true`) nor `Violation` (`== false`), so it appears only under `All`. The filter can't isolate the two new states, which can read as inconsistent.

**Fix:** Either state explicitly that the filter is intentionally binary over `is_compliant` and null rows surface only under `All` (document the behavior), or widen the filter to the four `VeriqooStatusKind`s so the toolbar matches the cell.

---

### 8. [NIT] Products "Status" (latest inspection) and "Violations" (summed across all) can display contradictory signals

**Where:** §10.4 (Products columns: Status via `VeriqooStatus` from the latest inspection; Violations = summed issue count across the group).

**Problem:** `ProductAggregate` carries the latest row's status but the summed issue count across every inspection for that product (carried forward from today's `products_screen.dart`). A product whose most recent inspection is compliant can therefore show `VERIFIED` next to a non-zero Violations count. Today this is masked by a binary status; the richer 4-way status makes the mismatch more visible.

**Fix:** Optional clarification — state in §10.4 that "Status" reflects only the latest inspection while "Violations" is cumulative, or derive the Products status from the aggregate (e.g. worst-case across the group) so the two columns agree.

---

## Verified assumptions (checked against source, all accurate)

- **Barrel + read-only consumption:** `package:shared_core/design_system/design_system.dart` exists and re-exports the full theme layer, `foundations/veriqoo_icons.dart`, painters, components, and the gallery. The gallery re-export (`VeriqooMockData`, `GalleryInspection`) does **not** collide with any admin model name, so the mandated barrel import is safe. ✔
- **Tokens (`VeriqooTokens`):** all 12 fields exactly as §3.1 lists; `dark` → `bg` deepBlack `#0A0A0A`, `surface` charcoal `#111111` (matches §4.1). ✔
- **Primitive ramp (`VeriqooColors`):** all 10 names match. ✔
- **Type ramp (`VeriqooType`):** `display, h1, h2, h3, bodyL, body, caption, meta, mono` all present; `meta` is **not** auto-uppercased (source says apply `.toUpperCase()` at the call site — N4 correct); `mono` is IBM Plex Mono w400 with `FontFeature.tabularFigures()`; `h2` is 24px (so "mono at the 24px h2 size" is right). ✔
- **Spacing / Radius / Elevation / Motion:** `s4…s96`; `none/sm/md/lg` + `*All` + `top()`; `softShadow` + `translucentSurface`; `fast/base/slow/cinematic`, `enter/move/press`, `pressSpring`, `reduceMotion` via `MediaQuery.maybeDisableAnimationsOf` — all exact. ✔
- **Theme:** `VeriqooTheme.dark/.light` build `ThemeData` with the tokens extension, Inter family, `surfaceTint: transparent` (Material tint disabled). ✔
- **Atom constructors:** `VeriqooButton`, `VeriqooIconButton` (`{required icon, required semanticLabel, onPressed, variant: ghost|outline, iconSize=20, size=44}`), `VeriqooTextField` (incl. `prefixIcon`/`onSubmitted`, label auto-uppercased), `VeriqooStatus` (`VeriqooStatusKind{verified,flag,missing,violation}`, labels `VERIFIED/FLAG/NOT DETECTED/VIOLATION`), `VeriqooScore` (mono readout at **w500** — so R3·#17's w500 choice matches the system), `VeriqooDivider(+.vertical)`, `VeriqooSectionHeader`, `VeriqooEmptyState`, `VeriqooErrorState`, `VeriqooModal(+show, maxWidth 420)` — every signature matches §3.1. ✔
- **`VeriqooErrorState` resolves `Theme.of(context).extension<VeriqooTokens>()!` with a non-null `!`** → N6's reasoning that `BootstrapErrorApp` must wrap it in `MaterialApp(theme: VeriqooTheme.dark)` is correct. ✔
- **`VeriqooIcons` facade:** exactly the 15 glyphs listed; source documents it as the sole lucide importer in the design system (the precedent §12 relies on). ✔
- **IBM Plex Mono bundling:** `shared_core/pubspec.yaml` bundles only `IBMPlexMono-Regular.ttf` (400) and `IBMPlexMono-Medium.ttf` (500) → `w500` is a true bundled weight and `w600` would fall back (R3·#17 correct). ✔
- **Existing live queries (carried forward verbatim):** dashboard's five-way `Future.wait` (count on `select('product_name').count(exact)`, `is_compliant` true/false counts, recent 50 `order inspected_at desc`, 30-day `gte(cutoff) order asc` bucketed by day + top-issue tally); inspections count + `limit(200)` + client search/status/paging(10); products `limit(500)` grouped by `name|manufacturer` with summed issues + latest row; tolerant `issueCount`; details screen pure-presentation with `Image.network` fallback. All match §3.2/§6.1. ✔
- **`SupabaseService`:** writes only (`saveInspectionReport`, `uploadInspectionImage`, `testConnection`), constructor `({SupabaseClient? client})` — the exact seam the repos mirror; its insert confirms the §3.3 column set and that **no `id` is written**. ✔
- **`ComplianceAnalysis`/`ComplianceIssue`:** real shapes behind `ai_report`/`possible_issues`, camelCase `toJson`, tolerant `fromJson`. ✔
- **main.dart bootstrap:** `ensureInitialized` → `dotenv.load('.env')` → `SUPABASE_URL` + `SUPABASE_ANON_KEY/SUPABASE_KEY` → `Supabase.initialize(url:, publishableKey:)` → throws `StateError` if missing; named routes `/`, `/inspections`, `/products` on a seeded blue/green theme. ✔
- **`avoid_print`:** `apps/admin_web/analysis_options.yaml` leaves `avoid_print: false` **commented out** (so the rule is live via `flutter_lints`), and there are **exactly two** bare `print(...)` calls, both in `dashboard_screen.dart` (`'DASHBOARD SCREEN LOADED'`, `'DASHBOARD BUILD'`). R3·#11 is accurate: today does not analyze clean until the rewrite drops them. ✔
- **Dependencies:** `go_router ^18.0.2`, `flutter_riverpod ^3.4.3`, `flutter_dotenv ^6.0.1` already declared; `supabase_flutter` + `lucide_icons_flutter` currently transitive at the pinned `^2.17.2` / `^3.1.21` (match `shared_core`); SDK `^3.13.3`. No `google_fonts` anywhere in real code. ✔
- **§12 Lucide constants:** all 29 names verified present in the installed `lucide_icons_flutter-3.1.21` (`layoutDashboard, clipboardCheck, package, factory, folderOpen, columns3, kanbanSquare, map, userCheck, scrollText, fileClock, shieldCheck, filter, arrowUpDown, arrowUp, arrowDown, ellipsisVertical, refreshCw, download, bell, menu, chevronLeft, chevronDown, calendar, clock, mapPin, trendingUp, trendingDown, plus`). `factory` is a real `static const IconData` member, so `LucideIcons.factory` compiles and A3 is correct (and AdminIcons names that member `manufacturers`, so there is no built-in-identifier clash on the admin side). ✔
- **Write scope:** every path in §18 (Create/Modify/Delete) is under `apps/admin_web/**`; the design keeps `shared_core` read-only and defers extending `VeriqooIcons` to a future phase. ✔
- **Schema references:** `final_schema.sql` exists and contains no `inspections`; the Phase 8B migration `20261004000000_phase8b_inspection_persistence.sql` exists; `setup-notes.md` is absent (A5 correct). ✔

## Unverified / wrong assumptions

- **No wrong assumptions found.** Every falsifiable claim the design makes about the codebase matched source.
- **A1 (inspection `id`)** remains genuinely **unverifiable from the repo** — the flat `public.inspections` table is defined in no committed schema/migration, and the live `select` lists never include `id`. The design hedges this correctly and non-blockingly (§5.3 redirect/null fallback via `inspectionById` returning `null`), so it is not a finding; it is simply an assumption that only runtime against the real database can confirm.
- **A2 (regional / system-status fixtures)** is a product decision (no normalized state column or telemetry exists), not a verifiable code claim; correctly badged DEMO.
- **Finding 1 (flutter_web_plugins)** is reasoned from the `depend_on_referenced_packages` definition and the design's own M1 precedent, **not** executed — the task prohibits running `flutter analyze`. If an implementer runs analyze and it is somehow lenient toward this SDK package, the fix (declaring the SDK dep) is still the correct, harmless, convention-matching action.
