# VERIQOO Phase 8 — Profile, Settings, Language selector, Notifications (user_app)

Implementation plan for a coding agent. Follow items in order; each leaves the
repo analysis-clean (`dart analyze` → "No issues found!"). This plan was written
after reading the actual source — API facts below are verified, not guessed.

## Scope & acceptance bar (read first)

- Write scope: `apps/user_app/**`. ONE additive exception:
  `packages/shared_core/lib/design_system/foundations/veriqoo_icons.dart` (add
  glyphs only — no edits elsewhere in shared_core, and nothing under
  `packages/shared_core/lib/services/*`). Do NOT touch `apps/admin_web/**`.
- Toolchain is `dart` ONLY. Shell `flutter *` is denied — do not run
  `flutter build/test/run` and do not try to bypass it.
- Acceptance bar for THIS phase:
  - `dart pub get` succeeds in `apps/user_app`.
  - `dart analyze` → 0 errors in `apps/user_app` AND in `packages/shared_core`
    (shared_core only because the icon facade changes). Note `dart analyze`
    also analyzes `test/`, so the widget tests must be analysis-clean even
    though they are not executed here.
- DEFERRED (record, do not run — `flutter` is denied):
  - `flutter test` (from `apps/user_app`) — execute all widget tests.
  - `flutter test test/profile test/settings test/notifications` — targeted run.
  - `flutter build web --dart-define=SUPABASE_URL=... --dart-define=SUPABASE_KEY=... --dart-define=GEMINI_API_KEY=...`
- Verified baseline before any change: `dart pub get` = "Got dependencies!",
  `dart analyze` (user_app) = "No issues found!".

## Verified design-system facts (do not re-derive)

- Import surface: `import 'package:shared_core/design_system/design_system.dart';`
  (single barrel; re-exports theme, icons, components).
- Theme: `VeriqooTheme.dark` / `VeriqooTheme.light` (getters). Tokens:
  `Theme.of(context).extension<VeriqooTokens>()!` → `bg, bgTrue, surface,
  surfaceRaised, borderHairline, borderStrong, textPrimary, textSecondary,
  textTertiary, inverseBg, inverseText` (+ `brightness`). `textTertiary` is
  meta/decorative/disabled only (fails AA for body).
- Type ramp (ALL exist on `VeriqooType`): `display, h1, h2, h3, bodyL, body,
  caption, meta, mono`. Each leaves `color` null — set via tokens with
  `.copyWith(color: ...)`. `meta` must be UPPERCASED at the call site
  (`label.toUpperCase()`); `VeriqooSectionHeader` already uppercases its title
  internally. `mono` = tabular figures for numerals/IDs/counts.
- Components (verified signatures):
  - `VeriqooAppBar({required String title, Widget? action, VoidCallback? onBack,
    bool showBack = true, double height = 56})` — ONE `action`; pass a `Row` for
    multiple. Back arrow auto-hides when `Navigator.canPop` is false.
  - `VeriqooIconButton({required IconData icon, required String semanticLabel,
    VoidCallback? onPressed, ...})`.
  - `VeriqooButton({required String label, VoidCallback? onPressed,
    VeriqooButtonVariant variant = primary, VeriqooButtonSize size = medium,
    IconData? icon, bool loading = false, bool expand = false,
    String? semanticLabel})`. Variants: `primary|secondary|ghost`.
  - `VeriqooSectionHeader({required String title, String? subtitle,
    Widget? action})` — renders `title.toUpperCase()` in `meta`.
  - `VeriqooDivider({double? height, double indent = 0, double endIndent = 0})`
    + `VeriqooDivider.vertical(...)` — a hairline using `borderHairline`.
  - `VeriqooStatus({required VeriqooStatusKind kind, double markerSize = 16,
    bool showLabel = true})`. `VeriqooStatusKind = {verified, flag, missing,
    violation}` with FIXED labels `VERIFIED | FLAG | NOT DETECTED | VIOLATION`
    (shape+glyph+label, never color).
  - `VeriqooEmptyState({required IconData icon, required String title,
    String? message, Widget? action})`.
  - `VeriqooBottomSheet.show<T>(BuildContext context, {required Widget child,
    String? title, bool isScrollControlled = false})`.
- `VeriqooBackdrop({required Widget child, Widget? background})` lives in
  `apps/user_app/lib/core/widgets/app_background.dart` (paints `tokens.bg` +
  optional painter). Background painters available: `VerificationPulse`,
  `DataTicker`, `InspectionGrid`, `TechnicalCoordinates`, etc.
- `VeriqooIcons` facade (existing glyphs you may reuse): `home, scan, history,
  profile (=LucideIcons.user), back, close, chevronRight, settings, search,
  check, alert, verified, violation, camera, upload, share, qrCode, flag, eye,
  zoomIn, shield, filter, sort, calendar, package`. NEVER import lucide in
  user_app — go through `VeriqooIcons`.
- Riverpod import rule (verified against the codebase): `StateProvider` comes
  from `package:flutter_riverpod/legacy.dart`; `Notifier/NotifierProvider/
  AsyncNotifier/AsyncNotifierProvider` and `Provider/FutureProvider` come from
  `package:flutter_riverpod/flutter_riverpod.dart`.

## Verified wiring / data facts

- `app.dart` builds `MaterialApp.router(theme: VeriqooTheme.light, darkTheme:
  VeriqooTheme.dark, themeMode: ref.watch(themeModeProvider), routerConfig:
  ref.watch(goRouterProvider))`. No `locale`/`supportedLocales` yet.
- Routes: `AppRoutes` in `app/routes.dart`; GoRoutes in `app/router.dart`.
  `/settings`, `/notifications`, `/biometric-setup` are top-level routes
  presented OVER the four-branch shell (so they show a back arrow). Profile is
  shell branch 3 (`showBack: false`).
- Identity: `currentUserProvider` (`Provider<HomeUser?>`) in
  `features/home/home_user.dart` reads `Supabase.instance...currentUser`
  GUARDED (null in hermetic tests); pure helper `displayNameFor(HomeUser?)`
  returns metadata name → email local-part → email → null. Reuse BOTH; do not
  re-read Supabase for name/email. It is overridden in tests via
  `currentUserProvider.overrideWithValue(...)`.
- Email-verified flag: gotrue `User.emailConfirmedAt` (String?, verified in
  gotrue 2.27.2) → verified when non-null.
- Sign-out today: `settings_screen._signOut()` calls
  `Supabase.instance.client.auth.signOut()` directly; `onAuthStateChange` flips
  the router guard → `/auth/login` (no manual nav). This must keep working but
  be made injectable (see item 7) so taps are testable without Supabase.
- Product derivation: `deriveProducts(List<InspectionRecord>)` in
  `features/inspections/product_summary.dart`; corpus via
  `allInspectionsProvider` (`FutureProvider.autoDispose`) in
  `features/inspections/inspections_providers.dart` (backed by the overridable
  `inspectionsRepositoryProvider`).
- Persistence precedent: `themeModeProvider` is a non-persisted
  `StateProvider<ThemeMode>` (default dark). `RecentSearchesStore` /
  `BiometricService` show the injectable-secure-storage pattern (provider +
  fake override). Both patterns are available.
- Notifications skeleton: `AppNotification {id, title, body}` +
  `notificationsProvider` (`StateProvider<List<AppNotification>>`, empty) in
  `features/notifications/notification_providers.dart`. Only the notifications
  screen (being rewritten) consumes them — safe to extend the model.
- Test harness convention (verified): `ProviderScope(overrides: [...], child:
  MaterialApp.router(theme: VeriqooTheme.dark, routerConfig: router))`; override
  providers with fakes; NEVER `pumpAndSettle` (background painters loop) — use
  `await tester.pump(); await tester.pump(const Duration(milliseconds: 50));`.
  Never touch `Supabase.instance` or platform channels. See
  `test/history/history_test.dart`, `test/home/home_harness.dart`,
  `test/auth/auth_harness.dart`.

## Design decisions (no formal design doc was supplied — rationale per decision)

1. Locale state = non-persisted `StateProvider<Locale>` (default `en`),
   mirroring `themeModeProvider` (the established app-wide-preference pattern,
   which is itself non-persisted). Persistence is a documented TODO (can later
   reuse the `RecentSearchesStore` secure-storage pattern). Rationale: matches
   codebase precedent, keeps `MaterialApp.locale` synchronous, and keeps
   hermetic tests free of async/storage.
2. Real locale resolution requires `flutter_localizations` (an `sdk: flutter`
   package). It is added to pubspec and `GlobalMaterialLocalizations.delegates`
   + `supportedLocales` are wired, so a non-English selection actually resolves
   instead of silently falling back to `en`. Verified: `dart pub get` resolves
   `sdk: flutter` deps here, and flutter_localizations ships material_* ARBs for
   all 10 target languages (en, hi, mr, bn, ta, te, gu, kn, ml, pa). TRANSLATION
   of VERIQOO's own strings is OUT OF SCOPE — a TODO notes UI copy stays English
   until a localization phase populates ARBs; `*_strings.dart` stay the single
   source of copy.
3. Language selector = a dedicated SCREEN with its own top-level route
   `/language` (not a bottom sheet). Rationale: the task asks to wire a new
   route, and a routed full screen is cleaner for a 10-row list.
4. Sign-out is extracted into an injectable `AuthActions` service +
   `authActionsProvider` (guarded, best-effort), consumed by Profile and
   Settings. Rationale: matches the injectable-service pattern (BiometricService
   / RecentSearchesStore), preserves current behavior, and makes sign-out taps
   testable without `Supabase.instance`.
5. Local settings toggles (notification prefs + privacy) live in ONE
   `settingsPreferencesProvider` (`Notifier<SettingsPreferences>`), local/
   skeleton only. Rationale: one small local store beats several tiny providers;
   `Notifier` gives clean `toggleX` methods (no legacy import needed).
6. Notification demo data is isolated in `demo_notifications.dart`
   (`kDemoNotifications`) behind `demoNotificationsEnabledProvider` (default
   FALSE). The live `notificationsProvider` stays empty, so the DEFAULT screen
   shows the empty state and the demo set is NEVER presented as live delivery —
   it only appears when the explicit, clearly-labelled demo toggle is on.
7. Profile verification chip maps `emailConfirmedAt != null` → `VeriqooStatus`
   `verified` (VERIFIED), else `flag` (FLAG) with a ProfileStrings caption.
   Rationale: uses the design-system chip as asked; `flag` reads as
   "needs attention" for an unconfirmed email.
8. New `VeriqooIcons` glyphs (verified Lucide 3.1.21 names):
   `notifications = LucideIcons.bell`, `language = LucideIcons.globe`,
   `privacy = LucideIcons.lock`, `help = LucideIcons.circleHelp`,
   `logout = LucideIcons.logOut`. "user" is NOT added — it already exists as
   `VeriqooIcons.profile` (`LucideIcons.user`). Additive only; no renames/
   removals.

---

# Implementation Plan

- [ ] 1. Add Phase-8 glyphs to the icon facade (ADDITIVE only).
      Add to `VeriqooIcons`: `notifications = LucideIcons.bell`,
      `language = LucideIcons.globe`, `privacy = LucideIcons.lock`,
      `help = LucideIcons.circleHelp`, `logout = LucideIcons.logOut`, under a
      `// Phase 8 — additive, no removals/renames.` comment. Do NOT add `user`
      (already exposed as `profile`). Do not touch any other shared_core file.
      Files: `packages/shared_core/lib/design_system/foundations/veriqoo_icons.dart`
      Verify: in `packages/shared_core`, `dart analyze` → "No issues found!".

- [ ] 2. Add the Flutter localizations SDK dependency.
      In `apps/user_app/pubspec.yaml` under `dependencies:` add:
      `flutter_localizations:` / newline / `    sdk: flutter`. Change nothing
      else.
      Files: `apps/user_app/pubspec.yaml`
      Verify: in `apps/user_app`, `dart pub get` → "Got dependencies!".

- [ ] 3. Create the locale provider + supported-language catalog.
      New file exporting: an immutable `AppLanguage {Locale locale; String
      englishName; String endonym}`; `const kSupportedLanguages =
      <AppLanguage>[...]` in the catalog order given below;
      and `localeProvider = StateProvider<Locale>((ref) =>
      kSupportedLanguages.first.locale)` (default `Locale('en')`). Language
      catalog (code → endonym): en → English, hi → हिन्दी, mr → मराठी,
      bn → বাংলা, ta → தமிழ், te → తెలుగు, gu → ગુજરાતી, kn → ಕನ್ನಡ,
      ml → മലയാളം, pa → ਪੰਜਾਬੀ. Import
      `package:flutter_riverpod/legacy.dart` for `StateProvider` and
      `package:flutter/widgets.dart` for `Locale`. Add a `// TODO(localization):
      persist selection (e.g. secure storage like RecentSearchesStore) and
      populate ARBs; UI copy stays English until then.` note.
      Files: `apps/user_app/lib/core/providers/locale_provider.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!".

- [ ] 4. Wire the selected locale into the root app.
      In `app.dart` add `import 'package:flutter_localizations/flutter_localizations.dart';`
      and `import '.../core/providers/locale_provider.dart';`; read
      `final locale = ref.watch(localeProvider);` and pass to
      `MaterialApp.router`: `locale: locale`,
      `supportedLocales: kSupportedLanguages.map((l) => l.locale)`,
      `localizationsDelegates: GlobalMaterialLocalizations.delegates`. Keep
      theme/themeMode/routerConfig unchanged.
      Files: `apps/user_app/lib/app/app.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!".

- [ ] 5. Create SettingsStrings and ProfileStrings (centralized copy).
      `SettingsStrings`: section titles (Appearance, Language, Notifications,
      Privacy, Security), theme labels (Dark/Light/System), the language row
      label + language-screen title + the localization TODO note shown on the
      language screen, notification-preference row labels, privacy row labels.
      `ProfileStrings`: identity fallback name, section headers (ACTIVITY /
      GENERAL / SUPPORT), nav row labels (My Products, Inspection history,
      Notifications, Settings, Help & Support), sign-out label, verified/
      unverified captions, and Help & Support sheet copy. Both are
      `abstract final class ...Strings` of flat `static const String` (match
      `auth_strings.dart`). Reuse `AuthStrings.securitySection`,
      `AuthStrings.biometricTitle`, `AuthStrings.signOutCta` where they already
      fit rather than duplicating.
      Files: `apps/user_app/lib/features/settings/settings_strings.dart`,
      `apps/user_app/lib/features/profile/profile_strings.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!".

- [ ] 6. Build the Language selector screen + route.
      Create `LanguageScreen` (ConsumerWidget): `Scaffold(backgroundColor:
      tokens.bg, appBar: VeriqooAppBar(title: SettingsStrings.languageTitle))`
      over a `VeriqooBackdrop`; a `ListView` of `kSupportedLanguages` rows (each
      = endonym as `bodyL` + `englishName` as `body`/`textSecondary` subtitle +
      trailing `VeriqooIcons.check` when `ref.watch(localeProvider) ==
      lang.locale`), hairline `VeriqooDivider` between rows; tapping sets
      `ref.read(localeProvider.notifier).state = lang.locale`. Add a footer note
      (`SettingsStrings.languageTodoNote`) in `caption`/`textTertiary` stating UI
      strings remain English until the localization phase. Then add route
      constants `languagePath = '/language'` + `languageName = 'language'` to
      `AppRoutes`, and a top-level `GoRoute` (over the shell, alongside
      `/settings`) in `router.dart` building `const LanguageScreen()` (add the
      import).
      Files: `apps/user_app/lib/features/settings/language_screen.dart`,
      `apps/user_app/lib/app/routes.dart`, `apps/user_app/lib/app/router.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!".

- [ ] 7. Add the injectable sign-out service.
      Create `AuthActions` with `Future<void> signOut()` that calls
      `Supabase.instance.client.auth.signOut()` wrapped in try/catch (best-effort,
      never throws — mirror `BiometricService`); expose
      `authActionsProvider = Provider<AuthActions>((ref) => AuthActions())`.
      Import `package:supabase_flutter/supabase_flutter.dart` (hide `AuthState`
      to match `auth_controller.dart`).
      Files: `apps/user_app/lib/features/auth/auth_actions.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!".

- [ ] 8. Rewrite profile providers for identity + verification.
      Replace the skeleton `UserProfile`/`profileProvider` with:
      `accountVerifiedProvider = Provider<bool>((ref) { try { return
      Supabase.instance.client.auth.currentUser?.emailConfirmedAt != null; }
      catch (_) { return false; } })` (guarded; overridable in tests); and
      `profileIdentityProvider = Provider<ProfileIdentity>((ref) {...})` where
      `ProfileIdentity {String? displayName; String? email; bool verified;
      String get initial}` is composed from `displayNameFor(ref.watch(
      currentUserProvider))`, `ref.watch(currentUserProvider)?.email`, and
      `ref.watch(accountVerifiedProvider)`. `initial` = first grapheme of
      displayName (else email, else 'V'), uppercased. Import `home_user.dart`
      for `currentUserProvider`/`displayNameFor`.
      Files: `apps/user_app/lib/features/profile/profile_providers.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!".

- [ ] 9. Rebuild the Profile screen (editorial sections + hairlines).
      `ProfileScreen` (ConsumerWidget) over `VeriqooBackdrop(background: const
      VerificationPulse())`, `VeriqooAppBar(title: 'Profile', showBack: false)`.
      Top identity block: a square avatar tile showing `identity.initial`
      (`h2`/`textPrimary` on `tokens.surface` with a `borderHairline` border),
      name (`h3`), email (`body`/`textSecondary`), and a verification chip —
      `VeriqooStatus(kind: identity.verified ? VeriqooStatusKind.verified :
      VeriqooStatusKind.flag)` plus a `ProfileStrings` caption. Then grouped nav
      rows under uppercase `VeriqooSectionHeader`s separated by `VeriqooDivider`:
      ACTIVITY → My Products (glyph `VeriqooIcons.package`; optional trailing
      derived count via `ref.watch(allInspectionsProvider).whenOrNull(data:
      (r) => deriveProducts(r).length)` rendered in `mono`, omitted while
      loading/error; onTap → `context.go(AppRoutes.historyPath)`) and Inspection
      history (`history` → `/history`); GENERAL → Notifications (`notifications`
      → `/notifications`), Settings (`settings` → `/settings`); SUPPORT →
      Help & Support (`help` → opens `VeriqooBottomSheet.show` with
      `ProfileStrings` support copy) and Sign out (`logout` →
      `await ref.read(authActionsProvider).signOut()`). Build one private
      `_ProfileNavRow` widget (glyph + label + optional trailing + chevron) used
      for every row. All copy from `ProfileStrings`.
      Files: `apps/user_app/lib/features/profile/profile_screen.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!".

- [ ] 10. Add the local settings-preferences store.
      Create immutable `SettingsPreferences {bool notifyInspections; bool
      notifyReports; bool notifyAlerts; bool shareDiagnostics; bool
      personalizedTips}` with `copyWith`, sensible defaults (notifications on,
      privacy toggles off), and a `SettingsPreferencesController extends
      Notifier<SettingsPreferences>` exposing `toggleNotifyInspections()` etc.
      (each flips one field via `state = state.copyWith(...)`); expose
      `settingsPreferencesProvider = NotifierProvider<SettingsPreferencesController,
      SettingsPreferences>(SettingsPreferencesController.new)`. Local/skeleton
      only; add a `// TODO: persist + wire to delivery in a later phase.` note.
      Import `package:flutter_riverpod/flutter_riverpod.dart` (Notifier — not
      legacy).
      Files: `apps/user_app/lib/features/settings/settings_preferences.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!".

- [ ] 11. Expand the Settings screen into sections (keep theme + sign-out working).
      Rework `SettingsScreen` into these sections on hairline dividers, all copy
      from `SettingsStrings`/`AuthStrings`:
      - Appearance — keep the existing 3-way theme switch driving
        `themeModeProvider` (reuse the current `_ThemeOption` + check behavior).
      - Language — a nav row (glyph `VeriqooIcons.language`) showing the current
        language endonym (from `kSupportedLanguages` matched to
        `ref.watch(localeProvider)`) as trailing meta; onTap →
        `context.go(AppRoutes.languagePath)`.
      - Notifications — switch rows bound to `settingsPreferencesProvider`
        (`notifyInspections/notifyReports/notifyAlerts`) via a private
        `_SwitchRow` (label + a monochrome `Switch` themed with
        `tokens.textPrimary`/`borderStrong`, no accent hue).
      - Privacy — switch rows (`shareDiagnostics`, `personalizedTips`), glyph
        `VeriqooIcons.privacy`.
      - Security — keep the biometric nav row (→ `AppRoutes.biometricSetupPath`)
        and the Sign out row, but route sign-out through
        `ref.read(authActionsProvider).signOut()` (remove the direct
        `Supabase.instance` call; keep the guard-driven redirect behavior).
      Files: `apps/user_app/lib/features/settings/settings_screen.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!".

- [ ] 12. Extend the notification model with categories.
      In `notification_providers.dart` add `enum NotificationCategory {system,
      inspections, reports, alerts}` and extend `AppNotification` with a
      `required this.category` field (plus optional `DateTime? receivedAt`).
      Keep `notificationsProvider` the LIVE source (stays empty). Only the demo
      set and the screen construct `AppNotification`, so this is safe.
      Files: `apps/user_app/lib/features/notifications/notification_providers.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!".

- [ ] 13. Add NotificationStrings + the ISOLATED demo source.
      `NotificationStrings`: the four category headers (SYSTEM / INSPECTIONS /
      REPORTS / ALERTS), empty-state title (`'NO NOTIFICATIONS'`) + message, the
      demo-toggle label (e.g. `'Show demo notifications'`), and the demo item
      titles/bodies (realistic, e.g. "Inspection completed — Your product
      analysis is ready.", "Report updated — An authority responded to your
      report."). Then `demo_notifications.dart`: a file-level doc comment stating
      this is NON-LIVE demo data; `const kDemoNotifications = <AppNotification>[
      ...]` spanning all four categories (copy from `NotificationStrings`); and
      `demoNotificationsEnabledProvider = StateProvider<bool>((ref) => false)`
      (import `legacy.dart`). Optionally a `visibleNotificationsProvider =
      Provider<List<AppNotification>>((ref) => ref.watch(
      demoNotificationsEnabledProvider) ? kDemoNotifications :
      ref.watch(notificationsProvider))`.
      Files: `apps/user_app/lib/features/notifications/notification_strings.dart`,
      `apps/user_app/lib/features/notifications/demo_notifications.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!".

- [ ] 14. Rebuild the Notifications center (category groups + demo toggle).
      `NotificationsScreen` (ConsumerWidget) over `VeriqooBackdrop(background:
      const DataTicker())`, `VeriqooAppBar(title: 'Notifications')` whose
      `action` is a `VeriqooIconButton` (icon `VeriqooIcons.eye`, semanticLabel
      from `NotificationStrings`) toggling `demoNotificationsEnabledProvider`
      (clearly a demo affordance, NOT live). Read the visible list; when empty →
      `VeriqooEmptyState(icon: VeriqooIcons.notifications, title:
      NotificationStrings.emptyTitle, message: ...)`; otherwise group by
      `NotificationCategory` and render, per non-empty category, a
      `VeriqooSectionHeader` (SYSTEM/INSPECTIONS/REPORTS/ALERTS) followed by rows
      (title `bodyL`, body `body`/`textSecondary`) on `VeriqooDivider`s. All
      copy from `NotificationStrings`.
      Files: `apps/user_app/lib/features/notifications/notifications_screen.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!".

- [ ] 15. Add Profile widget tests (hermetic).
      Pump `ProfileScreen` under `ProviderScope` + `MaterialApp.router` with a
      GoRouter exposing `/profile` and `Placeholder`-keyed `/history`,
      `/notifications`, `/settings` targets. Overrides:
      `currentUserProvider.overrideWithValue(const HomeUser(name: 'Ada Lovelace',
      email: 'ada@example.com'))`, `accountVerifiedProvider.overrideWithValue(
      true)`, a `FakeAuthActions` (records `signOut` calls) via
      `authActionsProvider.overrideWithValue(...)`, and
      `inspectionsRepositoryProvider.overrideWithValue(FakeInspectionsRepository())`
      (reuse the fake from `test/home/home_harness.dart`). Assert: name/email
      render; the VERIFIED `VeriqooStatus` chip shows; each nav row label
      (`ProfileStrings`) is present; tapping the Sign out row calls the fake;
      `tester.takeException()` is null. Use `pump()` + `pump(50ms)` (no settle).
      Files: `apps/user_app/test/profile/profile_screen_test.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!" (test
      execution is DEFERRED to `flutter test`).

- [ ] 16. Add Settings widget tests (hermetic).
      Pump `SettingsScreen` under `ProviderScope` + GoRouter with `/settings`,
      a `Placeholder`-keyed `/language`, and `/biometric-setup`. Override
      `authActionsProvider` with the `FakeAuthActions`. Assert: all five section
      headers render; tapping "Light" moves the selected check (themeModeProvider
      updated); the Language row shows the current endonym and tapping it
      navigates to the `/language` placeholder; toggling a notification/privacy
      `_SwitchRow` flips the switch (`settingsPreferencesProvider`); tapping Sign
      out calls the fake. No `Supabase.instance`, no settle.
      Files: `apps/user_app/test/settings/settings_screen_test.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!" (execution
      DEFERRED).

- [ ] 17. Add Language selector widget tests (hermetic).
      Pump `LanguageScreen` under `ProviderScope` + a minimal `MaterialApp`
      (dark theme). Assert: all 10 endonyms from `kSupportedLanguages` render;
      English is initially marked (its row shows `VeriqooIcons.check`); after
      tapping 'हिन्दी' and pumping, the Hindi row is marked and English is not
      (verifies `localeProvider` update end-to-end). No settle.
      Files: `apps/user_app/test/settings/language_screen_test.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!" (execution
      DEFERRED).

- [ ] 18. Add Notifications widget tests (hermetic, demo isolation).
      Pump `NotificationsScreen` under `ProviderScope` + `MaterialApp.router`
      (dark theme). Test A (defaults: live empty, demo off): the
      `VeriqooEmptyState` with `NotificationStrings.emptyTitle` shows and no
      category headers appear. Test B: override
      `demoNotificationsEnabledProvider` to `true` → the four category headers
      (or those present in `kDemoNotifications`) and representative demo titles
      render. Confirms the mock set is visible ONLY behind the demo toggle. No
      settle.
      Files: `apps/user_app/test/notifications/notifications_screen_test.dart`
      Verify: in `apps/user_app`, `dart analyze` → "No issues found!" (execution
      DEFERRED).

- [ ] 19. Full acceptance pass + record deferred commands.
      Run the whole bar: in `apps/user_app` → `dart pub get` ("Got
      dependencies!") then `dart analyze` ("No issues found!"); in
      `packages/shared_core` → `dart analyze` ("No issues found!"). Fix any
      error before finishing. Then record (do NOT run) the DEFERRED commands in
      the review/notes output: `flutter test` (from `apps/user_app`),
      `flutter test test/profile test/settings test/notifications`, and
      `flutter build web --dart-define=SUPABASE_URL=... --dart-define=SUPABASE_KEY=... --dart-define=GEMINI_API_KEY=...`.
      Files: (none — verification only)
      Verify: both `dart analyze` runs report 0 errors and `dart pub get`
      succeeds; deferred `flutter` commands are recorded.

## Notes / assumptions

- No dedicated product-LIST route exists (only `/products/:id`), so Profile's
  "My Products" and "Inspection history" both navigate to `/history`; this is
  explicitly sanctioned by the task ("…or link to history"). "My Products" adds
  only a derived count adornment via `deriveProducts`.
- The monochrome `Switch` for toggle rows uses token colors
  (`textPrimary`/`borderStrong`), no accent hue, to respect the monochrome rule
  (there is no `VeriqooSwitch` component).
- Reduced-motion: reuse existing backdrop painters (`VerificationPulse`,
  `DataTicker`) which already honor the system reduced-motion setting; add no
  new animations.
- Stop-gate for the implement-then-review loop is unchanged:
  `.agents/tasks/veriqoo-user-profile-phase8/phase8-impl-review.json` with
  jsonPath `verdict` == `APPROVED`, written last by the reviewer.
