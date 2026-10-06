# PHASE 4 — User-app HOME rebuild — Implementation Plan

Intelligent inspection command center for `apps/user_app`, editorial monochrome,
with the signature Verification-Scan motif. Implement-then-review (design is
fixed; no design phase). **Main workspace. NO worktree. NO commits.**

---

## 0. Ground truth captured during exploration (do NOT re-derive)

### Toolchain / acceptance bar
- `flutter *` is **denied** by workspace permissions (agents + orchestrator). Use `dart` only.
- Verified working: `dart pub get` → "Got dependencies!"; `dart analyze` → **"No issues found!"** (clean baseline, 0 issues).
- **Acceptance bar for every step:** `dart pub get` succeeds AND `dart analyze` reports 0 errors (keep it at the clean baseline).
- `flutter test` and `flutter build web` are **DEFERRED** — write + keep the tests but do not run them. Exact deferred commands recorded in §8.

### Write scope (STRICT)
- Modify ONLY `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\**`.
- Do NOT modify `packages/shared_core/**` (read-only) or `apps/admin_web/**` (parallel track).
- READ-ONLY reference used below: `packages/shared_core/lib/design_system/**`, `packages/shared_core/lib/services/supabase_service.dart`, `packages/shared_core/lib/services/compliance_analysis.dart`.

### Package / app facts
- `apps/user_app` package name is `flutter_application_1` → internal imports are `package:flutter_application_1/...`.
- Design-system barrel: `import 'package:shared_core/design_system/design_system.dart';` (single import exposes everything used here).
- Dependencies already present (no `pubspec.yaml` change, no `dart pub add` needed): `flutter_riverpod ^3.4.3`, `go_router ^18.0.2`, `supabase_flutter ^2.17.2` (transitively `postgrest 2.9.1`, `supabase 2.16.1`).
- Theme is applied app-wide in `lib/app/app.dart` via `MaterialApp.router` with `VeriqooTheme.light`/`VeriqooTheme.dark` (getters) and the `themeModeProvider`. Tokens resolve with `Theme.of(context).extension<VeriqooTokens>()!`.

### Pinned Supabase data (from `supabase_service.dart` → `saveInspectionReport`)
- Table name: **`inspections`**.
- Columns written per inspection (exact keys):
  `product_name` (text), `mrp`, `net_quantity`, `manufacturer`, `address`,
  `packing_date`, `customer_care`, `missing_information` (json array of strings),
  `possible_issues` (json array of objects, each has `title`, `description`,
  `severity`, `verificationStatus`, optional `ruleNumbers`/`ruleTitles`/`legalBasis`/`ocrEvidence`),
  `is_compliant` (bool), `ocr_text` (text), `ai_report` (json),
  `inspected_at` (timestamptz, ISO-8601 UTC), `image_url` (text, nullable).
- **There is NO `user_id` column and NO `score` column written.** Consequences baked into the plan:
  - **User scoping relies on Supabase RLS** (rows the signed-in client can read). Do NOT add a `.eq('user_id', ...)` filter — the column does not exist and would throw. Document this as the seam Phase 7 can extend if the schema later adds `user_id`.
  - **Score is derived client-side** (see §2 `deriveScore`) — it is NOT a stored column. Never `select('score')`.
  - Primary key column name is unknown (not in the insert). Read `id` null-safely and synthesize a display id when absent.

### Pinned postgrest 2.9.1 count API (verified in installed source)
- Head count (returns `Future<int>`, chainable with filters):
  `await client.from('inspections').count(CountOption.exact)`
  `await client.from('inspections').count(CountOption.exact).eq('is_compliant', false)`
- `CountOption`, `PostgrestException`, `SupabaseClient` all come from `package:supabase_flutter/supabase_flutter.dart`.
- Recent list: `await client.from('inspections').select().order('inspected_at', ascending: false).limit(n)` → `List<Map<String, dynamic>>`.

### Pinned design-system names (exact, read from source — do NOT guess)
- Tokens getter: `Theme.of(context).extension<VeriqooTokens>()!`. Fields: `bg, bgTrue, surface, surfaceRaised, borderHairline, borderStrong, textPrimary, textSecondary, textTertiary, inverseBg, inverseText, brightness`. `textTertiary` is meta/decorative ONLY (fails AA for body).
- Typography `VeriqooType`: `display` (editorial hero, 52/-1.5/w600), `h1, h2, h3, bodyL, body, caption`, `meta` (uppercase label — call `.toUpperCase()` at the call site), `mono` (IBM Plex Mono, tabular figures — for numerals/IDs/scores). Each style leaves `color` null; apply token color via `.copyWith(color: ...)`.
- Spacing `VeriqooSpacing`: `s4 s8 s12 s16 s24 s32 s48 s64 s80 s96`.
- Motion `VeriqooMotion`: durations `fast(160) base(240) slow(320) cinematic(700)`; curves `enter (easeOutCubic), move, press`; reduce-motion helper **`VeriqooMotion.reduceMotion(context)` → bool**. All looping/entrance motion must consult it and resolve to a static end state.
- Components (all from the barrel):
  - `VeriqooAppBar({required title, action, onBack, showBack=true, height=56})` — implements `PreferredSizeWidget`; auto-hides back when `!Navigator.canPop`. For a root screen pass `showBack: false`.
  - `VeriqooIconButton({required icon, required semanticLabel, onPressed, variant, iconSize=20, size=44})`.
  - `VeriqooButton({required label, onPressed, variant: VeriqooButtonVariant.{primary|secondary|ghost}, size: VeriqooButtonSize.{small|medium|large}, icon, loading, expand, semanticLabel})` — `primary` = inverse fill; `secondary` = hairline outline (use for ghost/outline secondary action).
  - `VeriqooSectionHeader({required title, subtitle, action})` — title auto-uppercased; `action` is a trailing widget (e.g. a ghost `VeriqooButton`).
  - `VeriqooDivider()` / `VeriqooDivider.vertical({height, indent, endIndent})` — hairline.
  - `VeriqooInspectionCard({required inspectionId, required timestamp, required product, required score:int, required status: VeriqooStatusKind, maxScore=100, onTap})` — ledger row; renders id+timestamp (mono), product, score `score/maxScore` (mono), and a `VeriqooStatus` chip; shows a chevron when `onTap != null`.
  - `VeriqooStatus({required kind: VeriqooStatusKind.{verified|flag|missing|violation}, markerSize=16, showLabel=true})` — meaning by shape+glyph+label, never color.
  - `VeriqooScore({required value:int, maxValue=100, size=120, strokeWidth=6, duration, caption})` — radial dial, counts up, reduce-motion aware (not required by this screen but available).
  - `VeriqooEmptyState({required icon, required title, message, action})`.
  - `VeriqooErrorState({title='Something went wrong', message, onRetry, retryLabel='Retry', icon=VeriqooIcons.alert})`.
  - `VeriqooLoading({message='Verifying', size=Size(220,180)})` — built on the scan motif.
- Icons facade `VeriqooIcons` (ONLY these glyphs exist; never import lucide, never add to the facade — it lives in shared_core and is read-only):
  `home, scan, history, profile, back, close, chevronRight, settings, search, check, alert, verified, violation, camera, upload`.
  - **Notifications action glyph:** facade has no bell — the existing app convention (`profile_screen.dart`, `notifications_screen.dart`) uses **`VeriqooIcons.alert`** for notifications. Follow that convention.
  - Profile/avatar action glyph: **`VeriqooIcons.profile`**.
- Painters / motif:
  - `InspectionGrid({enabled, color, cell=32})`, `ScanningLine({enabled, color})`, `ProductOutline({enabled, color})`, `DataTicker(...)` — all extend `BackgroundEffect`: monochrome, low opacity, auto-pause offscreen + under reduced motion.
  - `VerificationScan({child, fields=VerificationScan.defaultFields, enabled=true, loop=true, duration, stagger, color, cornerLength=18, sweepThickness=1.5})` — the signature motif; `ScanField(Rect normalized, {label})`; `defaultFields` already includes PRODUCT/MRP/NET QTY/MANUFACTURER/MFG DATE labels; honors reduced motion (renders static locked state).
- App-local helper (already present): `VeriqooBackdrop({required child, background})` in `lib/core/widgets/app_background.dart` — paints `tokens.bg`, an optional background effect (IgnorePointer) below, and the child on top. Reuse it for the Home scaffold body background.

### Routing facts (`lib/app/routes.dart`, `lib/app/router.dart`)
- Home lives in shell branch 0 at `AppRoutes.homePath` (`/home`), rendered by `HomeScreen` (currently a `StatelessWidget` placeholder). **Replace the body of `HomeScreen` only; do not touch the router, the scan branch, or the auth guard.**
- Navigation targets: `AppRoutes.scanPath` (`/scan`), `AppRoutes.historyPath` (`/history`), `AppRoutes.historyDetail(id)` (`/history/<id>`), `AppRoutes.notificationsPath` (`/notifications`), `AppRoutes.profilePath` (`/profile`), `AppRoutes.settingsPath`. Use `context.go(...)` (matches existing screens).
- `historyProvider` (Phase 2 skeleton) is in `lib/features/history/history_providers.dart`: `FutureProvider.autoDispose<List<InspectionSummary>>` returning `const []`. `InspectionSummary{ id, product, timestamp, score }`. `history_screen.dart` consumes it. **Build ON this — do not duplicate** (see steps 3 & 5).

### Hermetic-test constraint (why the repository defers Supabase access)
- `test/app_shell_test.dart` boots the REAL `VeriqooApp` with an authenticated fake and asserts `find.byType(HomeScreen)` and branch switching, **without initializing Supabase**. So:
  - The Home provider graph must **not touch `Supabase.instance` synchronously during widget build.** The repository provider must construct WITHOUT reading `Supabase.instance`; the client is resolved lazily inside each async method (and inside `try`), so an uninitialized Supabase becomes an `AsyncError` the UI renders as an error state — never an uncaught exception.
  - The greeting user lookup must be **guarded** (try/catch → null) because it is read synchronously during build.
- Test harness patterns to mirror: `test/auth/auth_harness.dart` (`wrapScreen` with `ProviderScope` overrides + `MaterialApp(theme: VeriqooTheme.dark)`), and `test/app_shell_test.dart` (`ProviderContainer` overrides, pumping with explicit `tester.pump(Duration)` instead of `pumpAndSettle`, since looping background motion never settles).

---

## 1. Inspections data layer — model + mapper (the Phase 7 seam)

- [ ] 1. Create the inspection record model with a null-safe mapper and the derived score/status helpers.
      Create `InspectionRecord` (immutable) with: `String id` (raw row id as string, or synthesized), `String displayId` (e.g. `VRQ-YYYYMMDD-####`), `String productName`, `DateTime? inspectedAt`, `bool? isCompliant`, `List<String> missingInformation`, `int issueCount`, `int violationCount` (issues with `severity` in {`high`,`critical`}), `int score`, `VeriqooStatusKind status`, and a `String timestampLabel` (formatted `inspectedAt`, zero-padded `YYYY-MM-DD HH:MM`, or `'—'` when null — no `intl` dependency).
      Add `factory InspectionRecord.fromMap(Map<String, dynamic> row, {int index = 0})` that reads every field defensively (missing/typed-wrong keys → safe defaults; `product_name` empty → `'Unknown product'`; parse `inspected_at` via `DateTime.tryParse`; `possible_issues`/`missing_information` tolerate non-list values).
      Add top-level pure helpers `int deriveScore({required bool? isCompliant, required int issueCount, required int missingCount})` (`isCompliant==true` → 100; else `(100 - (issueCount*15 + missingCount*10)).clamp(0,95)`) and `VeriqooStatusKind deriveStatus({required bool? isCompliant, required int issueCount, required int violationCount, required int missingCount})` (`isCompliant==true` → `verified`; `violationCount>0` → `violation`; `issueCount>0` → `flag`; `missingCount>0` → `missing`; otherwise `missing`). `displayId` uses `inspectedAt` date + last 4 chars of `id` (or the `index` when `id` absent).
      Files: `apps/user_app/lib/features/inspections/inspection_record.dart`
      Verify: `cd apps/user_app && dart analyze` → 0 issues (new file compiles; it has no Flutter-widget deps beyond `VeriqooStatusKind` from the design-system barrel).

## 2. Inspections repository (interface + Supabase implementation)

- [ ] 2. Create the repository abstraction and its Supabase-backed implementation, with graceful degradation and deferred client access.
      Define `class InspectionSummaryCounts { final int total; final int? flagged; }` (`flagged` null when the column/count is unavailable). Define `abstract interface class InspectionsRepository { Future<List<InspectionRecord>> recentInspections({int limit = 5}); Future<InspectionSummaryCounts> summaryCounts(); }`.
      Implement `class SupabaseInspectionsRepository implements InspectionsRepository` with `SupabaseInspectionsRepository({SupabaseClient? client})` storing the optional client and a private getter `SupabaseClient get _client => _injected ?? Supabase.instance.client` (so the CONSTRUCTOR never touches `Supabase.instance`). `static const String table = 'inspections';`.
      - `recentInspections`: `try { rows = await _client.from(table).select().order('inspected_at', ascending: false).limit(limit); } on PostgrestException { rows = await _client.from(table).select().limit(limit); }` (fallback when `inspected_at` is missing), then `rows.indexed.map((e) => InspectionRecord.fromMap(e.$2, index: e.$1)).toList()`. Any other failure propagates (becomes the provider's error state).
      - `summaryCounts`: `final total = await _client.from(table).count(CountOption.exact);` then `int? flagged; try { flagged = await _client.from(table).count(CountOption.exact).eq('is_compliant', false); } catch (_) { flagged = null; }` → `InspectionSummaryCounts(total: total, flagged: flagged)`. A failure of the `total` query propagates (error state).
      Document in a doc comment: no `user_id` filter (RLS scopes rows); score/status are derived, not stored; this is the reusable seam Phase 7 (History) extends.
      Files: `apps/user_app/lib/features/inspections/inspections_repository.dart`
      Verify: `cd apps/user_app && dart analyze` → 0 issues (confirms the pinned postgrest `count(CountOption.exact)`/`.eq` and `select().order().limit()` signatures type-check against the installed packages).

## 3. Riverpod providers for the data layer

- [ ] 3. Expose the repository and its two read providers; rewire the Phase 2 `historyProvider` to the repository (build on, don't duplicate).
      In a new `inspections_providers.dart`: `final inspectionsRepositoryProvider = Provider<InspectionsRepository>((ref) => SupabaseInspectionsRepository());` (NO `Supabase.instance` at build time). `final recentInspectionsProvider = FutureProvider.autoDispose<List<InspectionRecord>>((ref) => ref.watch(inspectionsRepositoryProvider).recentInspections(limit: 5));`. `final inspectionSummaryProvider = FutureProvider.autoDispose<InspectionSummaryCounts>((ref) => ref.watch(inspectionsRepositoryProvider).summaryCounts());`.
      Rewire `lib/features/history/history_providers.dart`: keep the `InspectionSummary` type and the `historyProvider` symbol (so `history_screen.dart` keeps compiling unchanged), but implement `historyProvider` by reading `inspectionsRepositoryProvider` and mapping `InspectionRecord` → `InspectionSummary` (`id: r.displayId, product: r.productName, timestamp: r.timestampLabel, score: r.score`). This routes History and Home through one repository — no duplicate data access.
      Files: create `apps/user_app/lib/features/inspections/inspections_providers.dart`; modify `apps/user_app/lib/features/history/history_providers.dart`.
      Verify: `cd apps/user_app && dart analyze` → 0 issues (both the new providers file and the rewired history provider compile; `history_screen.dart` is unchanged and still resolves `historyProvider`/`InspectionSummary`).

## 4. Centralized copy + greeting/user provider

- [ ] 4. Add the Home string constants and a guarded current-user provider with the time-of-day greeting helper.
      Create `HomeStrings` (abstract final) holding every user-facing string as a `static const`, ready for later localization: wordmark `VERIQOO`; greeting prefixes `GOOD MORNING/AFTERNOON/EVENING`; hero lines (`VERIFY`, `WHAT'S ON`, `THE LABEL.` as stacked lines + a combined semantics string); supporting line `Scan packaged products and check mandatory declarations with AI-powered compliance analysis.`; CTAs `SCAN PRODUCT`, `VIEW HISTORY`, `SCAN A PRODUCT`, `View all`; metric labels `INSPECTED`, `FLAGGED`; section title `RECENT INSPECTIONS`; empty title/message (`Your verification history will appear here after your first product analysis.`); error title/message; semantic labels for the notifications and profile actions.
      Create `currentUserProvider` (`Provider<HomeUser?>`) returning a small immutable `HomeUser({String? name, String? email})` read lazily and **guarded**: `try { final u = Supabase.instance.client.auth.currentUser; ... } catch (_) { return null; }`. Derive `name` from `userMetadata['full_name'] ?? userMetadata['name']`, else the email local-part, else null. Add pure helper `String greetingFor(DateTime now)` → MORNING (<12) / AFTERNOON (<17) / EVENING, and `String greetingLine(HomeUser?, DateTime now)` composing `"GOOD <TOD>, <NAME>"` with a graceful fallback (`"GOOD <TOD>"` when no name/email).
      Files: create `apps/user_app/lib/features/home/home_strings.dart`; create `apps/user_app/lib/features/home/home_user.dart`.
      Verify: `cd apps/user_app && dart analyze` → 0 issues (guarded provider compiles; the greeting helper is pure and unit-testable).

## 5. Home section widgets (decomposed, reduced-motion aware)

- [ ] 5. Build the Home section widgets as small, independently testable pieces under a `widgets/` folder.
      Create these widgets (each resolves tokens via `Theme.of(context).extension<VeriqooTokens>()!` and uses only pinned design-system APIs):
      - `HomeTopBar` — a root header (NOT a back-bar): left `VERIQOO` wordmark (`VeriqooType.h3`/mono-ish per editorial look); right a `VeriqooIconButton(icon: VeriqooIcons.alert, semanticLabel: notifications)` → `context.go('/notifications')` and `VeriqooIconButton(icon: VeriqooIcons.profile, semanticLabel: profile)` → `context.go('/profile')`; a subtle online/offline dot driven by `networkStatusProvider` (`lib/core/providers/network_provider.dart`) — shape+label, not color-only (e.g. a small hairline-ring dot + `ONLINE/OFFLINE/—` meta label).
      - `HomeGreeting` — meta-style line from `greetingLine(ref.watch(currentUserProvider), DateTime.now())`, `VeriqooType.meta` in `textSecondary`.
      - `HomeHero` — stacked `VeriqooType.display` lines (`VERIFY` / `WHAT'S ON` / `THE LABEL.`) in `textPrimary`, tight tracking (style already has `-1.5`), wrapped in a single `Semantics(label: combined hero string)`; supporting `VeriqooType.bodyL`/`body` line in `textSecondary`.
      - `HomeActions` — primary `VeriqooButton(label: SCAN PRODUCT, icon: VeriqooIcons.scan, variant: primary, size: large, expand: true)` → `/scan`; secondary `VeriqooButton(label: VIEW HISTORY, variant: secondary, expand: true)` → `/history`.
      - `HomeSignatureScan` — a bounded-height (~160–200px) `IgnorePointer` + low `Opacity` (~0.5) `Stack` of `ProductOutline()` under `VerificationScan(loop: true)`; sits BELOW foreground content (place it behind the hero/metrics in the page `Stack`, not above). Motion pauses automatically under reduced motion (handled by the DS widgets).
      - `HomeMetrics` — a slim editorial line (NOT cards): big `VeriqooType.mono` numbers with `VeriqooType.meta` uppercase labels (`INSPECTED`, `FLAGGED`), separated by `VeriqooDivider.vertical`. Takes `InspectionSummaryCounts` (render `flagged` as `'—'` when null, zero-padded totals like `12`/`03`). Count-up: a `TweenAnimationBuilder<int>` over `VeriqooMotion.base`, curve `enter`, collapsed to `Duration.zero` when `VeriqooMotion.reduceMotion(context)`.
      - `HomeRecentList` — takes `List<InspectionRecord>`; a `VeriqooSectionHeader(title: RECENT INSPECTIONS, action: ghost VeriqooButton 'View all' → /history)` over up to 5 `VeriqooInspectionCard(inspectionId: r.displayId, timestamp: r.timestampLabel, product: r.productName, score: r.score, status: r.status, onTap: () => context.go(AppRoutes.historyDetail(r.id)))`.
      - `HomeRecentEmpty` — the intelligent empty state: `VeriqooEmptyState(icon: VeriqooIcons.history, title/message from HomeStrings, action: VeriqooButton 'SCAN A PRODUCT' → /scan)` over a subtle `ProductOutline` + `ScanningLine` visual (low opacity, IgnorePointer).
      Files: `apps/user_app/lib/features/home/widgets/home_top_bar.dart`, `home_greeting.dart`, `home_hero.dart`, `home_actions.dart`, `home_signature_scan.dart`, `home_metrics.dart`, `home_recent_list.dart`, `home_recent_empty.dart` (ConsumerWidget where a provider is read; otherwise StatelessWidget).
      Verify: `cd apps/user_app && dart analyze` → 0 issues.

## 6. Assemble HomeScreen with entrance motion and loading/empty/error states

- [ ] 6. Replace the `HomeScreen` body: compose the sections, wire the providers, and add the reduced-motion-aware load entrance.
      Convert `HomeScreen` to a `ConsumerStatefulWidget` with a `SingleTickerProviderStateMixin` entrance `AnimationController` (`VeriqooMotion.slow`); in `didChangeDependencies`/`initState` set `controller.value = 1` when `VeriqooMotion.reduceMotion(context)` else `forward()`. Drive hero rise+fade, metrics, and recent-row stagger via `Interval`s on that controller (subtle; do not over-animate).
      Scaffold: `backgroundColor: tokens.bg`; body = `VeriqooBackdrop(background: const InspectionGrid(), child: SafeArea(...))`. Content is a `CustomScrollView`/`SingleScrollView` column: `HomeTopBar` (root, no back button) → `HomeGreeting` → a `Stack` with `HomeSignatureScan` behind `[HomeHero, HomeActions]` → `HomeMetrics` → recent section. Mobile-first; wrap in a `ConstrainedBox(maxWidth ~ 640)` centered when widened (don't stretch).
      Data wiring: `ref.watch(inspectionSummaryProvider).when(loading/error/data)` feeds `HomeMetrics` (show skeleton/placeholder dashes while loading; inline degrade on error — do NOT blow away the whole screen for the metrics line). `ref.watch(recentInspectionsProvider).when(loading: VeriqooLoading, error: VeriqooErrorState(onRetry: () => ref.invalidate(recentInspectionsProvider)), data: records.isEmpty ? HomeRecentEmpty : HomeRecentList)`. The hero/actions/top bar always render regardless of data state.
      Files: modify `apps/user_app/lib/features/home/home_screen.dart` (remove the placeholder body; keep the class name `HomeScreen` and the `const HomeScreen({super.key})` constructor so the router is untouched).
      Verify: `cd apps/user_app && dart analyze` → 0 issues. Manually confirm `lib/app/router.dart` is unchanged (Home still `const HomeScreen()`).

## 7. Hermetic widget tests (kept; run deferred)

- [ ] 7. Add a Home test harness and the widget-test matrix using a fake repository — never hit `Supabase.instance`.
      Harness `test/home/home_harness.dart`: a `FakeInspectionsRepository implements InspectionsRepository` with configurable behavior (populated list, empty list, never-completing `Completer` futures for loading, and throwing futures for error). A `pumpHome(tester, {repo, user, network})` that wraps `HomeScreen` in `ProviderScope(overrides: [inspectionsRepositoryProvider.overrideWithValue(repo), currentUserProvider.overrideWithValue(user), networkStatusProvider.overrideWith(...)])` inside a `MaterialApp.router` with a minimal `GoRouter` whose routes (`/home`, `/scan`, `/history`, `/history/:id`, `/notifications`, `/profile`) render keyed `Placeholder`s so navigation is observable. Theme `VeriqooTheme.dark`. Pump with explicit `tester.pump(Duration)` (never `pumpAndSettle` — background motion loops forever).
      Tests in `test/home/home_screen_test.dart`:
      - renders in LOADING (futures pending) without exception; hero + both action labels present.
      - renders EMPTY (empty list) → `HomeRecentEmpty` / empty-state message + `SCAN A PRODUCT` present.
      - renders POPULATED (fake records) → at least one `VeriqooInspectionCard`; metrics labels `INSPECTED`/`FLAGGED` present.
      - greeting present (`GOOD` text) with a fake user name; and the graceful fallback with `user: null`.
      - tapping `SCAN PRODUCT` navigates to `/scan`; tapping `VIEW HISTORY` navigates to `/history` (assert the keyed placeholder appears / router location).
      - ERROR (throwing recent future) → `VeriqooErrorState` shown; `takeException()` is null (error is an `AsyncError`, not uncaught).
      Optionally add `test/home/home_logic_test.dart` for the pure helpers (`deriveScore`, `deriveStatus`, `greetingFor`, `InspectionRecord.fromMap` with missing/odd columns).
      Files: `apps/user_app/test/home/home_harness.dart`, `apps/user_app/test/home/home_screen_test.dart`, optional `apps/user_app/test/home/home_logic_test.dart`.
      Verify: `cd apps/user_app && dart analyze` → 0 issues (tests compile). Running them is DEFERRED (see §8) — do NOT run `flutter test`.

## 8. Final verification + deferred commands

- [ ] 8. Confirm the acceptance bar and record deferred commands.
      Run `cd apps/user_app && dart pub get` (expect "Got dependencies!") and `cd apps/user_app && dart analyze` (expect **"No issues found!"**, i.e. 0 errors — same as baseline).
      Record (do NOT run) the DEFERRED verification, to be executed where `flutter` is permitted:
      - `cd apps/user_app && flutter test` — runs the kept widget tests (home + existing auth/shell suites).
      - `cd apps/user_app && flutter build web` — build smoke check.
      Files: none (verification only).
      Verify: `dart pub get` succeeds AND `dart analyze` → 0 issues. **No commits** are made at any point.

---

## Repository / provider API handed to Phase 7 (History)

- `InspectionsRepository` (abstract interface): `Future<List<InspectionRecord>> recentInspections({int limit = 5})`, `Future<InspectionSummaryCounts> summaryCounts()`.
- `SupabaseInspectionsRepository({SupabaseClient? client})` — table `inspections`; defers `Supabase.instance.client` to call time; RLS-scoped (no `user_id` filter); score/status derived.
- Providers: `inspectionsRepositoryProvider` (`Provider<InspectionsRepository>`), `recentInspectionsProvider` (`FutureProvider.autoDispose<List<InspectionRecord>>`), `inspectionSummaryProvider` (`FutureProvider.autoDispose<InspectionSummaryCounts>`). `historyProvider` now delegates to the same repository.
- `InspectionRecord` is the richer canonical model; `InspectionSummary` (Phase 2) is a thin projection kept for `history_screen.dart` compatibility. Phase 7 should extend `recentInspections`/add a paged `allInspections` on the same repository and migrate History to `InspectionRecord`.

## How Home degrades when the `inspections` table/columns differ
- No `user_id` column → no explicit user filter; scoping is RLS. If Phase 7 adds `user_id`, add a guarded `.eq('user_id', ...)` then.
- No `score` column → score is always derived (`deriveScore`); never selected.
- Missing `inspected_at` → recent query falls back to unordered `select().limit()`.
- Missing `is_compliant` (flagged count) → `flagged` is null → metrics render `'—'`; total still shows.
- Any row with missing/typed-wrong keys → `InspectionRecord.fromMap` returns safe defaults (`'Unknown product'`, null date → `'—'`, empty issue/missing lists); the UI never throws.
- Genuine fetch failure (e.g. network, uninitialized Supabase) → `FutureProvider` error → `VeriqooErrorState` with retry; hero/actions/top bar still render. No uncaught exceptions (greeting user read is guarded).

## `dart analyze` trajectory
- Baseline (before changes): **0 issues** ("No issues found!").
- Target after every step and at completion: **0 issues**. Each step above is independently `dart analyze`-clean and leaves the app buildable.
