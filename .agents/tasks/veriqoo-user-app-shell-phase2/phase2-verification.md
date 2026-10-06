# VERIQOO Phase 2 — user_app Application Shell: Verification Record

Iteration: **FIRST** (no `phase2-review.json` present at start).
Work done directly in the main workspace; **no commits**, no worktree.
All commands run with cwd = `apps/user_app`.

---

> ## ⚠️ READ FIRST — Gates 3 & 4 are DEFERRED, not failed
>
> **Phase 2 is finalized as COMPLETE on the agreed static bar** (orchestrator decision:
> proceed on static verification). Gates 1, 2, and the compile half of Gate 5 PASS.
>
> **Gate 3 (`flutter build web`, both targets) and Gate 4 (`flutter test`) are DEFERRED —
> they were NOT run and NOT failed.** They are blocked by the workspace permission policy,
> which denies every `flutter *` shell command (this blocks the coding agent AND the
> orchestrator/reviewer alike — a `flutter --version` was independently confirmed denied).
> This is an **environment constraint, not a code defect.** No bypass (full-path, alias,
> snapshot, etc.) was used, by explicit instruction.
>
> **A human or CI with `flutter` permitted must run these to close the two deferred gates**
> (cwd `apps/user_app`):
> ```
> flutter build web
> flutter build web -t lib/gallery_main.dart
> flutter test
> ```
> The widget test `test/app_shell_test.dart` is intentionally kept in place so Gate 4 runs
> as soon as `flutter` is permitted.

---

## Environment constraint affecting verification

The workspace permission policy
(`C:\Users\ajink\.kiro\workspace-roots\43b1d7c01eb65299\permissions.yaml`) **denies
all `flutter *` shell commands**:

```yaml
rules:
  - capability: shell
    effect: deny
    match:
      - flutter *
```

The Dart SDK bundled with Flutter (`dart`) is **not** denied, so Gates 1, 2 (and the
compile half of Gates 3 & 5) were verified with `dart` equivalents, which use the exact
same analyzer, package resolver, and dart2js compiler Flutter wraps:

| Flutter gate command | Dart equivalent used | Covers |
|----------------------|----------------------|--------|
| `flutter pub get` | `dart pub get` | identical pub resolution |
| `flutter analyze` | `dart analyze` | identical static analysis (analysis_options.yaml) |
| `flutter build web` | *(no dart-only equivalent — needs the flutter web toolchain)* | — |
| `flutter test` | *(no dart-only equivalent — flutter_test needs the flutter test host)* | — |

`flutter build web` (both targets) and `flutter test` are therefore **DEFERRED (not
failed)**: they require the `flutter` tool, which the policy blocks for every actor in this
workspace, and neither has a `dart`-only substitute. They must be run by a human or CI with
`flutter` permitted — see the banner above for the exact commands (cwd `apps/user_app`).
No workaround was attempted, by explicit instruction.

---

## Gate results

### Gate 1 — Dependencies resolve ✅ (via `dart pub get`)
Command: `dart pub get` (equivalent to `flutter pub get`).
Result: `Got dependencies!` — no resolution errors.
Added via `flutter pub add go_router flutter_riverpod` (run earlier, before the deny took
effect): resolved **`go_router 18.0.2`**, **`flutter_riverpod 3.4.3`** (+ `riverpod 3.4.3`).
Versions were pub-resolved, not hand-picked.

### Gate 2 — Static analysis clean ✅ (via `dart analyze`)
Command: `dart analyze` (equivalent to `flutter analyze`).
Result: **`No issues found!`** — 0 errors, 0 warnings, 0 infos.

### Gate 3 — Web builds (both entrypoints) ⏸ DEFERRED (not failed — `flutter *` denied)
Commands a human/CI must run (cwd `apps/user_app`):
```
flutter build web                      # default target lib/main.dart
flutter build web -t lib/gallery_main.dart
```
Status: **DEFERRED, not failed** — `flutter *` denied workspace-wide. Static compilation of
the whole app is clean (Gate 2), which covers the Dart compile that the web build performs.

dart:io note (investigated because the carried OCR pipeline imports ML Kit): the
`google_mlkit_commons` `InputImage` library imports `dart:io` unconditionally. This does
**not** break a web build — `dart compile js` compiles `dart:io` using dart2js web stubs
(verified locally: a probe `import 'dart:io'; main(){stdout.writeln('hi');}` compiled to
JS with exit 0). Flutter web uses the same dart2js, so the import compiles; the OCR path
would only throw at runtime if invoked on web, which is expected for a mobile-only feature
and does not affect the build. `gallery_main.dart` imports only the design system
(no mobile plugins) and is expected to build as before.

### Gate 4 — Tests pass ⏸ DEFERRED (not failed — `flutter *` denied)
Command a human/CI must run (cwd `apps/user_app`):
```
flutter test
```
Status: **DEFERRED, not failed** — `flutter *` denied; `dart test` cannot host flutter
widget tests (flutter_test needs `dart:ui`). The test file **compiles cleanly** (included
in Gate 2) and is **kept in place** so this gate runs the moment `flutter` is permitted. `test/app_shell_test.dart` asserts:
- boot → `/splash` while auth is `unknown` (no login flash);
- `set(unauthenticated)` → redirect to `LoginScreen`;
- authenticated boot → `HomeScreen`;
- nav bar switches branches: tap History → `HistoryScreen`; tap Scan → `ScanScreen`
  (this also proves Gate 5's "ScanScreen mounts at /scan").
Existing `test/gallery_test.dart` and `test/compliance_analysis_test.dart` are untouched.
Tests use `tester.pump(Duration)` (not `pumpAndSettle`) to avoid hangs from the looping
scan/background animations, and inject a `FakeAuthController` so Supabase is never touched.

### Gate 5 — Scan pipeline intact & reachable ✅ (compile) / ⏸ (runtime mount via Gate 4)
Compilation of the full path is confirmed by Gate 2 (`dart analyze` clean). Traced code
path, carried forward verbatim (behavior preserved) from the old `main.dart`:

`/scan` → `ScanScreen` (`lib/features/scan/scan_screen.dart`)
→ `captureImage()` (`image_picker`, `ImageSource.camera`)
→ `runOcrOnImage()` (`google_mlkit_text_recognition` `TextRecognizer.processImage`)
→ `analyzeProduct()` builds `LegalRulesRetrievalService` + `GeminiAIAnalysisService`
   **lazily** (disposed in `finally`), resolves the Gemini key dotenv-first then
   dart-define, combines OCR text, calls `retrieveLegalContext(...).formatted`, then
   `analyzeProductLabel(combinedText, legalContext: ...)`
→ `router.push('/scan/result', extra: AnalysisResultArgs(...))`
→ `AnalysisResultScreen` (`lib/features/scan/analysis_result_screen.dart`)
→ `_saveReport()` builds `SupabaseService()` **lazily** and calls
   `saveInspectionReport(analysis:, ocrText:, primaryImage:, imageUrl:)`.

All `shared_core/services/*` imports and call signatures are unchanged; services were only
moved from fields to lazy locals so the screen can mount without `Supabase.initialize`
(required for the widget test). The runtime "ScanScreen mounts at /scan" check lives in
Gate 4.

---

## Files

### pubspec.yaml (modified)
Added `go_router: ^18.0.2`, `flutter_riverpod: ^3.4.3` (pub-resolved). No font/google_fonts
changes. `.env` asset unchanged.

### lib/ — created
```
lib/main.dart                                  [REWRITTEN] thin bootstrap (dotenv + Supabase.initialize + runApp(ProviderScope(VeriqooApp)))
lib/app/app.dart                               VeriqooApp (ConsumerWidget) → MaterialApp.router (light+dark themes, themeModeProvider)
lib/app/router.dart                            goRouterProvider: full route table, StatefulShellRoute.indexedStack, redirect guard, errorBuilder
lib/app/routes.dart                            AppRoutes path/name constants + helpers
lib/app/transitions.dart                       fadePage() / sharedAxisPage() (VeriqooMotion, reduce-motion aware)
lib/app/not_found_screen.dart                  NotFoundScreen (VeriqooErrorState)
lib/shell/app_shell.dart                       AppShell: Scaffold + VeriqooNavigationBar + StatefulNavigationShell
lib/core/providers/theme_mode_provider.dart    themeModeProvider (StateProvider<ThemeMode>, default dark)
lib/core/providers/network_provider.dart       NetworkStatus enum + networkStatusProvider (skeleton)
lib/core/providers/offline_sync_provider.dart  OfflineSyncStatus enum + offlineSyncProvider (skeleton)
lib/core/widgets/app_background.dart           VeriqooBackdrop (token bg + optional painter + child)
lib/features/splash/splash_screen.dart         SplashScreen (VeriqooLoading motif; resolve() after ~1.2s; timer cancelled on dispose)
lib/features/auth/auth_controller.dart         AuthState enum + AuthController(Notifier) + authControllerProvider + devBypassProvider
lib/features/auth/login_screen.dart            FUNCTIONAL Supabase email/pw sign-in + TEMP dev bypass (TODO(phase3))
lib/features/auth/signup_screen.dart           placeholder (Phase 3)
lib/features/auth/otp_screen.dart              placeholder (Phase 3)
lib/features/auth/forgot_password_screen.dart  placeholder (Phase 3)
lib/features/auth/reset_password_screen.dart   placeholder (Phase 3)
lib/features/home/home_screen.dart             placeholder (InspectionGrid bg; Start inspection → /scan)
lib/features/scan/scan_screen.dart             CARRY-FORWARD OCR+analyze pipeline (relocated from main.dart)
lib/features/scan/analysis_result_screen.dart  CARRY-FORWARD result + SupabaseService save + AnalysisResultArgs
lib/features/scan/scan_capture_screen.dart     placeholder (VeriqooScannerOverlay)
lib/features/scan/scan_processing_screen.dart  placeholder (OCROverlay bg + VeriqooLoading)
lib/features/scan/scan_providers.dart          ScanState + ScanController + scanStateProvider (skeleton)
lib/features/history/history_screen.dart       placeholder (TechnicalCoordinates bg; historyProvider; empty state / cards)
lib/features/history/history_detail_screen.dart placeholder (/history/:id; ProductOutline bg, VeriqooScore/Status)
lib/features/history/history_providers.dart    InspectionSummary + historyProvider (skeleton, empty)
lib/features/products/product_detail_screen.dart placeholder (/products/:id; ProductOutline bg)
lib/features/reports/report_detail_screen.dart placeholder (/reports/:id; ComplianceMarkers bg, VeriqooScore/Status)
lib/features/reports/report_issue_screen.dart  placeholder (/report-issue; DataTicker bg; form + no-op submit SnackBar)
lib/features/profile/profile_screen.dart       placeholder (VerificationPulse bg; nav rows → /settings, /notifications)
lib/features/profile/profile_providers.dart    UserProfile + profileProvider (skeleton)
lib/features/settings/settings_screen.dart     FUNCTIONAL 3-way theme switch (themeModeProvider)
lib/features/notifications/notifications_screen.dart placeholder (DataTicker bg; empty state)
lib/features/notifications/notification_providers.dart AppNotification + notificationsProvider (skeleton)
```

### test/ — changes
```
test/app_shell_test.dart   [CREATED]  Gate 4/5 shell + redirect + nav + scan-reachability
test/widget_test.dart      [DELETED]  replaced (was a non-test runApp stub)
test/gallery_test.dart     [unchanged]
test/compliance_analysis_test.dart [unchanged]
```

### Not touched
`lib/gallery_main.dart` (separate entrypoint), `packages/shared_core/**`,
`apps/admin_web/**`.

---

## Full route table (as implemented in `lib/app/router.dart`)

Initial location `/splash`. Root navigator for top-level routes + error page.

| Path | Name | Screen | Placement | Transition |
|------|------|--------|-----------|------------|
| `/splash` | `splash` | `SplashScreen` | top-level | default |
| `/auth/login` | `login` | `LoginScreen` (functional + dev bypass) | top-level | default |
| `/auth/signup` | `signup` | `SignupScreen` | top-level | default |
| `/auth/otp` | `otp` | `OtpScreen` | top-level | default |
| `/auth/forgot-password` | `forgotPassword` | `ForgotPasswordScreen` | top-level | default |
| `/auth/reset` | `resetPassword` | `ResetPasswordScreen` | top-level | default |
| `/products/:id` | `productDetail` | `ProductDetailScreen` | top-level over shell | sharedAxis |
| `/reports/:id` | `reportDetail` | `ReportDetailScreen` | top-level over shell | sharedAxis |
| `/report-issue` | `reportIssue` | `ReportIssueScreen` | top-level over shell | default |
| `/settings` | `settings` | `SettingsScreen` (functional theme switch) | top-level over shell | default |
| `/notifications` | `notifications` | `NotificationsScreen` | top-level over shell | default |
| `/home` | `home` | `HomeScreen` | branch 0 | fade |
| `/scan` | `scan` | `ScanScreen` (carry-forward) | branch 1 | fade |
| `/scan/capture` | `scanCapture` | `ScanCaptureScreen` | branch 1 child | default |
| `/scan/processing` | `scanProcessing` | `ScanProcessingScreen` | branch 1 child | default |
| `/scan/result` | `scanResult` | `AnalysisResultScreen` (from `extra`) / placeholder | branch 1 child | default |
| `/history` | `history` | `HistoryScreen` | branch 2 | default |
| `/history/:id` | `historyDetail` | `HistoryDetailScreen` | branch 2 child | sharedAxis |
| `/profile` | `profile` | `ProfileScreen` | branch 3 | default |
| (no match) | — | `NotFoundScreen` (`VeriqooErrorState`) | `errorBuilder` | default |

Branch order = `VeriqooNavigationDestination.defaults`: Home(0), Scan(1, emphasized),
History(2), Profile(3).

---

## Implementation notes / deviations from the plan (grounded in the real packages)

1. **Riverpod 3.4.3 legacy import.** `StateProvider` is `@publicInLegacy` and is exported
   from `package:flutter_riverpod/legacy.dart`, **not** the main barrel. Files using
   `StateProvider` (theme_mode, network, offline_sync, notifications, auth devBypass) import
   `legacy.dart`. `Notifier`/`NotifierProvider`/`Provider`/`FutureProvider` come from the
   main barrel. (`dart analyze` caught the missing export and it was fixed.)
2. **`AuthState` name collision.** `supabase_flutter` exports its own `AuthState`. The guard
   enum is also named `AuthState` (per the plan), so `auth_controller.dart` and
   `login_screen.dart` import supabase with `hide AuthState`; stream payload member access
   (`data.session`) still resolves via inference.
3. **Theme getters, not methods.** Used `VeriqooTheme.dark` / `.light` (getters), matching
   `gallery_main.dart` (the task brief's `VeriqooTheme.dark()` was wrong).
4. **Gemini key dotenv-first.** `_geminiApiKey()` reads `dotenv.maybeGet('GEMINI_API_KEY')`
   guarded by `dotenv.isInitialized`, then falls back to
   `String.fromEnvironment('GEMINI_API_KEY')` — a superset of the old behavior that also uses
   the key already in `.env`, and safe when dotenv is uninitialized (tests).
5. **`print` → `debugPrint`** in the carried scan screen (avoids the `avoid_print` lint).
6. **Lazy services** (`GeminiAIAnalysisService`, `LegalRulesRetrievalService`,
   `SupabaseService`) built inside their action methods so screens mount without
   `Supabase.initialize`.
