# PHASE 7 — user_app HISTORY experience — Implementation Plan

Build the HISTORY experience for `apps/user_app`: an inspection **ledger** (`/history`),
**search**, **inspection detail** (`/history/:id`), and **product detail** (`/products/:id`),
editorial monochrome, reusing the Phase 4 inspections repository and the Phase 6 compliance
report / finding / evidence widgets. Implement-then-review (design is fixed by the task spec;
no design phase). **Main workspace. NO worktree. NO commits.**

---

## 0. Ground truth captured during exploration (do NOT re-derive)

### Toolchain / acceptance bar
- Shell `flutter *` is **DENIED**. Use `dart` ONLY: `dart pub add`, `dart pub get`, `dart analyze`.
  Do NOT run `flutter build/test/run`; do NOT bypass.
- **Acceptance bar for every step:** `dart pub get` succeeds AND `dart analyze` reports **0 errors**,
  run on EVERY package modified (always `apps/user_app`; additionally `packages/shared_core`
  for the icon-facade step).
- `flutter test` / `flutter build web` are **DEFERRED** — write + keep tests, do not run them.
  Exact deferred commands in §12.

### Clean baseline CONFIRMED before planning (2026-10 run)
- `apps/user_app`: `dart pub get` → "Got dependencies!"; `dart analyze` → **"No issues found!"**.
- `packages/shared_core`: `dart pub get` → "Got dependencies!"; `dart analyze` → **"No issues found!"**.
- Both packages are at the clean baseline (0 issues). Every step below must keep them there.

### Write scope (STRICT)
- Primary: `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app\**`.
- ALSO ALLOWED (additive ONLY): new glyph mappings in
  `c:\WorkSpace\Ajinkya\Veriqoo\packages\shared_core\lib\design_system\foundations\veriqoo_icons.dart`.
  No other `shared_core` file (especially NOT `lib/services/*`). Do NOT touch `apps/admin_web/**`.
- Design system is consumed through the single barrel
  `import 'package:shared_core/design_system/design_system.dart';`. Tokens via
  `Theme.of(context).extension<VeriqooTokens>()!`; theme getters `VeriqooTheme.dark/.light`.
- Package name is `flutter_application_1` → internal imports `package:flutter_application_1/...`.
- Dependencies already present (NO `dart pub add` needed): `flutter_riverpod ^3.4.3`,
  `go_router ^18.0.2`, `supabase_flutter ^2.17.2` (postgrest 2.9.1), `flutter_secure_storage ^11.2.0`,
  `share_plus ^13.3.1`, `qr_flutter ^4.1.0`, `image_picker ^1.2.2`.

### Phase 4 inspections layer (REUSE — do not duplicate)
- `apps/user_app/lib/features/inspections/inspection_record.dart`:
  - `InspectionRecord` (immutable): `id` (raw row id as string, or `row-<index>` fallback),
    `displayId` (`VRQ-YYYYMMDD-####`), `productName`, `inspectedAt` (`DateTime?`),
    `isCompliant` (`bool?`), `missingInformation` (`List<String>`), `issueCount`,
    `violationCount`, `score` (derived), `status` (`VeriqooStatusKind`, derived),
    `timestampLabel` (`YYYY-MM-DD HH:MM` or `—`).
  - `factory InspectionRecord.fromMap(Map<String,dynamic> row, {int index = 0})` — fully defensive.
  - Top-level pure helpers `int deriveScore(...)`, `VeriqooStatusKind deriveStatus(...)`.
- `apps/user_app/lib/features/inspections/inspections_repository.dart`:
  - `class InspectionSummaryCounts { final int total; final int? flagged; }`.
  - `abstract interface class InspectionsRepository { Future<List<InspectionRecord>> recentInspections({int limit = 5}); Future<InspectionSummaryCounts> summaryCounts(); }`.
  - `class SupabaseInspectionsRepository implements InspectionsRepository` — `static const String table = 'inspections';`,
    `SupabaseInspectionsRepository({SupabaseClient? client})`, private `SupabaseClient get _client => _injected ?? Supabase.instance.client`
    (constructor NEVER touches `Supabase.instance`). RLS-scoped (NO `user_id` filter); score/status derived (never `select`ed).
- `apps/user_app/lib/features/inspections/inspections_providers.dart`:
  `inspectionsRepositoryProvider` (`Provider<InspectionsRepository>`), `recentInspectionsProvider`
  (`FutureProvider.autoDispose<List<InspectionRecord>>`), `inspectionSummaryProvider`
  (`FutureProvider.autoDispose<InspectionSummaryCounts>`).
- **The ONLY implementers of `InspectionsRepository`** are `SupabaseInspectionsRepository` (lib) and
  `FakeInspectionsRepository` (`test/home/home_harness.dart`). Adding abstract methods to the
  interface therefore forces updating BOTH or `dart analyze` fails on the test file (tests are analyzed).

### Pinned Supabase row shape (from `shared_core/lib/services/supabase_service.dart` → `saveInspectionReport`)
Table `inspections` columns written (exact keys): `product_name`, `mrp`, `net_quantity`, `manufacturer`,
`address`, `packing_date`, `customer_care`, `missing_information` (json string array),
`possible_issues` (json array of `ComplianceIssue.toJson()` maps), `is_compliant` (bool),
`ocr_text` (text), **`ai_report` (json — the full `analysis.toJson()`)**, `inspected_at`
(timestamptz ISO-8601 UTC), `image_url` (text, nullable).
- **NO `user_id`, NO `score` column.** The `inspections` table is NOT in `final_schema.sql`
  (that file models a different `inspection_sessions` structure); the table is RLS-scoped with an
  **unknown/absent primary key** — rows expose `id` only if the table has one, read null-safely via `row['id']`.
- **`ai_report` is the key to reconstructing `ComplianceAnalysis` for the detail screen** — it is the
  camelCase `analysis.toJson()`, so `ComplianceAnalysis.fromJson(row['ai_report'])` round-trips exactly.

### `ComplianceAnalysis` (`shared_core/lib/services/compliance_analysis.dart`, read-only)
Fields `productName, mrp, netQuantity, manufacturer, address, packingDate, customerCare` (all `String`),
`missingInformation` (`List<String>`), `possibleIssues` (`List<ComplianceIssue>`), `bool get isCompliant`.
`ComplianceIssue`: `title, description, severity`, `ruleNumbers/ruleTitles` (`List<String>`),
`legalBasis?`, `ocrEvidence?`, `verificationStatus` (`LegalVerificationStatus`).
`ComplianceAnalysis.fromJson(Map)` uses camelCase keys; `ComplianceIssue.fromJson(Map)` tolerant.

### Phase 6 report / finding / evidence widgets (REUSE for inspection detail — do NOT duplicate)
- `apps/user_app/lib/features/scan/result/compliance_score.dart`:
  `ComplianceScore` immutable `{int score, verified, flagged, missing, mandatoryTotal}`;
  `factory ComplianceScore.fromAnalysis(ComplianceAnalysis)` (deterministic D2 score). **This is the
  Phase 6 "score function" the task says to reuse** (NOT `deriveScore` in `InspectionRecord`, which
  stays the ledger-row score; see D3).
- `apps/user_app/lib/features/scan/result/report_finding.dart`:
  `enum ReportFindingKind { missingDeclaration, potentialViolation }`; `ReportFinding` immutable with
  `static List<ReportFinding> fromAnalysis(ComplianceAnalysis)`; plus `EvidenceLink` + pure
  `EvidenceLink linkFinding(ReportFinding, {required List<DetectedField> detectedFields, required int evidenceCount})`.
- `apps/user_app/lib/features/scan/result/widgets/product_details_panel.dart`:
  `ProductDetailsPanel({required ComplianceAnalysis analysis})` — 6 hairline rows.
- `apps/user_app/lib/features/scan/result/widgets/report_finding_tile.dart`:
  `ReportFindingTile({required ReportFinding finding, required VoidCallback onInspect})`;
  `Key reportFindingActionKey(int number)`. **Always renders an inspect/view-evidence action.**
- `apps/user_app/lib/features/scan/result/result_strings.dart`: `ResultStrings` (reuse report copy).
- Evidence viewer (REUSE): `evidence/evidence_viewer_screen.dart` (`EvidenceViewerScreen({EvidenceViewerArgs args})`),
  `evidence/evidence_viewer_args.dart` (`EvidenceViewerArgs({int initialImageIndex = 0, ReportFinding? focusFinding})`),
  route `AppRoutes.scanEvidencePath` (`/scan/evidence`). The viewer reads `scanStateProvider`
  (**in-memory session evidence only**); with an empty session it renders its own
  `VeriqooEmptyState` (ResultStrings.evidenceEmptyTitle/Message) — never throws.
- `AnalysisResultScreen` (`scan/analysis_result_screen.dart`) is the Phase 6 live-scan report; it reads
  `scanStateProvider` and `reportSharerProvider` and offers Share/QR/**Save**. **We do NOT reuse this
  screen for history detail and do NOT refactor it** (see D3) — reusing it would re-expose Save and
  risk regressing its approved Phase 6 tests.

### Design-system components (exact signatures, read from source — do NOT guess)
- `VeriqooAppBar({required String title, Widget? action, VoidCallback? onBack, bool showBack = true, double height = 56})` — single trailing `action` widget (pass a `Row` for multiple).
- `VeriqooIconButton({required IconData icon, required String semanticLabel, VoidCallback? onPressed, variant, double iconSize = 20, double size = 44})`.
- `VeriqooButton({required String label, VoidCallback? onPressed, VeriqooButtonVariant variant, VeriqooButtonSize size, IconData? icon, bool loading, bool expand, String? semanticLabel})` — variants `primary|secondary|ghost`, sizes `small|medium|large`.
- `VeriqooTextField({TextEditingController? controller, String? label, String? hintText, String? helperText, String? errorText, bool obscureText, TextInputType? keyboardType, TextInputAction? textInputAction, bool enabled, ValueChanged<String>? onChanged, ValueChanged<String>? onSubmitted, FocusNode? focusNode, IconData? prefixIcon, IconData? suffixIcon})` — hairline underline; label auto-uppercased.
- `VeriqooSectionHeader({required String title, String? subtitle, Widget? action})` — title auto-uppercased.
- `VeriqooDivider()` / `VeriqooDivider.vertical({height, indent, endIndent})` — hairline.
- `VeriqooInspectionCard({required String inspectionId, required String timestamp, required String product, required int score, required VeriqooStatusKind status, int maxScore = 100, VoidCallback? onTap})` — ledger row; shows a chevron when `onTap != null`.
- `VeriqooStatus({required VeriqooStatusKind kind, double markerSize = 16, bool showLabel = true})` — kinds `verified|flag|missing|violation` (labels VERIFIED / FLAG / NOT DETECTED / VIOLATION); shape+glyph+label, never color.
- `VeriqooScore({required int value, int maxValue = 100, double size = 120, double strokeWidth = 6, Duration duration = VeriqooMotion.cinematic, String? caption})` — radial dial, count-up, reduced-motion aware.
- `VeriqooEmptyState({required IconData icon, required String title, String? message, Widget? action})`.
- `VeriqooErrorState({String title = 'Something went wrong', String? message, VoidCallback? onRetry, String retryLabel = 'Retry', IconData icon = VeriqooIcons.alert})`.
- `VeriqooLoading({String message = 'Verifying', Size size = const Size(220,180)})`.
- `VeriqooBottomSheet.show<T>(BuildContext context, {required Widget child, String? title, bool isScrollControlled = false})`.
- Painters (`BackgroundEffect`, monochrome, auto-pause + reduced-motion aware): `ProductOutline({enabled, color})`, `ScanningLine({enabled, color})`, `InspectionGrid({enabled, color, cell})`, `TechnicalCoordinates()`.
- `VeriqooMotion.reduceMotion(context) -> bool`; durations `fast/base/slow/cinematic`; curves `enter/move/press`.
- App-local `VeriqooBackdrop({required Widget child, Widget? background})` (`lib/core/widgets/app_background.dart`) — reuse for screen backgrounds.
- `VeriqooIcons` currently exposes: `home, scan, history, profile, back, close, chevronRight, settings, search, check, alert, verified, violation, camera, upload, share, qrCode, flag, eye, zoomIn, shield`. **Lacks `filter, sort, calendar, package`** (added in Step 1). `VeriqooIcons.search` already exists.

### Routing facts (`lib/app/routes.dart`, `lib/app/router.dart`)
- Shell branch 2 = History: `GoRoute(path: AppRoutes.historyPath '/history')` → `HistoryScreen` (root, `showBack: false`),
  child `GoRoute(path: AppRoutes.historyDetailSegment ':id')` → `HistoryDetailScreen(id:)` via `sharedAxisPage`.
- Top-level over the shell: `AppRoutes.productDetailPath '/products/:id'` → `ProductDetailScreen(id:)` (`sharedAxisPage`),
  plus `notifications`, `settings`, `reportIssue`, etc. `AppRoutes.historyDetail(id)`/`AppRoutes.productDetail(id)` helpers exist.
- **No `/search` route yet** — added in Step 7.
- `HistoryScreen`, `HistoryDetailScreen`, `ProductDetailScreen` are the current PLACEHOLDERS to replace.
  The home recent list already navigates with the **raw** `record.id` via `AppRoutes.historyDetail(record.id)`
  — detail fetch-by-id depends on the raw id, so History must navigate with raw `InspectionRecord.id` too
  (the current history placeholder incorrectly passes `displayId` — fixed in Step 6).

### Hermetic-test patterns to mirror (`test/home/home_harness.dart`, `test/scan/result_harness.dart`)
- Fakes implement `InspectionsRepository` and NEVER touch `Supabase.instance`; drive loading via a
  never-completing `Completer`, error via `Future.error(...)`, data via `Future.value(...)`.
- Mount screens under a minimal `GoRouter` with keyed `Placeholder` route targets + `MaterialApp.router(theme: VeriqooTheme.dark)`.
- Pump with fixed `tester.pump(Duration)` — **never `pumpAndSettle`** (background motion loops forever).
- `sampleRecords()` builds `InspectionRecord`s through the real `fromMap`.

---

## Design decisions (grounded; one or two lines each)

- **D1 — Recent-search persistence reuses `flutter_secure_storage`** (already a direct dependency),
  NOT a new `shared_preferences` dep. Mirror the injectable `BiometricService` pattern
  (`biometricServiceProvider`) with a `RecentSearchesStore` + provider that tests override with a fake.
  Rationale: no new dependency surface; the proven best-effort try/catch pattern already exists.
- **D2 — Extend the one `InspectionsRepository` interface** with `pagedInspections`, `allInspections`,
  `inspectionById` (returns `InspectionDetail?`). It stays the single data source (no screen reads
  Supabase). Both implementers (`SupabaseInspectionsRepository` AND the test `FakeInspectionsRepository`
  in `home_harness.dart`) are updated in the SAME step so `dart analyze` never breaks.
- **D3 — Inspection detail is a NEW read-only screen that REUSES Phase 6 widgets**, not a reuse/refactor
  of `AnalysisResultScreen`. It reconstructs `ComplianceAnalysis` from the stored row and renders
  `VeriqooScore` (fed by `ComplianceScore.fromAnalysis`), `ProductDetailsPanel`, and `ReportFinding`/
  `ReportFindingTile`. Rationale: `AnalysisResultScreen` reads live `scanStateProvider`, exposes **Save**
  (task says do NOT re-save), and has approved Phase 6 tests we must not regress. The score/finding/
  product-details/evidence widgets ARE reused verbatim; only the thin screen composition is new.
- **D4 — Reconstruct the analysis from `ai_report` first, columns as fallback.**
  `InspectionDetail.fromMap(row)` → `ComplianceAnalysis.fromJson(row['ai_report'])` when `ai_report` is a
  Map (round-trips the camelCase `toJson()`); otherwise build from the flat snake_case columns
  (`product_name`, `mrp`, … `missing_information`, `possible_issues`). Pure + unit-tested.
- **D5 — Search filters client-side across ALL fields; the server supplies the newest-first corpus.**
  Searchable fields include the DERIVED display id, derived score/status, and issue text buried inside the
  `possible_issues` JSON — none server-queryable — and PostgREST filter strings risk injection. So Search
  reads `allInspections` (bounded, RLS-scoped, small per user) and applies the pure `InspectionQuery`.
- **D6 — History paginates with postgrest `.range()` for the default view; switches to load-all +
  client filter/sort when a non-default query is active.** Default (no text, status=all, sort=newest):
  `pagedInspections(offset, limit)` with "load more". Any active filter/sort: `allInspections(limit: 200)`
  once + `InspectionQuery.apply` (correct ordering/filtering across the whole set). Documented tradeoff.
- **D7 — Evidence on detail is honest about the session boundary.** Saved rows carry a single remote
  `image_url`; the Phase 6 evidence viewer is in-memory (session) only. Detail renders `image_url` inline
  read-only (bounded box, `Image.network` with loading/error builders — never throws) and still offers the
  "VIEW EVIDENCE" / per-finding inspect link into the Phase 6 viewer. Opened cold (no live session) the
  viewer shows its built-in empty state. No backend coordinates are fabricated; derived links stay DERIVED.
- **D8 — Product detail is DERIVED from inspections grouped by normalized product name**, keyed by a
  stable URL-safe hash (`product_key` = `p-<8 hex>` via a bounded polynomial hash, same technique as
  `ReportReference._stableHash6`). It fabricates no backend product entity; the UI labels the association
  DERIVED. `/products/:id` carries that product key.
- **D9 — Icon facade additions are additive-only** (Step 1): `filter`, `sort`, `calendar`, `package`.
- **D10 — Centralized copy in `HistoryStrings`** (`static const`, mirroring `HomeStrings`/`ResultStrings`),
  ready for later localization; reuse `ResultStrings` for the report pieces on the detail screen.
- **D11 — Navigation uses the raw `InspectionRecord.id`** for `/history/:id` (so `inspectionById` can fetch),
  rendering the human `displayId` in the row. This corrects the Phase 2 placeholder that passed `displayId`.

---

# Implementation Plan

- [ ] 1. Add the `filter`, `sort`, `calendar`, `package` glyphs to the `VeriqooIcons` facade (additive only).
      Append to `abstract final class VeriqooIcons` (no removals/renames):
      `static const IconData filter = LucideIcons.filter;`
      `static const IconData sort = LucideIcons.arrowUpDown;`
      `static const IconData calendar = LucideIcons.calendar;`
      `static const IconData package = LucideIcons.package;`
      (All four confirmed present in `lucide_icons_flutter 3.1.21`.) This is the ONLY `shared_core` edit permitted;
      new `static const`s cannot break `admin_web`.
      Files: `packages/shared_core/lib/design_system/foundations/veriqoo_icons.dart`.
      Verify: in `packages/shared_core` → `dart pub get` ("Got dependencies!") + `dart analyze` ("No issues found!");
      then in `apps/user_app` → `dart analyze` ("No issues found!").

- [ ] 2. Add centralized History/Search copy (`HistoryStrings`).
      `abstract final class HistoryStrings` with `static const` fields for: screen titles (`INSPECTIONS`),
      action semantic labels (search/filter/sort), date-group labels (`TODAY`, `YESTERDAY`), the ledger empty
      state (`NO INSPECTIONS` + `Your verification history will appear here after your first product analysis.`
      + `SCAN A PRODUCT`), the error title/message + retry label, the search field label/hint
      (`Product, inspection ID, manufacturer, date, or issue`), `RECENT SEARCHES`, `CLEAR`, the no-results empty
      state, filter-sheet labels (`FILTER`, `SORT`, status options ALL/VERIFIED/FLAGGED/MISSING/VIOLATION, sort
      options NEWEST/OLDEST/SCORE HIGH→LOW/SCORE LOW→HIGH, `APPLY`, `RESET`), inspection-detail labels
      (`INSPECTION`, `CAPTURED IMAGE`, not-found title/message), and product-detail labels (`PRODUCT`,
      `INSPECTION HISTORY`, the `DERIVED — grouped by product name` note, not-found title/message). Also an
      `inspectionsCount(int n)` helper (e.g. `1 INSPECTION` / `N INSPECTIONS`).
      Files: `apps/user_app/lib/features/history/history_strings.dart`.
      Verify: `apps/user_app` → `dart analyze` → "No issues found!".

- [ ] 3. Add the pure domain layer: query/filter/sort, date grouping, product derivation, and the detail model.
      All pure/data-only (no Supabase, no widgets beyond `VeriqooStatusKind` from the barrel), hence unit-testable.
      - `inspection_query.dart`: `enum InspectionStatusFilter { all, verified, flag, missing, violation }`;
        `enum InspectionSortOrder { newest, oldest, scoreHigh, scoreLow }`; immutable `InspectionQuery`
        `{String text = '', InspectionStatusFilter status = all, InspectionSortOrder sort = newest}` with a const
        ctor, `copyWith`, `bool get isActive`, pure `bool matches(InspectionRecord r)` (text matches across
        `productName`, `displayId`, raw `id`, `timestampLabel`, and each `missingInformation` entry — all
        case-insensitive `contains`; `status` maps to `r.status`), and `List<InspectionRecord> apply(List<InspectionRecord>)`
        (filter by `matches` then stable-sort by `sort`).
      - `inspection_grouping.dart`: immutable `InspectionDateGroup {String label; List<InspectionRecord> records}`;
        pure `List<InspectionDateGroup> groupByDate(List<InspectionRecord> records, {DateTime? now})` preserving
        newest-first order, labelling `TODAY` / `YESTERDAY` / `YYYY-MM-DD` (local date; records with null
        `inspectedAt` fall into a trailing `UNDATED` group). `now` is injectable for tests.
      - `product_summary.dart`: `String productKeyFor(String productName)` (`p-<8 hex>` bounded polynomial hash of
        the trimmed lower-cased name); immutable `ProductSummary {String key; String productName; int inspectionCount;
        DateTime? lastInspectedAt; int latestScore; int bestScore; List<InspectionRecord> inspections}`; pure
        `List<ProductSummary> deriveProducts(List<InspectionRecord>)` (group by key, newest-first within a group,
        groups sorted by `lastInspectedAt` desc) and `ProductSummary? findProduct(List<ProductSummary>, String key)`.
      - `inspection_detail.dart`: immutable `InspectionDetail {InspectionRecord record; ComplianceAnalysis analysis;
        String? imageUrl; String ocrText}`; `factory InspectionDetail.fromMap(Map<String,dynamic> row, {int index = 0})`
        building `record` via `InspectionRecord.fromMap`, `analysis` via a private
        `_reconstructAnalysis(row)` (D4: `ComplianceAnalysis.fromJson(Map<String,dynamic>.from(row['ai_report']))`
        inside a try when `ai_report is Map`, else build from flat columns with `possible_issues` parsed via
        `ComplianceIssue.fromJson` defensively), `imageUrl` (non-blank String or null), `ocrText` (String or '').
      Files: `apps/user_app/lib/features/inspections/inspection_query.dart`,
      `apps/user_app/lib/features/inspections/inspection_grouping.dart`,
      `apps/user_app/lib/features/inspections/product_summary.dart`,
      `apps/user_app/lib/features/inspections/inspection_detail.dart`.
      Verify: `apps/user_app` → `dart analyze` → "No issues found!".

- [ ] 4. Extend the repository (interface + Supabase impl) and the providers; update the Home test fake in lockstep.
      In `inspections_repository.dart` add to `abstract interface class InspectionsRepository`:
      `Future<List<InspectionRecord>> pagedInspections({int offset = 0, int limit = 20});`
      `Future<List<InspectionRecord>> allInspections({int limit = 200});`
      `Future<InspectionDetail?> inspectionById(String id);`
      Implement in `SupabaseInspectionsRepository` (reuse the existing `_client` + `PostgrestException` fallback idiom):
      - `pagedInspections`: `try { rows = await _client.from(table).select().order('inspected_at', ascending: false).range(offset, offset + limit - 1); } on PostgrestException { rows = await _client.from(table).select().range(offset, offset + limit - 1); }`
        then `rows.indexed.map((e) => InspectionRecord.fromMap(e.$2, index: offset + e.$1))`. (`.range(int from, int to)` confirmed on postgrest 2.9.1.)
      - `allInspections`: same as `recentInspections` but `limit` default 200 (ordered, with the unordered fallback).
      - `inspectionById`: `try { final rows = await _client.from(table).select().eq('id', id).limit(1); if (rows.isEmpty) return null; return InspectionDetail.fromMap(rows.first); } on PostgrestException { return null; }`
        (missing `id` column or no match → not-found/null; other errors propagate to the provider's error state).
      Document the additions in the class doc comment (RLS scoping, derived score/status, deferred client access unchanged).
      In `inspections_providers.dart` add: `allInspectionsProvider` (`FutureProvider.autoDispose<List<InspectionRecord>>` → `allInspections()`)
      and `inspectionDetailProvider` (`FutureProvider.autoDispose.family<InspectionDetail?, String>((ref, id) => ref.watch(inspectionsRepositoryProvider).inspectionById(id))`).
      **Update `test/home/home_harness.dart`** `FakeInspectionsRepository` to implement the 3 new methods honoring its
      existing `pending`/`fail` flags (pending → `Completer().future`; fail → `Future.error`; else
      `pagedInspections`/`allInspections` → the configured `records` window, `inspectionById` → first record whose
      `record.id`/`displayId` matches, else null). Additive only; Home tests keep compiling/passing.
      Files: `apps/user_app/lib/features/inspections/inspections_repository.dart`,
      `apps/user_app/lib/features/inspections/inspections_providers.dart`,
      `apps/user_app/test/home/home_harness.dart`.
      Verify: `apps/user_app` → `dart analyze` → "No issues found!" (confirms the postgrest `.range()`/`.eq().limit()`
      signatures type-check AND the Home test fake still satisfies the widened interface).

- [ ] 5. Add the recent-searches store (injectable, over `flutter_secure_storage`) + provider.
      `class RecentSearchesStore { RecentSearchesStore({FlutterSecureStorage? storage}) : _storage = storage ?? const FlutterSecureStorage(); ... }`
      with `static const String _key = 'veriqoo_recent_searches';` and best-effort (try/catch → safe default):
      `Future<List<String>> load()` (JSON-decode the stored list, newest-first), `Future<List<String>> add(String query)`
      (trim; ignore blanks; case-insensitive de-dupe to front; cap at 8; persist; return the new list),
      `Future<List<String>> clear()`. Expose `final recentSearchesStoreProvider = Provider<RecentSearchesStore>((ref) => RecentSearchesStore());`
      and `final recentSearchesControllerProvider = AsyncNotifierProvider<RecentSearchesController, List<String>>(RecentSearchesController.new);`
      whose `build()` calls `store.load()` and whose `add`/`clear` update state + persist. Mirror the `BiometricService` doc tone.
      Files: `apps/user_app/lib/features/history/recent_searches_store.dart`.
      Verify: `apps/user_app` → `dart analyze` → "No issues found!".

- [ ] 6. Rebuild the HISTORY ledger screen with a pagination controller, date grouping, states, pull-to-refresh,
      and the filter/sort sheet.
      Add a controller `historyControllerProvider = AsyncNotifierProvider.autoDispose<HistoryController, HistoryState>(...)`
      where immutable `HistoryState {List<InspectionRecord> items; InspectionQuery query; bool hasMore; bool loadingMore}`:
      `build()` loads page 0 via `pagedInspections(offset: 0, limit: 20)`; `loadMore()` appends the next
      `.range` page (only when `query` is default and `hasMore`); `refresh()` reloads page 0; `applyQuery(InspectionQuery q)`
      — when `q.isActive` fetch `allInspections(limit: 200)` once and store `q.apply(all)` with `hasMore=false`, else reload page 0.
      Rebuild `history_screen.dart` as a `ConsumerStatefulWidget`:
      - `Scaffold(backgroundColor: tokens.bg)` + `VeriqooAppBar(title: HistoryStrings.title /* INSPECTIONS */, showBack: false,
        action: Row([VeriqooIconButton(icon: VeriqooIcons.search → context.go(AppRoutes.searchPath)),
        VeriqooIconButton(icon: VeriqooIcons.filter → open sheet), VeriqooIconButton(icon: VeriqooIcons.sort → open sheet)]))`.
      - Body `VeriqooBackdrop(background: const TechnicalCoordinates(), child: SafeArea(...))` wrapped in a centered
        `ConstrainedBox(maxWidth: 640)` (mobile-first).
      - `ref.watch(historyControllerProvider).when(loading: VeriqooLoading, error: VeriqooErrorState(onRetry: refresh),
        data: ...)`: when `items.isEmpty && !query.isActive` → `HistoryEmpty`; else a `RefreshIndicator`(onRefresh → controller.refresh)
        wrapping a `CustomScrollView`/`ListView` of `groupByDate(items)` → per group a header (meta label TODAY/YESTERDAY/date)
        then `VeriqooInspectionCard(inspectionId: r.displayId, timestamp: r.timestampLabel, product: r.productName,
        score: r.score, status: r.status, onTap: () => context.go(AppRoutes.historyDetail(r.id)))` (RAW `r.id` — D11),
        plus a trailing load-more sentinel (scroll-extent listener → `controller.loadMore()`); when `query.isActive && items.isEmpty`
        show the no-results `VeriqooEmptyState`.
      - `HistoryEmpty` widget: `VeriqooEmptyState(icon: VeriqooIcons.history, title: NO INSPECTIONS, message: ..., action:
        VeriqooButton('SCAN A PRODUCT', variant: primary, icon: VeriqooIcons.scan → context.go(AppRoutes.scanPath)))` layered over a
        low-opacity `IgnorePointer` stack of `ProductOutline()` + `ScanningLine()` (reduced-motion handled by the painters).
      - `HistoryFilterSheet` widget: `VeriqooBottomSheet` content with status options (reuse `VeriqooStatus` markers +
        labels) and sort options; returns an `InspectionQuery` via `Navigator.pop`. The screen calls `controller.applyQuery(...)`.
      Replace the obsolete `InspectionSummary`/`historyProvider` in `history_providers.dart` with the new controller
      (nothing else references them — grep-confirmed). Add `AppRoutes.searchPath = '/search'` + `AppRoutes.searchName = 'search'`
      to `routes.dart` (the search GoRoute + screen land in Step 7).
      Files: `apps/user_app/lib/features/history/history_providers.dart` (replace),
      `apps/user_app/lib/features/history/history_screen.dart` (rebuild),
      `apps/user_app/lib/features/history/widgets/history_empty.dart`,
      `apps/user_app/lib/features/history/widgets/history_date_group.dart`,
      `apps/user_app/lib/features/history/widgets/history_filter_sheet.dart`,
      `apps/user_app/lib/app/routes.dart` (add `searchPath`/`searchName`).
      Verify: `apps/user_app` → `dart analyze` → "No issues found!".

- [ ] 7. Build the SEARCH screen and wire the `/search` route.
      `SearchScreen extends ConsumerStatefulWidget` (owns a `TextEditingController` + a local `InspectionQuery`):
      - `Scaffold(bg)` + `VeriqooAppBar(title: 'SEARCH')` (back enabled — it is pushed over the shell).
      - A large editorial `VeriqooTextField(controller:, label: 'SEARCH', hintText: HistoryStrings.searchHint,
        prefixIcon: VeriqooIcons.search, textInputAction: TextInputAction.search, onChanged: (t) => setState(update query.text),
        onSubmitted: (t) => ref.read(recentSearchesControllerProvider.notifier).add(t))`, plus a `VeriqooIconButton(VeriqooIcons.filter)`
        opening the reused `HistoryFilterSheet`.
      - When the text is empty: a `RECENT SEARCHES` section from `ref.watch(recentSearchesControllerProvider)` (tappable rows/chips
        that set the query; a `CLEAR` ghost action) and lightweight suggestions (top product names from `allInspectionsProvider`,
        best-effort).
      - When the text is non-empty: `ref.watch(allInspectionsProvider).when(loading: VeriqooLoading,
        error: VeriqooErrorState(onRetry: () => ref.invalidate(allInspectionsProvider)), data: (all) { final results = query.apply(all);
        return results.isEmpty ? VeriqooEmptyState(...) : ListView of VeriqooInspectionCard(... onTap → context.go(AppRoutes.historyDetail(r.id))); })`.
      Add the `/search` GoRoute (top-level over the shell, like `/notifications`): in `router.dart` add
      `GoRoute(path: AppRoutes.searchPath, name: AppRoutes.searchName, builder: (c, s) => const SearchScreen())` + the import.
      Files: `apps/user_app/lib/features/search/search_screen.dart`,
      `apps/user_app/lib/app/router.dart` (add route + import).
      Verify: `apps/user_app` → `dart analyze` → "No issues found!".

- [ ] 8. Rebuild the INSPECTION DETAIL screen (`/history/:id`) — read-only Phase 6 report, reconstructed from the saved row.
      Replace `HistoryDetailScreen` with a `ConsumerWidget` taking `required this.id`:
      - `ref.watch(inspectionDetailProvider(id)).when(loading: VeriqooLoading,
        error: (e, _) => VeriqooErrorState(title: HistoryStrings.detailErrorTitle, message: '...', onRetry: () => ref.invalidate(inspectionDetailProvider(id))),
        data: (detail) => detail == null ? VeriqooErrorState(title: HistoryStrings.notFoundTitle, message: HistoryStrings.notFoundMessage) : _report(context, ref, detail))`.
      - `_report` composes, in `Scaffold(bg)` + `VeriqooAppBar(title: HistoryStrings.inspectionTitle /* INSPECTION */)` + scrollable body
        (centered `ConstrainedBox(maxWidth: 640)`): header (product name tappable → `context.push(AppRoutes.productDetail(productKeyFor(detail.analysis.productName)))`,
        meta line `${detail.record.displayId} · ${detail.record.timestampLabel}` in mono/textTertiary); a centered
        `VeriqooScore(value: ComplianceScore.fromAnalysis(detail.analysis).score, caption: ResultStrings.scoreCaption, size: 160)`;
        a compact summary row of three `VeriqooStatus` markers with the `ComplianceScore` verified/flagged/missing counts;
        `VeriqooSectionHeader(title: ResultStrings.productDetailsHeader)` + `ProductDetailsPanel(analysis: detail.analysis)`;
        `VeriqooSectionHeader(title: ResultStrings.findingsHeader)` + a `ReportFindingTile` per `ReportFinding.fromAnalysis(detail.analysis)`
        (reused) whose `onInspect` pushes `AppRoutes.scanEvidencePath` with `EvidenceViewerArgs(focusFinding: finding)` (D7 — the viewer
        shows its own empty state when the session has no in-memory evidence), or the Phase 6 "all clear" line when empty;
        and, when `detail.imageUrl != null`, a `VeriqooSectionHeader(title: HistoryStrings.capturedImage)` + a bounded hairline box with
        `Image.network(detail.imageUrl!, loadingBuilder: ..., errorBuilder: ... /* never throws */)`.
      - **No Save / Share / QR actions and no `SupabaseService` call** (do NOT re-save on view).
      Keep the `HistoryDetailScreen` class name + `const HistoryDetailScreen({super.key, required this.id})` constructor (router unchanged).
      Files: `apps/user_app/lib/features/history/history_detail_screen.dart` (rebuild).
      Verify: `apps/user_app` → `dart analyze` → "No issues found!".

- [ ] 9. Rebuild the PRODUCT DETAIL screen (`/products/:id`) — a derived product summary + its inspection history.
      Add `product_providers.dart`: `final productDetailProvider = FutureProvider.autoDispose.family<ProductSummary?, String>((ref, key) async {
      final all = await ref.watch(inspectionsRepositoryProvider).allInspections(); return findProduct(deriveProducts(all), key); });`.
      Replace `ProductDetailScreen` with a `ConsumerWidget` taking `required this.id` (the product key):
      - `ref.watch(productDetailProvider(id)).when(loading: VeriqooLoading, error: VeriqooErrorState(onRetry: invalidate),
        data: (product) => product == null ? VeriqooErrorState(title: HistoryStrings.productNotFoundTitle, message: ...) : _view(context, product))`.
      - `_view`: `Scaffold(bg)` + `VeriqooAppBar(title: HistoryStrings.productTitle)` + body: product name (`VeriqooType.h1`),
        a meta line with `inspectionCount` (via `HistoryStrings.inspectionsCount`) + `lastInspectedAt` label + latest/best score (mono),
        a visible **DERIVED** note (`HistoryStrings.productDerivedNote`, textTertiary) clearly marking that the product and its
        history are synthesized by grouping inspections by product name (no backend product record); then
        `VeriqooSectionHeader(title: HistoryStrings.inspectionHistory)` + a `VeriqooInspectionCard` per `product.inspections`
        (`onTap` → `context.go(AppRoutes.historyDetail(r.id))`). Optional subtle `ProductOutline()` backdrop; `VeriqooIcons.package`
        available for the header/empty affordance.
      Files: `apps/user_app/lib/features/products/product_providers.dart`,
      `apps/user_app/lib/features/products/product_detail_screen.dart` (rebuild).
      Verify: `apps/user_app` → `dart analyze` → "No issues found!".

- [ ] 10. Add the hermetic widget/unit tests (kept; run DEFERRED) using a FAKE repository — never hit `Supabase.instance`.
      New harness `test/history/history_harness.dart`: a `FakeInspectionsRepository implements InspectionsRepository`
      (full surface: `recentInspections`, `summaryCounts`, `pagedInspections`, `allInspections`, `inspectionById`) with
      configurable `records`/`detail`/pending/fail; a `FakeRecentSearchesStore`; `sampleHistoryRecords()` (fixed timestamps
      spanning today/yesterday/older, mixed statuses) built through the real `InspectionRecord.fromMap`; and pump helpers
      (`pumpHistory`, `pumpSearch`, `pumpInspectionDetail`, `pumpProductDetail`) mounting each screen under a minimal `GoRouter`
      with keyed `Placeholder`s (`/history/:id`, `/products/:id`, `/scan`, `/scan/evidence`, `/search`) + `MaterialApp.router(theme: VeriqooTheme.dark)`,
      overriding `inspectionsRepositoryProvider` and `recentSearchesStoreProvider`. Fixed `pump`s only.
      Tests:
      - `test/history/history_logic_test.dart` (pure): `InspectionQuery.matches/apply` (text across product/displayId/id/timestamp/missing;
        status filter; each sort order); `groupByDate` with an injected `now` (TODAY/YESTERDAY/explicit date/UNDATED + newest-first order);
        `deriveProducts` grouping + count/latest/best + `productKeyFor` stability (same name → same key, case/space-insensitive) + `findProduct`;
        `InspectionDetail.fromMap` with `ai_report` present (round-trips), with `ai_report` absent (flat-column fallback incl. `possible_issues`),
        and a sparse/typed-wrong row (safe defaults, no throw).
      - `test/history/history_screen_test.dart`: LOADING (pending repo) renders without exception; EMPTY (no records) →
        `NO INSPECTIONS` + `SCAN A PRODUCT`; POPULATED → date-group headers (TODAY/YESTERDAY) + ≥1 `VeriqooInspectionCard`;
        ERROR (fail) → `VeriqooErrorState`, `tester.takeException()` null; tapping a row navigates to `/history/:id` with the RAW id;
        pull-to-refresh triggers a reload.
      - `test/history/search_screen_test.dart`: empty query shows RECENT SEARCHES from the fake store; typing filters the
        `allInspections` corpus (matching card shown, non-matching absent); submitting persists via the fake store (add called);
        the filter sheet opens; no-results shows the empty state.
      - `test/history/inspection_detail_test.dart`: renders the report from a fake saved `InspectionDetail` (score dial present,
        a `ProductDetailsPanel` row, a `ReportFindingTile`); NOT-FOUND (repo returns null) → `VeriqooErrorState`; ERROR (repo throws) →
        `VeriqooErrorState` with `takeException()` null; asserts NO Save affordance (report is read-only).
      - `test/history/product_detail_test.dart`: renders product name + `INSPECTION HISTORY` rows from fake data + the DERIVED note;
        NOT-FOUND (unknown key) → `VeriqooErrorState`.
      Files: `apps/user_app/test/history/history_harness.dart`, `history_logic_test.dart`, `history_screen_test.dart`,
      `search_screen_test.dart`, `inspection_detail_test.dart`, `product_detail_test.dart`.
      Verify: `apps/user_app` → `dart analyze` → "No issues found!" (tests compile; `test/` is analyzed). Running is DEFERRED (§12).

- [ ] 11. Full-surface analyze sweep.
      Confirm the whole package still type-checks after all screens/providers/tests are in place and that the
      existing Home/auth/scan suites still compile against the widened `InspectionsRepository`.
      Files: none (verification only).
      Verify: `apps/user_app` → `dart pub get` ("Got dependencies!") + `dart analyze` ("No issues found!");
      `packages/shared_core` → `dart analyze` ("No issues found!").

- [ ] 12. Record the DEFERRED commands (do NOT run) and confirm no commits.
      DEFERRED (run where `flutter` is permitted):
      - `cd c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app && flutter test` — runs the kept history/search/detail/product
        widget+unit tests plus the existing home/auth/scan suites.
      - `cd c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app && flutter build web` — build smoke check.
      Files: none.
      Verify: `dart pub get` + `dart analyze` green on both packages (as in Step 11). **No commits** at any point.

---

## Extended repository API handed forward (single source)

`abstract interface class InspectionsRepository`:
- `Future<List<InspectionRecord>> recentInspections({int limit = 5})` — existing (Home recent list).
- `Future<InspectionSummaryCounts> summaryCounts()` — existing (Home metrics).
- `Future<List<InspectionRecord>> pagedInspections({int offset = 0, int limit = 20})` — NEW; newest-first via `.range`, unordered fallback.
- `Future<List<InspectionRecord>> allInspections({int limit = 200})` — NEW; newest-first corpus for Search + product derivation.
- `Future<InspectionDetail?> inspectionById(String id)` — NEW; `.eq('id', id).limit(1)`; null on no-match or `PostgrestException`.

Providers (in `inspections_providers.dart` unless noted): `inspectionsRepositoryProvider`, `recentInspectionsProvider`,
`inspectionSummaryProvider` (existing); `allInspectionsProvider`, `inspectionDetailProvider` (family, NEW);
`historyControllerProvider` (history feature), `recentSearchesStoreProvider` + `recentSearchesControllerProvider`
(history feature), `productDetailProvider` (family, products feature).

## How detail / product degrade when stored data is sparse (never throw to the UI)
- No `ai_report` → `InspectionDetail._reconstructAnalysis` builds the analysis from the flat snake_case columns;
  missing/typed-wrong columns fall back to empty strings / empty lists (report renders "Not detected" rows + no findings).
- No `id` column / synthesized `row-<index>` id → `inspectionById` returns null → detail shows the NOT-FOUND `VeriqooErrorState`.
- No `image_url` → the "CAPTURED IMAGE" section is omitted; a broken URL is caught by `Image.network`'s `errorBuilder`.
- No in-memory scan session → a finding's "inspect" opens the Phase 6 evidence viewer, which renders its own empty state.
- Product with one inspection → a single-row history; `productKeyFor` is stable so re-opening resolves the same group.
- Genuine fetch failure (network / uninitialized Supabase) → the `FutureProvider` surfaces an error → `VeriqooErrorState`
  with retry. The repository constructor never touches `Supabase.instance`, so widget build never throws.

## VeriqooIcons added this phase (additive only)
`filter` → `LucideIcons.filter`; `sort` → `LucideIcons.arrowUpDown`; `calendar` → `LucideIcons.calendar`;
`package` → `LucideIcons.package`. (`search` already existed and is reused for the search action.)

## `dart analyze` trajectory
Baseline (confirmed): **0 issues** on `apps/user_app` and `packages/shared_core`. Target after every step and at
completion: **0 issues** on both. Each step is independently analyze-clean and leaves both packages buildable.
