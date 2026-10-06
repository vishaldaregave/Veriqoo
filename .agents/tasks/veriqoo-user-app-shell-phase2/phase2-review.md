# user_app application shell: GoRouter + Riverpod + branded splash + bottom-nav shell (Phase 2)

Phase 2 relocates the old monolithic `lib/main.dart` into a structured `apps/user_app` shell: a thin bootstrap, an `app/` routing layer (GoRouter with a Riverpod-driven redirect guard), a four-branch `StatefulShellRoute.indexedStack`, a branded splash, a functional Supabase login with a labelled dev bypass, minimal typed provider skeletons, and design-system placeholder screens for every route in the table. The scan→OCR→compliance-analysis→save pipeline is carried into the `/scan` branch with its service calls intact. I reviewed every `apps/user_app/lib` source file, the shell test, the pubspec, the two evidence docs, and compared the carried pipeline against the original `main.dart` in git history. I did not re-run `flutter`/`dart` suites (per the step's evidence rule, and because the workspace policy denies `flutter *` for me as well).

Watch for: (1) write scope could not be checked with a clean per-phase diff — the entire monorepo is uncommitted/untracked against `main`, so I verified scope via file modification times instead (confirmed). (2) Verification Gates 3 (`flutter build web`, both targets) and 4 (`flutter test`) were never executed — blocked by the workspace `flutter *` deny for every actor, so runtime behavior of the guard/nav and the web build remain unverified and need a human/CI to close (confirmed). (3) The carried `/scan` pipeline now passes the dotenv-resolved Gemini key into `LegalRulesRetrievalService` where the original passed none — verified a safe superset, not a regression (confirmed).

**Verdict**: APPROVED

## High-level view

The whole monorepo is uncommitted against `main` (which still holds the pre-restructure root-level app), so `git diff main` cannot isolate Phase 2 from the earlier scaffolding. I checked write scope by modification time: all user_app shell files were written in a 00:47–01:21 burst, `shared_core` source was last touched ~an hour earlier (prior day 23:53) and is untouched by this phase, and `admin_web` shows only pub-metadata timestamps that predate the Phase 2 window. No source file outside `apps/user_app/**` was modified by this phase.

Auth is a three-value state (`unknown`/`authenticated`/`unauthenticated`) exposed through a Riverpod `Notifier`; the GoRouter redirect holds on `/splash` while `unknown`, so there is no login flash, and the splash settles the state after a ~1.2s minimum. The router is exposed as a provider and refreshed through a `ValueNotifier` so auth changes re-run the redirect without rebuilding the router and dropping navigation state.

The route table matches the spec exactly: splash, five `/auth/*` routes, five cross-cutting routes presented over the shell (`/products/:id`, `/reports/:id`, `/report-issue`, `/settings`, `/notifications`), and a four-branch indexed-stack shell (Home / Scan / History / Profile) with `/scan`'s capture/processing/result and `/history/:id` nested in their branch navigators. Unmatched locations render a custom 404 built on `VeriqooErrorState`.

The scan pipeline is carried forward behavior-intact: image_picker capture → ML Kit OCR → `LegalRulesRetrievalService.retrieveLegalContext` → `GeminiAIAnalysisService.analyzeProductLabel` → push `/scan/result` → `SupabaseService.saveInspectionReport`. Services moved from `State` fields to lazy locals disposed in `finally` so the screen mounts in tests without `Supabase.initialize`; the Gemini key resolves dotenv-first then dart-define. `shared_core/services/*` is unchanged.

Design-system discipline holds: every screen consumes `package:shared_core/design_system/design_system.dart` read-only and renders real components rather than blank scaffolds; icons come only through the `VeriqooIcons` facade; no `lucide` import, no `google_fonts`, and `textTertiary` appears once as a disabled-value color, never for body copy. Providers are minimal typed skeletons.

Static verification passed via the `dart` equivalents the policy permits (`dart pub get`, `dart analyze` = No issues found). The two flutter-only gates are deferred, not failed, with an orchestrator decision to proceed on the static bar and a documented human/CI handoff. That handoff is the one real residual risk and the reason the deferral is called out prominently rather than buried.

<details>
<summary>Issues (4)</summary>

1. **Deferred build/test gates (non-blocking, needs human/CI)** — `flutter build web` (default + `gallery_main.dart`) and `flutter test` were never executed because the workspace denies `flutter *` for all actors; the guard/nav runtime behavior and the web build are unverified. A human or CI with `flutter` permitted must run the three commands to close Gates 3 and 4.
2. **Write scope verified by mtime, not a clean diff (non-blocking)** — the monorepo is fully uncommitted, so per-phase isolation can't be shown with `git diff`. mtimes confirm no source outside `apps/user_app/**` changed in the Phase 2 window; `admin_web` pub-metadata (pubspec.yaml/lock/.dart_tool) carries 00:21 timestamps that predate the window and are attributable to earlier setup. If strict isolation must be provable, confirm `admin_web/pubspec.yaml` matches its Phase-1 baseline.
3. **Retrieval service now receives the Gemini key (non-blocking, informational)** — the carried `/scan` passes the dotenv-first Gemini key into `LegalRulesRetrievalService(apiKey:)` where the original passed none. Verified safe: the service defaults to the same `GEMINI_API_KEY` and guards an empty key, and retrieval is wrapped in try/catch with a Gemini fallback. No action required.
4. **Relative import in the 404 screen (nit)** — `not_found_screen.dart` imports `'routes.dart'` relatively while the rest of the app uses absolute `package:flutter_application_1/...` imports. Cosmetic; analyze is clean.

</details>

<details>
<summary>Details</summary>

### Write scope on an uncommitted tree

`git diff main` is not usable to isolate this phase: `main` still contains the old root-level Flutter app, and the entire monorepo (`apps/`, `packages/`, `.agents/`, `final_schema.sql`) is untracked. So the diff shows the whole restructuring as root-level deletions plus untracked additions, with none of `apps/user_app`'s content visible as a tracked change. There is no clean per-phase diff to read.

I verified scope by modification time instead. Every user_app shell source file was written in one burst — pubspec at 00:47, the `lib/` tree 01:02–01:21. `shared_core`'s most recent source file (`design_gallery.dart`) is 04-10 23:53 and its `.dart_tool/version` 23:59, both well before the Phase 2 burst, so `shared_core` is untouched by this phase. `admin_web` shows 05-10 timestamps only on `pubspec.yaml` (00:21:39), `pubspec.lock` (00:21:52), and `.dart_tool/*` (00:21–00:22) — a dependency-resolution signature that predates the user_app work by ~26 minutes; its newest non-pub source files are 04-10 20:42. No source file outside `apps/user_app/**` was modified inside the Phase 2 window. The caveat worth stating plainly: because nothing is committed, this is an mtime argument rather than a diff, and the `admin_web` pub-metadata touch — though it predates the window and is not source logic — can't be attributed to a specific phase with certainty.

### Splash-gated auth with no login flash

`AuthController` is a `Notifier<AuthState>` over `Supabase.instance.client.auth`: it subscribes to `onAuthStateChange` (cancelled on dispose), starts at `unknown`, and exposes `resolve()` (reads `currentSession`) plus `set()` for tests. The redirect treats `unknown` as "hold on `/splash`", so no auth screen renders during session restore. The splash runs a 1.2s timer that calls `resolve()` and cancels the timer on dispose, so navigating away leaves no pending callback.

```
boot → /splash (unknown; redirect pins here)
        │  onAuthStateChange fires, or splash timer calls resolve()
        ▼
   authenticated ──▶ /home
   unauthenticated ─▶ /auth/login
```

The router is a `Provider<GoRouter>`; a `ValueNotifier` bumped by `ref.listen` on `authControllerProvider` and `devBypassProvider` is wired as `refreshListenable`, so auth/bypass transitions re-run the redirect without rebuilding the router (which would discard shell navigation state). The `supabase_flutter` `AuthState` name collision is handled by `hide AuthState` on the import so the three-value guard enum is the only `AuthState` in scope.

### Four-branch shell and the full route table

`StatefulShellRoute.indexedStack` hosts the four branches in nav-bar order (Home 0, Scan 1, History 2, Profile 3), each with its own navigator; `AppShell` wires `VeriqooNavigationBar` to `goBranch`, and tapping the active destination resets that branch to its root. Deep routes that belong to a branch (`/scan/capture`, `/scan/processing`, `/scan/result`, `/history/:id`) nest inside it so the bottom nav persists; the cross-cutting routes (`/products/:id`, `/reports/:id`, `/report-issue`, `/settings`, `/notifications`) are declared as siblings of the shell so they resolve at their literal absolute paths and present full-screen over the shell on the root navigator. `/scan/result` reads `state.extra as AnalysisResultArgs?` and renders the functional result screen when present, otherwise a graceful empty-state placeholder. `errorBuilder` renders `NotFoundScreen` (a `VeriqooErrorState` with the failed location and a "Go home" retry). Every path named in the task is present.

### Carry-forward scan pipeline: preserved and reachable

Comparing against `main:lib/main.dart`, the pipeline is behavior-intact: `ImagePicker` rear-camera capture, `TextRecognizer` OCR (closed in `dispose`), per-image OCR combined into a single payload, `retrieveLegalContext(...).formatted` feeding `analyzeProductLabel(combinedText, legalContext:)`, then `router.push('/scan/result', extra: AnalysisResultArgs(...))`, and `SupabaseService().saveInspectionReport(analysis:, ocrText:, primaryImage:, imageUrl:)` on the result screen.

Three intentional, documented adaptations: services moved from `State` fields to locals built inside `analyzeProduct`/`_saveReport` and disposed in `finally` (lets the screen mount in a widget test without `Supabase.initialize`); the Gemini key resolves dotenv-first then dart-define (`dotenv.isInitialized` guard) so an uninitialized dotenv in tests can't throw; and `print` became `debugPrint`.

One delta is not in the deviation list: the original constructed `LegalRulesRetrievalService()` with no arguments, while the carry-forward passes `apiKey: <dotenv-first Gemini key>`. Reading the service (shared_core, read-only) confirms this is safe — its constructor defaults `apiKey` to the same `const String.fromEnvironment('GEMINI_API_KEY', defaultValue: '')`, it guards an empty key before classifying, and the scan screen wraps `retrieveLegalContext` in try/catch with a Gemini fallback. Because `.env` carries `GEMINI_API_KEY`, the effect is that RAG retrieval now actually receives a key in normal runs instead of an empty dart-define default — a superset consistent with decision #8, not a regression. `shared_core/services/*` itself is unchanged.

The new `main()` loads dotenv then `Supabase.initialize(url:, publishableKey:)`, resolving `SUPABASE_URL`/`SUPABASE_ANON_KEY` dotenv-first with dart-define fallback and a fail-fast `StateError` when unset. The original `main()` used `String.fromEnvironment` (dart-define) and no dotenv at all, so this is both the dotenv-based init the task asked for and better aligned with the `.env` asset than a literal copy would have been.

### Login: real sign-in plus a labelled dev bypass

`LoginScreen` is a `ConsumerStatefulWidget` with real `signInWithPassword`, empty-field validation, a loading state, and `AuthException.message` surfaced on the password field with a generic fallback for other errors; on success the `onAuthStateChange` listener flips the guard and the redirect moves to `/home`. The temporary bypass sets `devBypassProvider = true` and `context.go('/home')`, and the redirect's `loggedIn = authenticated || bypass` honors it. Both the method and the button carry `// TODO(phase3): remove dev bypass`, and the button is a labelled "Enter app (dev)" secondary action — exactly the reviewable-before-Phase-3 affordance the task specified. Fields and buttons are `VeriqooTextField`/`VeriqooButton`.

### Provider skeletons and design-system discipline

The seven providers are minimal and typed: `themeModeProvider` (default dark), `networkStatusProvider` and `offlineSyncProvider` (enum + default), `scanStateProvider` (immutable state + `copyWith` + `reset`), `historyProvider` (`FutureProvider.autoDispose` returning empty), `profileProvider` (nullable), and `notificationsProvider` (empty list). `StateProvider` is imported from `flutter_riverpod/legacy.dart`, correct for Riverpod 3.x. No business logic leaks in — it stays in `shared_core`.

Every screen renders real design-system components (verified across all of them): `VeriqooAppBar`, `VeriqooSectionHeader`, `VeriqooEmptyState`/`VeriqooErrorState`, `VeriqooScore`/`VeriqooStatus`, `VeriqooScannerOverlay`, `VeriqooInspectionCard`, `VeriqooLoading`, and the background painters via a small `VeriqooBackdrop` helper — no blank scaffolds. Icons come only through `VeriqooIcons` (notifications reuses `alert` since the facade has no bell glyph, as planned); there is no `lucide` import and no `google_fonts` anywhere. `textTertiary` is used exactly once, as the color of a "Not found" placeholder value in the result screen — a disabled-state use, not body copy — so the WCAG constraint holds. Settings implements a working three-way theme switch bound to `themeModeProvider`.

### Verification posture: static passed, two gates deferred

The evidence record is honest and specific. Gate 1 (`dart pub get`) resolved cleanly and Gate 2 (`dart analyze`) reported "No issues found!" — the same analyzer and resolver `flutter` wraps, so compilation of the whole app (including the OCR→analysis→save path and the test file) is covered. Gates 3 (`flutter build web` for both `main.dart` and `gallery_main.dart`) and 4 (`flutter test`) were not executed because the workspace policy denies `flutter *` for every actor, including this reviewer; they are recorded as deferred, not failed, with an orchestrator decision to finalize Phase 2 on the static bar and an explicit list of commands for a human/CI to run.

This is the one place where approval rests on something unexecuted rather than observed. `flutter test` has never run, so the asserted behaviors — splash-holds-while-unknown, redirect to login with no session, authenticated boot to home, and nav branch switching that mounts `ScanScreen` at `/scan` — are compiled but not runtime-verified (the nav test also depends on `VeriqooNavigationBar` rendering the literal uppercase labels `HISTORY`/`SCAN`, which only an actual test run confirms). The web build is likewise unverified, including ML Kit's unconditional `dart:io` import under dart2js, which the author reasoned through but did not build. None of this is fixable by the coding agent inside this environment, which is why it is surfaced as a required human/CI follow-up rather than a change request.

</details>

<details>
<summary>File map</summary>

All paths under `apps/user_app/`. Scope confirmed by modification time; the tree is uncommitted so there is no `git diff` to link.

- `pubspec.yaml` — adds `go_router ^18.0.2`, `flutter_riverpod ^3.4.3`; no fonts/google_fonts; `.env` asset preserved.
- `lib/main.dart` — thin bootstrap: dotenv load, Supabase.initialize (dotenv-first + fail-fast guard), `runApp(ProviderScope(VeriqooApp))`.
- `lib/app/app.dart` — `VeriqooApp`: `MaterialApp.router` with both VeriqooTheme schemes + `themeModeProvider`.
- `lib/app/router.dart` — `goRouterProvider`: full route table, indexed-stack shell, redirect guard, `errorBuilder`, `/scan/result` placeholder.
- `lib/app/routes.dart` — path/name constants and helpers.
- `lib/app/transitions.dart` — `fadePage`/`sharedAxisPage`, reduce-motion aware.
- `lib/app/not_found_screen.dart` — custom 404 on `VeriqooErrorState` (relative import nit).
- `lib/shell/app_shell.dart` — Scaffold + `VeriqooNavigationBar` driving `goBranch`.
- `lib/core/providers/*` — `themeMode`, `network`, `offlineSync` skeletons.
- `lib/core/widgets/app_background.dart` — `VeriqooBackdrop` (bg + optional painter + child).
- `lib/features/auth/*` — `auth_controller` (guard + dev bypass), functional `login_screen`, four Phase-3 placeholders.
- `lib/features/scan/*` — carried `scan_screen` + `analysis_result_screen` (+ `AnalysisResultArgs`), capture/processing placeholders, `scan_providers`.
- `lib/features/{home,history,products,reports,profile,settings,notifications}/*` — DS placeholder screens + skeleton providers; settings has a working theme switch.
- `lib/features/splash/splash_screen.dart` — branded splash, timer→`resolve()`, cancelled on dispose.
- `test/app_shell_test.dart` — shell/guard/nav/scan-reachability widget tests with a `FakeAuthController` (compiles; not executed — see deferred gates). `test/widget_test.dart` deleted; `gallery_test.dart` and `compliance_analysis_test.dart` unchanged.
- Not touched: `lib/gallery_main.dart`, `packages/shared_core/**`, `apps/admin_web/**`.

</details>
