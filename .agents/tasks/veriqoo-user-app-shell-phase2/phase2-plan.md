# VERIQOO Phase 2 — user_app Application Shell: Implementation Plan

Planning mode: **no approved design doc was supplied**, so this plan makes the design
decisions itself (grounded in the real codebase) and records a one–two sentence rationale
for each. Scope is **STRICT**: modify only files under `apps/user_app/**`. `packages/shared_core/**`
and `apps/admin_web/**` are consumed read-only and must not change.

Work directly in the main workspace `c:\WorkSpace\Ajinkya\Veriqoo` — no git worktree, no commits.

---

## 0. Facts confirmed by reading the code (so the coder does not re-guess)

### Toolchain / project shape
- Flutter 3.47.4 • Dart 3.13.3 (stable). Verified via `flutter --version`.
- Monorepo with **no melos / no root workspace**. `apps/user_app` is a standalone Flutter app
  that depends on `shared_core` via a path dependency (`shared_core: { path: ../../packages/shared_core }`).
- **All build/test commands run from `apps/user_app/`.**
- `apps/user_app` pubspec `name:` is **`flutter_application_1`** → test imports use
  `package:flutter_application_1/...`. (Decision: keep this name; renaming ripples across
  android/ios/web manifests and is out of scope.)
- Dart SDK constraint in user_app pubspec: `sdk: ^3.9.2`.
- Fonts (Inter, IBMPlexMono) are **bundled in `shared_core`** and wired by `VeriqooTheme`.
  Add **no** fonts and do **not** add `google_fonts`.
- `lucide_icons_flutter` lives only in `shared_core` and is wrapped by `VeriqooIcons`. user_app
  must **never** import lucide directly.
- `.env` (asset of user_app, already in pubspec `assets:`) contains keys:
  `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`.

### Design-system public API (import barrel `package:shared_core/design_system/design_system.dart`)

**Theme entry points are GETTERS, not methods** — use `VeriqooTheme.dark` / `VeriqooTheme.light`
(NO parentheses). The task brief wrote `VeriqooTheme.dark()`; that is wrong — `veriqoo_theme.dart`
and `gallery_main.dart` both use the getters.

Resolve tokens with `Theme.of(context).extension<VeriqooTokens>()!`.

- **VeriqooTokens** fields: `brightness, bg, bgTrue, surface, surfaceRaised, borderHairline,
  borderStrong, textPrimary, textSecondary, textTertiary, inverseBg, inverseText`.
  WCAG: `textTertiary` is for large/decorative/disabled/meta only — **never body copy**. Use
  `textPrimary`/`textSecondary` for readable text.
- **VeriqooType** text styles (color is null; widgets apply token color): `display, h1, h2, h3,
  bodyL, body, caption, meta, mono`. Font family consts: `kInterFamily`, `kMonoFamily`.
  `meta` is for small UPPERCASE labels — call `.toUpperCase()` at the call site.
- **VeriqooColors** ramp (prefer tokens over raw): `black, deepBlack, charcoal, graphite,
  borderStrongDark, midGrey, lightGrey, borderGrey, offWhite, white`.
- **VeriqooSpacing**: `s4,s8,s12,s16,s24,s32,s48,s64,s80,s96` (doubles).
- **VeriqooRadius**: `none(0), sm(6), md(10), lg(20)`; `noneAll, smAll, mdAll, lgAll`; `top(r)`.
- **VeriqooMotion**: durations `fast(160ms), base(240ms), slow(320ms), cinematic(700ms)`; curves
  `enter(easeOutCubic), move(easeInOutCubic), press(easeOutCubic)`; `pressSpring`;
  `reduceMotion(context) -> bool`.
- **VeriqooElevation**: `softShadow` (the only shadow), `translucentSurface`.
- **VeriqooIcons** (the ONLY allowed glyph source — 15 glyphs): `home, scan, history, profile,
  back, close, chevronRight, settings, search, check, alert, verified, violation, camera, upload`.
  Where a screen wants a glyph not in this set (e.g. notifications bell), reuse the closest facade
  entry (e.g. `alert`). Do not import lucide.

**Component constructors (read & confirmed):**
- `VeriqooButton({required String label, VoidCallback? onPressed, VeriqooButtonVariant variant=primary,
  VeriqooButtonSize size=medium, IconData? icon, bool loading=false, bool expand=false, String? semanticLabel})`.
  `VeriqooButtonVariant{primary,secondary,ghost}`, `VeriqooButtonSize{small,medium,large}`.
- `VeriqooIconButton({required IconData icon, required String semanticLabel, VoidCallback? onPressed,
  VeriqooIconButtonVariant variant=ghost, double iconSize=20, double size=44})`. `{ghost,outline}`.
- `VeriqooTextField({TextEditingController? controller, String? label, String? hintText, String? helperText,
  String? errorText, bool obscureText=false, TextInputType? keyboardType, TextInputAction? textInputAction,
  bool enabled=true, ValueChanged<String>? onChanged, ValueChanged<String>? onSubmitted, FocusNode? focusNode,
  IconData? prefixIcon, IconData? suffixIcon})`.
- `VeriqooAppBar({required String title, Widget? action, VoidCallback? onBack, bool showBack=true,
  double height=56})` — implements `PreferredSizeWidget`; back auto-hidden when `!Navigator.canPop(context)`.
- `VeriqooNavigationBar({required int currentIndex, required ValueChanged<int> onDestinationSelected,
  List<VeriqooNavigationDestination> destinations = VeriqooNavigationDestination.defaults})`.
  `.defaults` = Home, **Scan (emphasized)**, History, Profile — exactly our 4 branches in order.
- `VeriqooSectionHeader({required String title, Widget? action, String? subtitle})` (title uppercased).
- `VeriqooDivider({double? height, double indent=0, double endIndent=0})` + `VeriqooDivider.vertical({...})`.
- `VeriqooStatus({required VeriqooStatusKind kind, double markerSize=16, bool showLabel=true})`.
  `VeriqooStatusKind{verified,flag,missing,violation}`.
- `VeriqooScore({required int value, int maxValue=100, double size=120, double strokeWidth=6,
  Duration duration=VeriqooMotion.cinematic, String? caption})`.
- `VeriqooInspectionCard({required String inspectionId, required String timestamp, required String product,
  required int score, required VeriqooStatusKind status, int maxScore=100, VoidCallback? onTap})`.
- `VeriqooBottomSheet({required Widget child, String? title})` + static `show<T>(context,{required child,title,isScrollControlled=false})`.
- `VeriqooModal({required String title, required Widget child, List<Widget> actions=const[], bool showClose=true})`
  + static `show<T>(context,{required title,required child,actions,showClose,barrierDismissible})`.
- `VeriqooLoading({String message='Verifying', Size size=const Size(220,180)})`.
- `VeriqooEmptyState({required IconData icon, required String title, String? message, Widget? action})`.
- `VeriqooErrorState({String title='Something went wrong', String? message, VoidCallback? onRetry,
  String retryLabel='Retry', IconData icon=VeriqooIcons.alert})`.
- `VeriqooScannerOverlay({Widget? child, String? hint='Align the label within the frame', bool enabled=true,
  List<ScanField> fields=VerificationScan.defaultFields})`.
- `VerificationScan({Widget? child, List<ScanField> fields=defaultFields, bool enabled=true, bool loop=true,
  Duration duration=1600ms, Duration stagger=40ms, Color? color, double cornerLength=18, double sweepThickness=1.5})`.
- Background painters — all `const X({Key? key, bool enabled=true, Color? color})`, paint `Size.infinite`
  BELOW content, auto-pause offscreen/reduced-motion. Exact class names:
  **`InspectionGrid, ScanningLine, OCROverlay, DataTicker, ProductOutline, VerificationPulse,
  ComplianceMarkers, TechnicalCoordinates`** (note `OCROverlay`, not `OcrOverlay`).

### Services to preserve & consume (read-only, in `shared_core/lib/services/`)
- `compliance_analysis.dart` → `ComplianceAnalysis`, `ComplianceIssue`, `LegalVerificationStatus`,
  `AIAnalysisException`. `ComplianceAnalysis` fields: `productName, mrp, netQuantity, manufacturer,
  address, packingDate, customerCare, missingInformation(List<String>), possibleIssues(List<ComplianceIssue>)`,
  getter `isCompliant`. `ComplianceIssue({required title, description, severity, ruleNumbers=[], ruleTitles=[],
  legalBasis, ocrEvidence, verificationStatus=generalObservation})`.
- `gemini_ai_analysis_service.dart` → `GeminiAIAnalysisService({String? apiKey, String model='gemini-3.6-flash',
  http.Client? client})`; `Future<ComplianceAnalysis> analyzeProductLabel(String extractedText, {String legalContext=''})`;
  `dispose()`. apiKey defaults to `String.fromEnvironment('GEMINI_API_KEY')`.
- `legal_rules_retrieval_service.dart` → `LegalRulesRetrievalService({String? apiKey, SupabaseClient? client,
  http.Client? httpClient})`; `Future<LegalRulesContext> retrieveLegalContext(String ocrText)`; result has
  `.formatted`; `dispose()`.
- `supabase_service.dart` → `SupabaseService({SupabaseClient? client})`; `Future<void> saveInspectionReport(
  {required ComplianceAnalysis analysis, required String ocrText, XFile? primaryImage, String? imageUrl,
  DateTime? inspectedAt})`.

### Current `main.dart` (the pipeline we must carry forward)
`main()` does: `WidgetsFlutterBinding.ensureInitialized()` → `dotenv.load(".env")` → read
`SUPABASE_URL` and `SUPABASE_ANON_KEY`/`SUPABASE_KEY` → `Supabase.initialize(url:, publishableKey:)`
→ `runApp(...)`. The working product flow lives in `ScanScreen` (image_picker camera capture →
`google_mlkit_text_recognition` OCR → combine text → `LegalRulesRetrievalService.retrieveLegalContext`
→ `GeminiAIAnalysisService.analyzeProductLabel` → `AnalysisResultScreen` → `SupabaseService().saveInspectionReport`).
Today Gemini key is read via `String.fromEnvironment('GEMINI_API_KEY')`.

### Existing tests (must keep green; they only touch shared_core)
- `test/gallery_test.dart` — pumps `DesignGallery` + core components. Keep passing (no changes needed).
- `test/compliance_analysis_test.dart` — ComplianceIssue/Analysis JSON. Keep passing.
- `test/widget_test.dart` — **not a real test** (just `main(){runApp(...)}`, zero `test`/`testWidgets`).
  This plan **replaces** it with the Phase-2 shell widget tests (Gate 4).

---

## Design decisions (made here; no design doc existed)

1. **State management**: `flutter_riverpod` with `ProviderScope` at the root and
   `MaterialApp.router`. GoRouter is exposed as a `Provider<GoRouter>` so the redirect can read
   auth state. Rationale: task mandates Riverpod + GoRouter; a provider-exposed router is the
   standard way to let the guard observe Riverpod state.
2. **Theme**: root supplies both `theme: VeriqooTheme.light` and `darkTheme: VeriqooTheme.dark`
   with `themeMode` from `themeModeProvider` (default `ThemeMode.dark`). Supplying both themes means
   `ThemeMode.system` honors the OS while the default stays dark. Rationale: satisfies "default dark,
   honor system" without custom logic.
3. **Routing shape**: four `StatefulShellBranch`es in a `StatefulShellRoute.indexedStack`
   (Home/Scan/History/Profile), each with its own navigator. **Natural deep routes nest inside their
   branch** (`/scan/capture`, `/scan/processing`, `/scan/result`, `/history/:id`) so the bottom nav
   persists and per-branch back stacks work. **Cross-cutting detail/utility routes**
   (`/products/:id`, `/reports/:id`, `/report-issue`, `/settings`, `/notifications`) are declared as
   **top-level routes over the shell** so their exact absolute paths (as the task lists them) resolve
   and they present full-screen with a `VeriqooAppBar` back button. Rationale: go_router child paths
   are relative, so nesting `/settings` under `/profile` would force `/profile/settings`; top-level
   placement preserves the literal paths the task specified.
4. **Auth guard**: `AuthState{unknown,authenticated,unauthenticated}` via a Riverpod `Notifier`
   backed by `Supabase.instance.client.auth` (`currentSession` + `onAuthStateChange`). Start at
   `unknown` so the splash shows with no login flash; settle on the first `onAuthStateChange` event
   and/or an explicit `resolve()` the splash calls after its minimum display. Rationale: deterministic,
   testable, matches the "restore session in background, then redirect" requirement.
5. **Dev bypass**: a `devBypassProvider` (StateProvider<bool>, default false) that the redirect
   treats as "logged in". The login screen's TEMP "Enter app (dev)" sets it true and `go('/home')`.
   Marked `// TODO(phase3): remove dev bypass`. Rationale: makes the app reviewable before Phase 3
   auth without a real session, and the guard still enforces redirects otherwise.
6. **Scan result navigation**: scan → result uses `context.push('/scan/result', extra: AnalysisResultArgs(...))`;
   the `/scan/result` route renders the functional `AnalysisResultScreen` when `state.extra` is present,
   else a graceful placeholder. Rationale: keeps the result within the Scan branch navigator, satisfies
   "placeholder route" + "functional carry-forward" without a global store.
7. **Carried services are constructed lazily** inside the action methods that use them
   (`analyzeProduct`, `_saveReport`), not as `State` fields. Behavior is identical, but the screen can
   be mounted in a widget test without `Supabase.initialize` (field-level `LegalRulesRetrievalService()`/
   `SupabaseService()` would hit `Supabase.instance` at construction and throw). Rationale: required for
   the Gate-4/Gate-5 widget test to mount `/scan`.
8. **Gemini key resolution** in the carried scan screen: `dotenv.env['GEMINI_API_KEY'] ??
   const String.fromEnvironment('GEMINI_API_KEY', defaultValue: '')`, wrapped so a not-initialized
   dotenv in tests falls back instead of throwing. Rationale: strict superset of today's behavior
   (dart-define still works) and actually uses the key already present in `.env`.
9. **Motion**: `VeriqooMotion` tokens drive GoRouter `CustomTransitionPage`s — an immersive fade for
   the Home and Scan branch roots, a shared-axis (slide+fade) for list→detail (`/history/:id`). Honor
   `VeriqooMotion.reduceMotion`. Other routes use the default transition. Rationale: "apply where easy,
   don't over-engineer".
10. **Riverpod/go_router API notes for the coder**: use `Notifier`/`NotifierProvider(Controller.new)`,
    `StateProvider`, `Provider`, `FutureProvider`, `ConsumerWidget`/`ConsumerStatefulWidget`; in the
    redirect read `state.matchedLocation` and `state.pathParameters` (go_router ≥ 7). Do not hand-pick
    versions — `flutter pub add` resolves them.

---

## New `apps/user_app/lib/` directory layout & file manifest

Legend: **[C]** create, **[R]** rewrite existing, **[=]** keep unchanged.

```
apps/user_app/
├── pubspec.yaml                                [R]  (+ go_router, flutter_riverpod via `flutter pub add`)
├── test/
│   ├── app_shell_test.dart                     [C]  Gate 4/5 shell + redirect + nav + scan-reachability tests
│   ├── gallery_test.dart                       [=]
│   ├── compliance_analysis_test.dart           [=]
│   └── widget_test.dart                         →   DELETE (replaced by app_shell_test.dart)
└── lib/
    ├── main.dart                               [R]  thin bootstrap: dotenv + Supabase.initialize + runApp(ProviderScope(VeriqooApp))
    ├── gallery_main.dart                       [=]  separate gallery entrypoint — DO NOT TOUCH
    ├── app/
    │   ├── app.dart                            [C]  VeriqooApp (ConsumerWidget) -> MaterialApp.router
    │   ├── router.dart                         [C]  goRouterProvider: route table + StatefulShellRoute + redirect + errorBuilder
    │   ├── routes.dart                         [C]  route path + name string constants
    │   └── transitions.dart                    [C]  fadePage() / sharedAxisPage() CustomTransitionPage helpers
    ├── shell/
    │   └── app_shell.dart                      [C]  Scaffold + VeriqooNavigationBar wrapping StatefulNavigationShell
    ├── core/
    │   ├── providers/
    │   │   ├── theme_mode_provider.dart        [C]  themeModeProvider (StateProvider<ThemeMode>, default dark)
    │   │   ├── network_provider.dart           [C]  NetworkStatus enum + networkStatusProvider (skeleton)
    │   │   └── offline_sync_provider.dart      [C]  OfflineSyncStatus enum + offlineSyncProvider (skeleton)
    │   └── widgets/
    │       └── app_background.dart             [C]  VeriqooBackdrop (Stack: token bg + optional painter + child)
    └── features/
        ├── splash/
        │   └── splash_screen.dart              [C]  branded splash (VeriqooLoading / VerificationScan), calls auth resolve()
        ├── auth/
        │   ├── auth_controller.dart            [C]  AuthState enum + AuthController(Notifier) + authControllerProvider + devBypassProvider
        │   ├── login_screen.dart               [C]  FUNCTIONAL email/pw sign-in + TEMP dev bypass
        │   ├── signup_screen.dart              [C]  placeholder (Phase 3)
        │   ├── otp_screen.dart                 [C]  placeholder (Phase 3)
        │   ├── forgot_password_screen.dart     [C]  placeholder (Phase 3)
        │   └── reset_password_screen.dart      [C]  placeholder (Phase 3)
        ├── home/
        │   └── home_screen.dart                [C]  placeholder using DS (InspectionGrid bg)
        ├── scan/
        │   ├── scan_screen.dart                [C]  CARRY-FORWARD OCR+analyze pipeline (relocated from main.dart)
        │   ├── scan_capture_screen.dart        [C]  placeholder (VeriqooScannerOverlay)
        │   ├── scan_processing_screen.dart     [C]  placeholder (VeriqooLoading + OCROverlay bg)
        │   ├── analysis_result_screen.dart     [C]  CARRY-FORWARD result + SupabaseService save; AnalysisResultArgs
        │   └── scan_providers.dart             [C]  ScanState + ScanController + scanStateProvider (skeleton)
        ├── history/
        │   ├── history_screen.dart             [C]  placeholder (TechnicalCoordinates bg, VeriqooEmptyState / cards)
        │   ├── history_detail_screen.dart      [C]  placeholder (/history/:id)
        │   └── history_providers.dart          [C]  InspectionSummary + historyProvider (skeleton)
        ├── products/
        │   └── product_detail_screen.dart      [C]  placeholder (/products/:id)
        ├── reports/
        │   ├── report_detail_screen.dart       [C]  placeholder (/reports/:id)
        │   └── report_issue_screen.dart        [C]  placeholder (/report-issue)
        ├── profile/
        │   ├── profile_screen.dart             [C]  placeholder (VerificationPulse bg, nav rows to settings/notifications)
        │   └── profile_providers.dart          [C]  UserProfile + profileProvider (skeleton)
        ├── settings/
        │   └── settings_screen.dart            [C]  placeholder + FUNCTIONAL theme-mode switch (themeModeProvider)
        └── notifications/
            ├── notifications_screen.dart       [C]  placeholder (VeriqooEmptyState)
            └── notification_providers.dart     [C]  AppNotification + notificationsProvider (skeleton)
```

---

## Complete route table

Initial location: **`/splash`**. Root navigator key used for top-level routes + error page.

| Path | Name | Screen | Placement | Transition |
|------|------|--------|-----------|------------|
| `/splash` | `splash` | `SplashScreen` | top-level | default |
| `/auth/login` | `login` | `LoginScreen` (functional + dev bypass) | top-level | default |
| `/auth/signup` | `signup` | `SignupScreen` (placeholder) | top-level | default |
| `/auth/otp` | `otp` | `OtpScreen` (placeholder) | top-level | default |
| `/auth/forgot-password` | `forgotPassword` | `ForgotPasswordScreen` (placeholder) | top-level | default |
| `/auth/reset` | `resetPassword` | `ResetPasswordScreen` (placeholder) | top-level | default |
| `/products/:id` | `productDetail` | `ProductDetailScreen` | top-level over shell | sharedAxis |
| `/reports/:id` | `reportDetail` | `ReportDetailScreen` | top-level over shell | sharedAxis |
| `/report-issue` | `reportIssue` | `ReportIssueScreen` | top-level over shell | default |
| `/settings` | `settings` | `SettingsScreen` (functional theme switch) | top-level over shell | default |
| `/notifications` | `notifications` | `NotificationsScreen` | top-level over shell | default |
| `/home` | `home` | `HomeScreen` | **branch 0** | fade |
| `/scan` | `scan` | `ScanScreen` (carry-forward) | **branch 1** | fade |
| `/scan/capture` | `scanCapture` | `ScanCaptureScreen` | branch 1 child | default |
| `/scan/processing` | `scanProcessing` | `ScanProcessingScreen` | branch 1 child | default |
| `/scan/result` | `scanResult` | `AnalysisResultScreen` (from `extra`) / placeholder | branch 1 child | default |
| `/history` | `history` | `HistoryScreen` | **branch 2** | default |
| `/history/:id` | `historyDetail` | `HistoryDetailScreen` | branch 2 child | sharedAxis |
| `/profile` | `profile` | `ProfileScreen` | **branch 3** | default |
| (no match) | — | `NotFoundScreen` (`VeriqooErrorState`) | `errorBuilder` | default |

Branch order = nav-bar `VeriqooNavigationDestination.defaults` order: Home(0), Scan(1, emphasized),
History(2), Profile(3).

---

## Splash / auth-guard / redirect logic

**`AuthController` (`features/auth/auth_controller.dart`)**
```dart
enum AuthState { unknown, authenticated, unauthenticated }

class AuthController extends Notifier<AuthState> {
  StreamSubscription<AuthState>? _sub; // over onAuthStateChange
  @override
  AuthState build() {
    final auth = Supabase.instance.client.auth;
    final sub = auth.onAuthStateChange.listen((data) {
      state = data.session != null ? AuthState.authenticated : AuthState.unauthenticated;
    });
    ref.onDispose(sub.cancel);
    return AuthState.unknown; // show splash, no login flash
  }

  /// Called by the splash after its minimum display to settle from the restored session.
  void resolve() {
    final session = Supabase.instance.client.auth.currentSession;
    state = session != null ? AuthState.authenticated : AuthState.unauthenticated;
  }
}

final authControllerProvider = NotifierProvider<AuthController, AuthState>(AuthController.new);
final devBypassProvider = StateProvider<bool>((ref) => false); // TODO(phase3): remove dev bypass
```

**Router guard (`app/router.dart`)**
```dart
final rootNavigatorKey = GlobalKey<NavigatorState>();

final goRouterProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier<int>(0);
  ref.onDispose(refresh.dispose);
  ref.listen(authControllerProvider, (_, __) => refresh.value++);
  ref.listen(devBypassProvider, (_, __) => refresh.value++);

  return GoRouter(
    navigatorKey: rootNavigatorKey,
    initialLocation: '/splash',
    refreshListenable: refresh,
    redirect: (context, state) {
      final auth = ref.read(authControllerProvider);
      final bypass = ref.read(devBypassProvider);
      final loc = state.matchedLocation;
      final onSplash = loc == '/splash';
      final onAuth = loc.startsWith('/auth');
      if (auth == AuthState.unknown) return onSplash ? null : '/splash';
      final loggedIn = auth == AuthState.authenticated || bypass;
      if (!loggedIn) return onAuth ? null : '/auth/login';
      if (onSplash || onAuth) return '/home';
      return null;
    },
    routes: [ /* see route table */ ],
    errorBuilder: (context, state) => const NotFoundScreen(),
  );
});
```

**`SplashScreen`**: full-screen `tokens.bgTrue` background; centered `VeriqooLoading(message: 'VERIQOO')`
(which internally runs the `VerificationScan` motif). In `initState`, start a cancelable
`Timer(const Duration(milliseconds: 1200), () => ref.read(authControllerProvider.notifier).resolve())`
and **cancel it in `dispose`** (so navigating away does not leave a pending timer). No artificial delay
beyond the ~1.2s minimum; if `onAuthStateChange` settles sooner the redirect still waits for the timer
only because state stays `unknown` until `resolve()`/the stream fires — whichever is first wins and the
redirect moves off `/splash`. Must be a `ConsumerStatefulWidget`.

Flow: boot → `/splash` (state `unknown`, redirect keeps us here) → session restored →
state → `authenticated` ⇒ `/home`, or `unauthenticated` ⇒ `/auth/login`. No login flash because we never
render an auth screen while `unknown`.

---

## Riverpod provider list & signatures

| Provider | File | Signature | Purpose |
|----------|------|-----------|---------|
| `themeModeProvider` | core/providers/theme_mode_provider.dart | `StateProvider<ThemeMode>((ref) => ThemeMode.dark)` | app theme mode (default dark) |
| `networkStatusProvider` | core/providers/network_provider.dart | `StateProvider<NetworkStatus>((ref)=>NetworkStatus.unknown)` + `enum NetworkStatus{unknown,online,offline}` | skeleton |
| `offlineSyncProvider` | core/providers/offline_sync_provider.dart | `StateProvider<OfflineSyncStatus>((ref)=>OfflineSyncStatus.idle)` + `enum OfflineSyncStatus{idle,syncing,error}` | skeleton |
| `authControllerProvider` | features/auth/auth_controller.dart | `NotifierProvider<AuthController, AuthState>(AuthController.new)` | auth state / guard source |
| `devBypassProvider` | features/auth/auth_controller.dart | `StateProvider<bool>((ref)=>false)` | TEMP dev bypass |
| `goRouterProvider` | app/router.dart | `Provider<GoRouter>` | router + redirect |
| `scanStateProvider` | features/scan/scan_providers.dart | `NotifierProvider<ScanController, ScanState>(ScanController.new)` | skeleton (pipeline keeps local state for now) |
| `historyProvider` | features/history/history_providers.dart | `FutureProvider.autoDispose<List<InspectionSummary>>((ref) async => const [])` | skeleton (empty) |
| `profileProvider` | features/profile/profile_providers.dart | `Provider<UserProfile?>((ref)=>null)` | skeleton |
| `notificationsProvider` | features/notifications/notification_providers.dart | `StateProvider<List<AppNotification>>((ref)=>const [])` | skeleton |

Skeleton state types (typed-but-minimal, no business logic — logic stays in `shared_core`):
```dart
// scan_providers.dart
@immutable class ScanState {
  final List<XFile> images; final String ocrText; final bool isAnalyzing;
  const ScanState({this.images = const [], this.ocrText = '', this.isAnalyzing = false});
  ScanState copyWith({List<XFile>? images, String? ocrText, bool? isAnalyzing}) => ScanState(
    images: images ?? this.images, ocrText: ocrText ?? this.ocrText, isAnalyzing: isAnalyzing ?? this.isAnalyzing);
}
class ScanController extends Notifier<ScanState> {
  @override ScanState build() => const ScanState();
  void reset() => state = const ScanState();
}
// history_providers.dart
@immutable class InspectionSummary {
  final String id; final String product; final String timestamp; final int score;
  const InspectionSummary({required this.id, required this.product, required this.timestamp, required this.score});
}
// profile_providers.dart
@immutable class UserProfile { final String displayName; final String? email;
  const UserProfile({required this.displayName, this.email}); }
// notification_providers.dart
@immutable class AppNotification { final String id; final String title; final String body;
  const AppNotification({required this.id, required this.title, required this.body}); }
```

---

## Scan pipeline relocation (carry-forward — must stay functional & reachable from `/scan`)

Relocate the current `main.dart` logic verbatim into `features/scan/`:

- **`scan_screen.dart`** = the current `ScanScreen`/`_ScanScreenState` (image_picker capture →
  `TextRecognizer` OCR → combine text → `LegalRulesRetrievalService.retrieveLegalContext` →
  `GeminiAIAnalysisService.analyzeProductLabel`), with three adaptations:
  1. Construct `GeminiAIAnalysisService` and `LegalRulesRetrievalService` **inside `analyzeProduct()`**
     (not as fields) and `dispose()` them in a `finally`. Construct `TextRecognizer` on demand in
     `runOcrOnImage()` (or keep as a field — it does not touch Supabase; either is fine) and `close()` it.
  2. Resolve the Gemini key with the dotenv-first helper (decision #8), wrapped in try/catch.
  3. On success, navigate via `context.push('/scan/result', extra: AnalysisResultArgs(analysis: result,
     ocrText: combinedText, primaryImage: _capturedImages.first))` instead of `Navigator.push(MaterialPageRoute)`.
  Lightly restyle the chrome with the design system (wrap in `VeriqooAppBar(title: 'Scan')`, use token
  colors, a `VeriqooButton` for Capture/Analyze), but keep every functional path intact. Visual
  redesign is a later phase.
- **`analysis_result_screen.dart`** = the current `AnalysisResultScreen` (+ its helper widgets
  `_detailRow/_warningSection/_issueWarningSection/_verificationStatusBadge/_legalReferenceRow`), with
  `SupabaseService()` constructed **inside `_saveReport()`** and `await ...saveInspectionReport(...)`
  unchanged. Add `class AnalysisResultArgs { final ComplianceAnalysis analysis; final String ocrText;
  final XFile? primaryImage; final String? imageUrl; const AnalysisResultArgs({required this.analysis,
  required this.ocrText, this.primaryImage, this.imageUrl}); }`. Keep the Save button and its
  success/error SnackBars.
- **`/scan/result` route builder**: `final args = state.extra as AnalysisResultArgs?;` → if non-null
  render `AnalysisResultScreen(args: args)`, else render a `VeriqooEmptyState(icon: VeriqooIcons.scan,
  title: 'No analysis yet', message: 'Run a scan to see results here.')`.

Reachability is proven at Gate 5 by a widget test that boots authenticated, taps the Scan nav
destination, and finds the `ScanScreen` capture affordance mounted at `/scan` — plus `flutter analyze`
and `flutter build web` proving the whole OCR→analysis→save code path compiles.

---

## Per-screen design-system usage (placeholders must look intentional, not blank)

Common pattern: `Scaffold(appBar: VeriqooAppBar(title: ...), body: VeriqooBackdrop(background: <Painter>,
child: SafeArea(child: content)))`. `VeriqooBackdrop` (core/widgets/app_background.dart) =
`Stack([Positioned.fill(ColoredBox(tokens.bg)), if(background!=null) Positioned.fill(IgnorePointer(background)), child])`.

- **Splash** — `tokens.bgTrue` + centered `VeriqooLoading(message:'VERIQOO')` (VerificationScan motif). No app bar.
- **Login** (functional) — `VeriqooAppBar(title:'VERIQOO', showBack:false)`; `VeriqooTextField` email
  (`keyboardType: TextInputType.emailAddress`, `prefixIcon: VeriqooIcons.profile`) + password
  (`obscureText:true`); `VeriqooButton(label:'Sign in', variant: primary, loading:…, expand:true)` →
  `Supabase.instance.client.auth.signInWithPassword(email,password)` with try/catch surfacing
  `AuthException.message` as the field `errorText` or a SnackBar; `VeriqooButton(label:'Enter app (dev)',
  variant: secondary, expand:true)` → set `devBypassProvider=true` + `context.go('/home')`
  `// TODO(phase3): remove dev bypass`; ghost `VeriqooButton`s to `/auth/signup` and `/auth/forgot-password`.
  `ConsumerStatefulWidget` (controllers + loading state).
- **Signup / OTP / Forgot / Reset** — `VeriqooAppBar(title: …)` + `VeriqooSectionHeader` +
  `VeriqooEmptyState(icon: VeriqooIcons.alert, title:'Coming in Phase 3', message:'…')` +
  `VeriqooButton(label:'Back to login', variant: ghost)` → `context.go('/auth/login')`.
- **Home** — `VeriqooAppBar(title:'VERIQOO', showBack:false, action: VeriqooIconButton(icon: VeriqooIcons.search,…))`,
  `InspectionGrid` bg, `VeriqooSectionHeader(title:'Inspect', subtitle:'…')`, a primary
  `VeriqooButton(label:'Start inspection', icon: VeriqooIcons.scan)` → `context.go('/scan')`,
  `VeriqooSectionHeader(title:'Recent')` + `VeriqooEmptyState(icon: VeriqooIcons.history, title:'No inspections yet')`.
- **Scan** — carry-forward (see above); minimal/no bg so the camera preview reads cleanly.
- **Scan capture** — `VeriqooScannerOverlay()` full-bleed + `VeriqooAppBar(title:'Capture')`.
- **Scan processing** — `OCROverlay` bg + centered `VeriqooLoading(message:'Analyzing')`.
- **History** — `TechnicalCoordinates` bg, `VeriqooSectionHeader(title:'History')`;
  `ref.watch(historyProvider)` → when empty `VeriqooEmptyState(icon: VeriqooIcons.history,
  title:'No inspections yet')`, else a column of `VeriqooInspectionCard(onTap:()=>context.go('/history/$id'))`.
- **History detail** — `ProductOutline` bg, `VeriqooAppBar(title:'Inspection')`, `VeriqooScore(value: 0,
  caption:'SCORE')`, `VeriqooStatus(kind: VeriqooStatusKind.missing)`, `VeriqooSectionHeader`s; reads `:id`.
- **Product detail** — `ProductOutline` bg, `VeriqooAppBar(title:'Product')`, `VeriqooSectionHeader` +
  `VeriqooEmptyState`; reads `:id`.
- **Report detail** — `ComplianceMarkers` bg, `VeriqooScore`, `VeriqooStatus`, `VeriqooSectionHeader`; reads `:id`.
- **Report issue** — `DataTicker` bg, `VeriqooAppBar(title:'Report an issue')`, `VeriqooTextField`
  (subject + details) + `VeriqooButton(label:'Submit', expand:true)` (no-op placeholder + SnackBar).
- **Profile** — `VerificationPulse` bg, `VeriqooAppBar(title:'Profile', showBack:false)`, a header row,
  `VeriqooSectionHeader`, nav rows (`VeriqooButton` ghost / `ListTile`-style) to `/settings` and
  `/notifications` separated by `VeriqooDivider`.
- **Settings** (functional) — `TechnicalCoordinates` bg, `VeriqooAppBar(title:'Settings')`,
  `VeriqooSectionHeader(title:'Appearance')`, a 3-way theme switch (Dark / Light / System) writing
  `ref.read(themeModeProvider.notifier).state`, `VeriqooDivider`s between rows.
- **Notifications** — `DataTicker` bg, `VeriqooAppBar(title:'Notifications')`,
  `VeriqooEmptyState(icon: VeriqooIcons.alert, title:'No notifications')`.
- **NotFound (errorBuilder)** — `VeriqooErrorState(title:'Page not found', message: state.uri.toString(),
  onRetry: ()=>context.go('/home'), retryLabel:'Go home')`.

WCAG reminder for custom copy: body/supporting text uses `tokens.textPrimary`/`textSecondary`; reserve
`textTertiary` for meta/decorative/disabled only.

---

## Ordered, dependency-ordered implementation steps

Each step leaves the app buildable. All commands run with cwd = `apps/user_app`.

- [ ] 1. Add routing + state deps.
      Run `flutter pub add go_router flutter_riverpod` (let pub resolve versions; do not hand-pick).
      Files: `apps/user_app/pubspec.yaml`, `pubspec.lock`.
      Verify: `flutter pub get` → "Got dependencies!" with no resolution error; `go_router` and
      `flutter_riverpod` appear under `dependencies` in pubspec.yaml.

- [ ] 2. Create core providers + the auth controller.
      Create `themeModeProvider`, `networkStatusProvider`(+enum), `offlineSyncProvider`(+enum), and
      `auth_controller.dart` (`AuthState`, `AuthController`, `authControllerProvider`, `devBypassProvider`)
      exactly as specified above.
      Files: `lib/core/providers/theme_mode_provider.dart`, `network_provider.dart`,
      `offline_sync_provider.dart`, `lib/features/auth/auth_controller.dart`.
      Verify: `flutter analyze lib/core lib/features/auth/auth_controller.dart` → no errors.

- [ ] 3. Create shared UI plumbing: backdrop, transitions, route constants, 404.
      `VeriqooBackdrop`; `fadePage()` + `sharedAxisPage()` (using `VeriqooMotion`, honoring
      `reduceMotion`); `routes.dart` path/name constants; `NotFoundScreen` (place in router file or a
      small `lib/app/not_found_screen.dart` — your choice, keep it with the router).
      Files: `lib/core/widgets/app_background.dart`, `lib/app/transitions.dart`, `lib/app/routes.dart`,
      (+ `lib/app/not_found_screen.dart` if separate).
      Verify: `flutter analyze lib/core lib/app` → no errors.

- [ ] 4. Create the skeleton feature providers.
      `scan_providers.dart`, `history_providers.dart`, `profile_providers.dart`,
      `notification_providers.dart` with the typed-minimal state classes above.
      Files: the four `*_providers.dart` under `lib/features/{scan,history,profile,notifications}/`.
      Verify: `flutter analyze lib/features` → no errors (unused-provider is not an error).

- [ ] 5. Create all placeholder screens (one pattern repeated across many files).
      Splash; auth login (functional) + signup/otp/forgot/reset placeholders; home; scan capture;
      scan processing; history + history detail; product detail; report detail + report issue; profile;
      settings (functional theme switch); notifications. Each uses the DS components/painters mapped in
      "Per-screen design-system usage". Login + Settings are `ConsumerStatefulWidget`/`ConsumerWidget`.
      Files: `lib/features/splash/splash_screen.dart`; `lib/features/auth/{login,signup,otp,
      forgot_password,reset_password}_screen.dart`; `lib/features/home/home_screen.dart`;
      `lib/features/scan/{scan_capture_screen,scan_processing_screen}.dart`;
      `lib/features/history/{history_screen,history_detail_screen}.dart`;
      `lib/features/products/product_detail_screen.dart`;
      `lib/features/reports/{report_detail_screen,report_issue_screen}.dart`;
      `lib/features/profile/profile_screen.dart`; `lib/features/settings/settings_screen.dart`;
      `lib/features/notifications/notifications_screen.dart`.
      Verify: `flutter analyze lib/features` → no errors.

- [ ] 6. Carry forward the scan pipeline into `/scan`.
      Create `scan_screen.dart` (relocated `ScanScreen` with lazy services + dotenv-first Gemini key +
      `context.push('/scan/result', extra: …)`) and `analysis_result_screen.dart` (relocated
      `AnalysisResultScreen` + `AnalysisResultArgs` + lazy `SupabaseService` save). Keep all OCR /
      retrieval / analysis / save calls and their imports from `shared_core/services/*` intact.
      Files: `lib/features/scan/scan_screen.dart`, `lib/features/scan/analysis_result_screen.dart`.
      Verify: `flutter analyze lib/features/scan` → no errors (confirms the shared-service calls compile).

- [ ] 7. Build the shell + router.
      `AppShell` (Scaffold + `VeriqooNavigationBar` driving `StatefulNavigationShell.goBranch`) and
      `goRouterProvider` wiring the full route table (top-level routes, the four-branch
      `StatefulShellRoute.indexedStack` with nested `/scan/*` and `/history/:id`, the redirect guard,
      `refreshListenable`, `errorBuilder`), using `fadePage` for `/home` and `/scan` and `sharedAxisPage`
      for `/history/:id`, `/products/:id`, `/reports/:id`.
      Files: `lib/shell/app_shell.dart`, `lib/app/router.dart`.
      Verify: `flutter analyze lib/shell lib/app` → no errors.

- [ ] 8. Rewrite the root app + thin bootstrap `main.dart`.
      `app/app.dart` = `VeriqooApp` (`ConsumerWidget`) → `MaterialApp.router(theme: VeriqooTheme.light,
      darkTheme: VeriqooTheme.dark, themeMode: ref.watch(themeModeProvider), routerConfig:
      ref.watch(goRouterProvider), debugShowCheckedModeBanner:false, title:'VERIQOO')`. Rewrite
      `main.dart` to the thin bootstrap: `WidgetsFlutterBinding.ensureInitialized()` → `dotenv.load(".env")`
      → read Supabase URL/key (same keys/fallbacks as today) → `Supabase.initialize(url:, publishableKey:)`
      → `runApp(const ProviderScope(child: VeriqooApp()))`. Remove the old monolithic screens from
      `main.dart` (now relocated). Do **not** touch `gallery_main.dart`.
      Files: `lib/app/app.dart`, `lib/main.dart`.
      Verify: `flutter analyze` (whole app) → **No issues found!**; then `flutter build web` → build
      succeeds; then `flutter build web -t lib/gallery_main.dart` → build succeeds.

- [ ] 9. Replace the placeholder widget test with the Phase-2 shell tests (Gates 4 & 5).
      Delete `test/widget_test.dart`; create `test/app_shell_test.dart`. Use a `ProviderContainer` with
      `authControllerProvider.overrideWith(() => FakeAuthController(initial))` (a subclass whose `build()`
      returns the injected state and whose `resolve()` is a no-op — never touches Supabase) +
      `UncontrolledProviderScope(container: …, child: const VeriqooApp())`. After each test
      `await tester.pump(const Duration(seconds: 2))` to drain the splash timer; `addTearDown(container.dispose)`.
      Scenarios:
      (a) start `unknown` → pump → `expect(find.byType(SplashScreen), findsOneWidget)`; then
      `container.read(authControllerProvider.notifier).set(AuthState.unauthenticated)` → pumpAndSettle →
      `expect(find.byType(LoginScreen), findsOneWidget)`.
      (b) start `authenticated` → pumpAndSettle → `expect(find.byType(HomeScreen), findsOneWidget)`.
      (c) nav switching (authenticated): tap the History destination (`find.bySemanticsLabel('History')`)
      → `expect(find.byType(HistoryScreen), findsOneWidget)`; tap Scan → `expect(find.byType(ScanScreen),
      findsOneWidget)` (this also proves **Gate 5**: the carried `ScanScreen` mounts at `/scan`).
      Files: `test/app_shell_test.dart` (create), `test/widget_test.dart` (delete).
      Verify: `flutter test` → all tests pass (new shell tests + existing `gallery_test.dart` +
      `compliance_analysis_test.dart`).

- [ ] 10. Final 5-gate verification sweep (see next section). Fix any issue found and re-run until all
      five gates pass. Clean up any scratch files.
      Verify: all five commands below succeed.

---

## The 5 verification gates (exact commands — cwd `apps/user_app`)

1. **Dependencies resolve** — `flutter pub get` → ends with dependencies resolved, no error.
2. **Static analysis clean** — `flutter analyze` → `No issues found!` (0 errors; also target 0 new warnings).
3. **Web builds (both entrypoints)** —
   `flutter build web` (default target `lib/main.dart`) → "✓ Built build\web"; then
   `flutter build web -t lib/gallery_main.dart` → "✓ Built build\web". Both must succeed.
4. **Tests pass** — `flutter test` → all pass, including `test/app_shell_test.dart` proving: boot →
   `/splash`; no session → `/auth/login`; mocked authenticated → `/home`; nav bar switches branches.
5. **Scan pipeline intact & reachable** — confirmed by (a) Gate 2/3 compiling the full
   OCR→`retrieveLegalContext`→`analyzeProductLabel`→`AnalysisResultScreen`→`saveInspectionReport` path,
   and (b) the Gate-4 nav test mounting `ScanScreen` at `/scan`. The coder reports the traced code path:
   `/scan` → `ScanScreen` → `captureImage()`/`runOcrOnImage()` → `analyzeProduct()` (lazily builds
   `LegalRulesRetrievalService` + `GeminiAIAnalysisService`) → `context.push('/scan/result', extra:)` →
   `AnalysisResultScreen` → `_saveReport()` → `SupabaseService().saveInspectionReport(...)`.

Reviewer approves only when all five pass; record the result in
`.agents/tasks/veriqoo-user-app-shell-phase2/phase2-review.json` with `verdict` = `APPROVED`.

---

## Assumptions & gaps (reasonable choices made rather than stalling)

- **Package name** kept as `flutter_application_1` (test imports use that). Renaming is out of scope.
- `/settings`, `/notifications`, `/products/:id`, `/reports/:id`, `/report-issue` are **top-level over
  the shell** to preserve the exact absolute paths the task lists (go_router child paths are relative).
  If a later phase prefers them inside the Profile branch, that is a path-shape change to revisit then.
- Live OCR/camera/Gemini/Supabase calls cannot execute in a headless web build or `flutter test`;
  Gate 5 therefore verifies the pipeline **compiles and is reachable** (mounting `ScanScreen` at `/scan`)
  rather than executing a real inference — matching the task's "report how the code path was verified".
- `GEMINI_API_KEY` is resolved dotenv-first then dart-define (a superset of today's behavior) so the
  key already in `.env` is actually used; dart-define continues to work.
- Skeleton providers return empty/default state only — business logic stays in `shared_core` per the task.
```
