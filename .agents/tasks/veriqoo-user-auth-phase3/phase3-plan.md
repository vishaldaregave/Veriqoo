# VERIQOO — Phase 3 Implementation Plan: Six-Screen Authentication Experience

Target app: `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app` (Dart package name `flutter_application_1`).
Design system consumed READ-ONLY from `packages/shared_core` via `package:shared_core/design_system/design_system.dart`.

This plan builds the full six-screen auth family (Login, Signup, OTP, Forgot password, Reset password, Biometric setup) on a shared cinematic `AuthScaffold`, removes the Phase 2 dev bypass, and keeps the GoRouter guard correct — on top of the already-approved Phase 2 shell.

---

## Hard constraints (apply to every item)

- Work DIRECTLY in the main workspace. NO git worktree, NO commits.
- WRITE SCOPE (STRICT): modify ONLY files under `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app` (`lib`, `pubspec.yaml`, `android`, `ios`, `test`).
  - Do NOT modify `packages/shared_core/**` or `apps/admin_web/**` (a parallel track owns admin_web).
  - Consume the design system READ-ONLY. Do NOT modify `packages/shared_core/lib/services/*`.
- Icons: use the `VeriqooIcons` facade ONLY. NEVER import `lucide_icons_flutter` in user_app. The facade exposes exactly 15 glyphs (see pinned list below).
- Fonts are bundled by shared_core. Do NOT add `google_fonts`. Mono = `kMonoFamily` via `VeriqooType.mono`.
- Theme entry points are GETTERS: `VeriqooTheme.dark` / `VeriqooTheme.light`. Tokens via `Theme.of(context).extension<VeriqooTokens>()!`.
- Do NOT ship a fake video or add any placeholder video asset. The shipping auth background is design-system motion; the video path is a documented seam only.

## Verification bar (dart-only; `flutter *` is DENIED for all actors)

- Primary acceptance (run from `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app`):
  - `dart pub get` → succeeds ("Got dependencies!").
  - `dart analyze` → 0 errors ("No issues found!" is the goal; the hard bar is 0 errors).
- `dart analyze` analyzes `lib/**` and `test/**` but EXCLUDES `android/**`, `ios/**`, `web/**` (see `analysis_options.yaml`). So native-config edits do not affect analyze, and test files MUST compile cleanly.
- DEFERRED (blocked by the `flutter` deny, not failed) — the plan still requires widget tests be written and kept. Record and run later, cwd `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app`:
  - `flutter test`
  - `flutter build web --dart-define=SUPABASE_URL=<url> --dart-define=SUPABASE_ANON_KEY=<anon-key>`

## Dependencies (already resolved by the setup-deps step — do NOT re-add)

`pubspec.yaml` already contains, and `pubspec.lock` resolves:
- `supabase_flutter` 2.17.2 (gotrue 2.27.2), `local_auth` 3.0.2, `flutter_secure_storage` 11.2.0, `go_router` 18.0.2, `flutter_riverpod` 3.4.3, `flutter_dotenv` 6.0.1.
- Therefore `pubspec.yaml` likely needs NO change. Only touch it if an import fails to resolve.

## Pinned facts from the real code (do not re-derive)

Design-system names (verified in `packages/shared_core/lib/design_system/`):
- Theme: `VeriqooTheme.dark`/`.light` (getters). Tokens: `VeriqooTokens` with `bg` (#0A0A0A), `bgTrue` (#000000), `surface`, `surfaceRaised`, `borderHairline`, `borderStrong`, `textPrimary`, `textSecondary`, `textTertiary`, `inverseBg`, `inverseText`, `brightness`.
- Spacing: `VeriqooSpacing.s4..s96`. Radius: `VeriqooRadius.{none,sm,md,lg}` + `*All` (`lgAll` = 20px, for hero/auth surfaces). Elevation: `VeriqooElevation.softShadow`, `VeriqooElevation.translucentSurface` (= deepBlack @ 60%).
- Motion: `VeriqooMotion.{fast=160ms, base=240ms, slow=320ms, cinematic=700ms}`, curves `enter`/`move`/`press`, and `VeriqooMotion.reduceMotion(context)` (returns bool).
- Typography: `VeriqooType.{display,h1,h2,h3,bodyL,body,caption,meta,mono}`; `kInterFamily`, `kMonoFamily`. `meta` is meant to be UPPERCASED at call site.
- Components (constructors verified): `VeriqooButton({required String label, VoidCallback? onPressed, VeriqooButtonVariant variant, VeriqooButtonSize size, IconData? icon, bool loading, bool expand, String? semanticLabel})` with `VeriqooButtonVariant.{primary,secondary,ghost}`; `VeriqooIconButton({required IconData icon, required String semanticLabel, VoidCallback? onPressed, VeriqooIconButtonVariant variant, double iconSize, double size})`; `VeriqooTextField({TextEditingController? controller, String? label, String? hintText, String? helperText, String? errorText, bool obscureText, TextInputType? keyboardType, TextInputAction? textInputAction, bool enabled, ValueChanged<String>? onChanged, ValueChanged<String>? onSubmitted, FocusNode? focusNode, IconData? prefixIcon, IconData? suffixIcon})`; `VeriqooAppBar({required String title, Widget? action, VoidCallback? onBack, bool showBack, double height})`; `VeriqooSectionHeader({required String title, String? subtitle, Widget? action})`; `VeriqooDivider()` / `VeriqooDivider.vertical()`; `VeriqooModal.show(context, {required String title, required Widget child, List<Widget> actions, bool showClose, bool barrierDismissible})`; `VeriqooLoading({String message, Size size})`; `VeriqooEmptyState({required IconData icon, required String title, required String message, Widget? action})`; `VeriqooErrorState(...)`.
- Background effects (all extend `BackgroundEffect` → monochrome, low-opacity, pausable, reduced-motion aware; `enabled:false` holds the static end state): `InspectionGrid({double cell = 32})`, `ScanningLine()`, `DataTicker()`. Signature motif: `VerificationScan({Widget? child, List<ScanField> fields, bool enabled, bool loop, Duration duration, Duration stagger, Color? color, double cornerLength, double sweepThickness})`.
- `VeriqooIcons` glyphs available (exactly 15): `home, scan, history, profile, back, close, chevronRight, settings, search, check, alert, verified, violation, camera, upload`. (There is NO fingerprint/lock/mail/eye glyph — use `verified`/`check`/`alert`/`profile` as the closest monochrome stand-ins, or text-only.)

Supabase auth API (verified in gotrue 2.27.2 / supabase_flutter 2.17.2; access via `Supabase.instance.client.auth`):
- `signInWithPassword({String? email, String? phone, String? password})` → `AuthResponse` (already used in Phase 2).
- `signUp({String? email, String? phone, required String password, String? emailRedirectTo, Map<String,dynamic>? data, ...})` → `AuthResponse` (fields `.session`, `.user`). Pass the display name via `data: {'display_name': name}`.
- `signInWithOAuth(OAuthProvider provider, {String? redirectTo, String? scopes, LaunchMode authScreenLaunchMode, Map<String,String>? queryParams})` → `Future<bool>`. Provider value: `OAuthProvider.google`.
- `verifyOTP({String? email, String? phone, String? token, required OtpType type, ...})` → `AuthResponse`. For a signup email code use `type: OtpType.signup`.
- `resend({String? email, String? phone, required OtpType type, String? emailRedirectTo, ...})` → `ResendResponse`. For email it asserts `type ∈ {OtpType.signup, OtpType.emailChange}`; use `OtpType.signup`.
- `resetPasswordForEmail(String email, {String? redirectTo, String? captchaToken})` → `Future<void>`.
- `updateUser(UserAttributes attributes, {String? emailRedirectTo})` → `UserResponse`. New password: `UserAttributes(password: newPassword)`.
- `signOut()` → `Future<void>`.
- Errors: catch `AuthException` (`.message`, `.statusCode`, `.code`); subtypes include `AuthApiException`, `AuthWeakPasswordException`. Recovery deep links emit `AuthChangeEvent.passwordRecovery` on `onAuthStateChange`.
- IMPORTANT: `import 'package:supabase_flutter/supabase_flutter.dart' hide AuthState;` in every auth file (our `AuthState` enum shadows Supabase's).

local_auth 3.0.2 (`LocalAuthentication`): `isDeviceSupported()` → `Future<bool>`; `getAvailableBiometrics()` → `Future<List<BiometricType>>` (`BiometricType.{face,fingerprint,iris,strong,weak}`); `authenticate({required String localizedReason, AuthenticationOptions options})` → `Future<bool>`; `AuthenticationOptions({bool useErrorDialogs=true, bool stickyAuth=false, bool sensitiveTransaction=true, bool biometricOnly=false})`. Platform calls can throw `PlatformException` — wrap in try/catch.

flutter_secure_storage 11.2.0 (`FlutterSecureStorage`): `const FlutterSecureStorage({...})`; `write({required String key, required String? value})`; `read({required String key})` → `Future<String?>`; `delete({required String key})`.

Existing test pattern to reuse (`test/app_shell_test.dart`): a `FakeAuthController extends AuthController` overriding `build()` (returns injected `AuthState`) and `resolve()` (no-op), injected via `authControllerProvider.overrideWith(() => FakeAuthController(initial))` inside an `UncontrolledProviderScope`. This keeps tests from ever touching `Supabase.instance`.

## Cross-cutting design rules (so widget tests can pump without a live Supabase)

- Screens must call `Supabase.instance.client.auth.*` ONLY inside user-triggered async handlers — never in `build()` / `initState()`. Tests pump the screen and type into fields WITHOUT tapping submit, then assert `tester.takeException()` isNull.
- Biometric + secure storage access goes through an injectable `biometricServiceProvider` (item 4) so tests override it with a fake and never hit platform channels.

---

# Implementation Plan

- [ ] 1. Create the centralized auth copy file.
      Add `abstract final class AuthStrings` with flat `static const String` members, grouped by screen with clear prefixes: `wordmark` ('VERIQOO'), `tagline`; `login*` (title, subtitle, emailLabel, passwordLabel, forgotCta, signInCta, googleCta, createAccountCta), `signup*` (title, nameLabel, confirmLabel, createCta, checkEmailTitle/Body), `otp*` (title = 'VERIFY YOUR IDENTITY', subtitle, resendCta, resendIn, changeEmailCta, verifyCta), `forgot*` (title, subtitle, sendCta, sentTitle/Body), `reset*` (title, subtitle, newPasswordLabel, confirmLabel, updateCta, successTitle/Body), `biometric*` (title, enableBody, enableCta, unavailableTitle/Body, unlockCta, skipCta), and `err*` (generic, emptyFields, passwordMismatch, weakPassword, oauthUnavailable, biometricFailed). Add a top-of-file doc comment: Phase 8 will localize; keep buttons/labels short and let `VeriqooButton`/`Text` ellipsize/wrap so longer languages do not break layout.
      Files: `apps/user_app/lib/features/auth/auth_strings.dart`
      Verify: `dart analyze` — 0 errors.

- [ ] 2. Create `AuthBackground` — the shipping cinematic motion backdrop plus the documented video-swap seam.
      Define `enum AuthBackgroundMode { motion, video }` and `class AuthBackground extends StatelessWidget { const AuthBackground({super.key, this.mode = AuthBackgroundMode.motion}); }`. In `build`, resolve `final reduce = VeriqooMotion.reduceMotion(context);` and a `tokens.bgTrue` base `ColoredBox`, then layer, each wrapped in `Positioned.fill(child: IgnorePointer(child: ...))`: `InspectionGrid(enabled: !reduce)`, `ScanningLine(enabled: !reduce)`, and a restrained `DataTicker(enabled: !reduce)` — this is the SHIPPING default (reduced motion → the effects hold their static end state because `enabled:false`). Add a private `_motionLayers(context, reduce)` builder. Add the seam: a `_videoLayers(context)` builder that currently delegates to `_motionLayers` and carries `// TODO(phase3+): swap in a muted, looping VideoPlayer with a static poster fallback. No video asset ships in Phase 3; fall back to motion until then.`; also add `static const bool kVideoBackdropAvailable = false;`. The `video` mode selects `_videoLayers` only when `kVideoBackdropAvailable`, else `_motionLayers`. Keep opacity low (the effects already paint at 0.03–0.12 alpha) — do not over-animate.
      Files: `apps/user_app/lib/features/auth/widgets/auth_background.dart`
      Verify: `dart analyze` — 0 errors.

- [ ] 3. Create `AuthScaffold` — the shared hero + translucent glass panel + entrance motion that all six screens use.
      `class AuthScaffold extends StatefulWidget` with `{required Widget child, String title = AuthStrings.wordmark, String? subtitle, bool showBack = false, VoidCallback? onBack, Widget? footer}`. Build a `Scaffold(backgroundColor: tokens.bgTrue, body: Stack([ const Positioned.fill(child: AuthBackground()), SafeArea(child: ...) ]))`. Foreground (centered, max-width ~440, scrollable `SingleChildScrollView` with `VeriqooSpacing.s24` padding): the VERIQOO wordmark (`VeriqooType.h1`/`display`, letter-spaced, `tokens.textPrimary`), optional `subtitle` (`VeriqooType.body`, `textSecondary`), then a restrained glass panel wrapping `child`: `ClipRRect(borderRadius: VeriqooRadius.lgAll, child: BackdropFilter(filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12), child: DecoratedBox(decoration: BoxDecoration(color: VeriqooElevation.translucentSurface, borderRadius: VeriqooRadius.lgAll, border: Border.all(color: tokens.borderHairline)), child: Padding(VeriqooSpacing.s24, child: child))))` — tasteful, not generic glassmorphism. If `showBack`, overlay a top-left `VeriqooIconButton(icon: VeriqooIcons.back, semanticLabel: 'Back', onPressed: onBack ?? () => Navigator.maybePop(context))`. Entrance motion: one `AnimationController(duration: VeriqooMotion.cinematic)` with `CurvedAnimation(curve: VeriqooMotion.enter)` driving a staggered fade+rise (wordmark then panel) via `FadeTransition`/`SlideTransition`; in `initState`/`didChangeDependencies`, if `VeriqooMotion.reduceMotion(context)` set the controller to `value = 1` (static end state) and do not animate, else `forward()`. The per-input focus line is already provided by `VeriqooTextField`.
      Files: `apps/user_app/lib/features/auth/widgets/auth_scaffold.dart` (add `import 'dart:ui';` for `ImageFilter`)
      Verify: `dart analyze` — 0 errors.

- [ ] 4. Create the injectable biometric/secure-storage service used by the biometric screen, the splash unlock, and (overridden) tests.
      `BiometricService` wrapping `LocalAuthentication` + `FlutterSecureStorage` with: `Future<bool> isAvailable()` (= `isDeviceSupported()` AND `getAvailableBiometrics()` non-empty), `Future<bool> authenticate(String reason)` (`authenticate(localizedReason: reason, options: const AuthenticationOptions(biometricOnly: true, stickyAuth: true))`, try/catch `PlatformException` → false), `Future<void> setEnabled(bool)` (`write`/`delete` key `veriqoo_biometric_enabled`), `Future<bool> isEnabled()` (`read` == 'true'). Expose `final biometricServiceProvider = Provider<BiometricService>((ref) => BiometricService());`. All methods wrap platform exceptions and never throw to the UI.
      Files: `apps/user_app/lib/features/auth/biometric_service.dart`
      Verify: `dart analyze` — 0 errors.

- [ ] 5. Remove the dev bypass, reconcile the guard, and ship the real Login on `AuthScaffold` (one atomic change — the provider and all its references must go together or the build breaks).
      In `auth_controller.dart`: delete `devBypassProvider` and its `// TODO(phase3): remove dev bypass` comment (keep the `AuthController`/`AuthState`/`authControllerProvider` intact). In `router.dart`: remove `ref.listen(devBypassProvider, ...)`, remove `final bypass = ref.read(devBypassProvider);`, and change the guard so `final loggedIn = auth == AuthState.authenticated;` (drop `|| bypass`). In `login_screen.dart`: full rewrite onto `AuthScaffold` (remove the "Enter app (dev)" button and `_enterAppDev`): email + password `VeriqooTextField`s; "Forgot password?" ghost link → `context.go(AppRoutes.forgotPasswordPath)`; primary SIGN IN `VeriqooButton` → `signInWithPassword` (keep existing error handling: `AuthException` → `errorText = error.message`, generic → `AuthStrings.errGeneric`); a "Continue with Google" `VeriqooButton` (secondary) → `signInWithOAuth(OAuthProvider.google)`, wrapped in try/catch(`AuthException`)/catch(_) that surfaces `AuthStrings.errOauthUnavailable` (button always shown; note web completes via current origin, mobile needs native deep-link config that is out of Phase 3 scope); a ghost "Create an account" link → `AppRoutes.signupPath`. On successful password sign-in the existing `onAuthStateChange` listener flips the guard to `authenticated` and the redirect moves to `/home` (no manual navigation).
      Files: `apps/user_app/lib/features/auth/auth_controller.dart`, `apps/user_app/lib/app/router.dart`, `apps/user_app/lib/features/auth/login_screen.dart`
      Verify: `dart analyze` — 0 errors (confirms no remaining references to `devBypassProvider`).

- [ ] 6. Implement the Signup screen on `AuthScaffold`.
      Fields: name, email, password, confirm-password (`VeriqooTextField`s, `showBack: true`). Per-field validation: name non-empty; email matches a simple regex; password length ≥ 8; confirm == password (`AuthStrings.errPasswordMismatch`/`errWeakPassword`). On submit call `signUp(email:, password:, data: {'display_name': name})`. On result: if `res.session != null` the guard advances to `/home`; else if `res.user != null` route to OTP verification via `context.go('${AppRoutes.otpPath}?email=${Uri.encodeComponent(email)}')` (email confirmation required). Provide a "check your email" inline state (`AuthStrings.signupCheckEmail*`) as the fallback when the project is configured for magic-link rather than code. Catch `AuthException` (incl. `AuthWeakPasswordException`) → inline error; generic → `AuthStrings.errGeneric`. Replace the current placeholder body entirely.
      Files: `apps/user_app/lib/features/auth/signup_screen.dart`
      Verify: `dart analyze` — 0 errors.

- [ ] 7. Build the segmented OTP input widget, then implement the OTP verification screen on `AuthScaffold`.
      Add `OtpInput` (`lib/features/auth/widgets/otp_input.dart`): a single `TextEditingController` of up to 6 chars rendered as six monospace cells (`VeriqooType.mono`), paste-aware and auto-advancing by construction (one backing field; `inputFormatters` restrict to digits + `maxLength: 6`; `onCompleted(String)` fires at length 6). Each cell is a bordered box using `tokens.borderHairline`/`borderStrong` with the active cell emphasized. Then rewrite `otp_screen.dart` (`ConsumerStatefulWidget`): read `email` from the GoRouter query (`state.uri.queryParameters['email']`) — pass it into the screen via the route builder (item 9 wiring); heading `AuthStrings.otpTitle` ('VERIFY YOUR IDENTITY'); `OtpInput`; a Resend action gated by a 60s countdown (`Timer.periodic`, show `AuthStrings.otpResendIn` with seconds, enable at 0) calling `resend(type: OtpType.signup, email: email)`; a "Change email" ghost action popping back to Signup/Login; verify via `verifyOTP(email: email, token: code, type: OtpType.signup)`. On success the session arrives and the guard advances to `/home`. Catch `AuthException` → inline error; generic → `AuthStrings.errGeneric`. Dispose the controller + timer.
      Files: `apps/user_app/lib/features/auth/widgets/otp_input.dart`, `apps/user_app/lib/features/auth/otp_screen.dart`
      Verify: `dart analyze` — 0 errors.

- [ ] 8. Implement the Forgot-password and Reset-password screens on `AuthScaffold`.
      Forgot (`forgot_password_screen.dart`, `showBack: true`): email `VeriqooTextField`; submit → `resetPasswordForEmail(email, redirectTo: <reset deep link constant>)`; show a clear confirmation state (`AuthStrings.forgotSent*`) regardless of whether the address exists (no account enumeration). Reset (`reset_password_screen.dart`, reachable at `/auth/reset`): new-password + confirm `VeriqooTextField`s with the same validation as signup; submit → `updateUser(UserAttributes(password: newPassword))`; on success show `AuthStrings.resetSuccess*` and `context.go(AppRoutes.homePath)` if a session exists else `AppRoutes.loginPath`. Add a doc comment noting deep-link wiring is minimal: a real recovery email emits `AuthChangeEvent.passwordRecovery` and establishes a session (which the current guard would route to `/home`); full recovery-link → `/auth/reset` routing is a deferred seam (`// TODO(phase3+): on AuthChangeEvent.passwordRecovery, route to /auth/reset`). Both replace their placeholder bodies; catch `AuthException`/generic as above.
      Files: `apps/user_app/lib/features/auth/forgot_password_screen.dart`, `apps/user_app/lib/features/auth/reset_password_screen.dart`
      Verify: `dart analyze` — 0 errors.

- [ ] 9. Implement the Biometric setup screen and wire its route + the OTP email param.
      New screen `biometric_setup_screen.dart` (`ConsumerStatefulWidget`, on `AuthScaffold`, `showBack: true`): on init read `ref.read(biometricServiceProvider).isAvailable()`; if unavailable show a graceful `AuthStrings.biometricUnavailable*` state; else show `AuthStrings.biometricEnableBody` + an "Enable" `VeriqooButton` that calls `authenticate(...)` then `setEnabled(true)` on success and pops/confirms, plus a "Skip" ghost action. Reach it POST-login (a session is required to tie opt-in to the account), so route it OUTSIDE the `/auth` group — the guard bounces authenticated users off any `/auth/*` path to `/home`. In `routes.dart` add `biometricSetupPath = '/biometric-setup'` + `biometricSetupName`. In `router.dart` add a top-level `GoRoute` for it (sibling of `/settings`), and update the OTP `GoRoute` builder to pass the `email` query param into `OtpScreen` (`OtpScreen(email: state.uri.queryParameters['email'])`; make `OtpScreen` accept an optional `String? email`).
      Files: `apps/user_app/lib/features/auth/biometric_setup_screen.dart`, `apps/user_app/lib/app/routes.dart`, `apps/user_app/lib/app/router.dart`
      Verify: `dart analyze` — 0 errors.

- [ ] 10. Add the Settings entry points for biometric setup and sign-out (makes the guard's signout→/auth/login behavior real).
      In `settings_screen.dart` add a "Security" `VeriqooSectionHeader` with a row → `context.go(AppRoutes.biometricSetupPath)` and a "Sign out" row calling `Supabase.instance.client.auth.signOut()` (import `supabase_flutter` with `hide AuthState`). After sign-out, `onAuthStateChange` flips the guard to `unauthenticated` and the redirect returns to `/auth/login` (no manual navigation needed). Keep the existing theme controls untouched. Use only `VeriqooIcons` glyphs (`settings`, `verified`, `profile`, etc.).
      Files: `apps/user_app/lib/features/settings/settings_screen.dart`
      Verify: `dart analyze` — 0 errors.

- [ ] 11. Add the optional, non-blocking biometric unlock to the splash.
      In `splash_screen.dart`, before/around the existing 1.2s `resolve()`: read `ref.read(biometricServiceProvider)`; if `await isEnabled()` is true AND a restored session exists (checked via the overridable `AuthController` path, NOT `Supabase.instance` directly — e.g. gate on `ref.read(authControllerProvider) == AuthState.authenticated` after resolve), present a biometric unlock affordance (`AuthStrings.biometricUnlockCta`) and call `authenticate(...)`; on success or on "skip" proceed exactly as today. Keep it OPTIONAL and NON-BLOCKING: when biometric is not enabled or unavailable, behavior is identical to Phase 2. Add a `// TODO(phase3+)` note that a stricter re-auth gate can build on this seam.
      Files: `apps/user_app/lib/features/splash/splash_screen.dart`
      Verify: `dart analyze` — 0 errors.

- [ ] 12. Apply the native biometric configuration (deferred from build verification, but required for the feature to run).
      Android manifest: add `<uses-permission android:name="android.permission.USE_BIOMETRIC"/>` above `<application>`. MainActivity: change `class MainActivity : FlutterActivity()` → `FlutterFragmentActivity()` and the import to `io.flutter.embedding.android.FlutterFragmentActivity` (local_auth requires a FragmentActivity host). iOS: add `<key>NSFaceIDUsageDescription</key><string>Use Face ID to unlock VERIQOO.</string>` to `Info.plist`.
      Files: `apps/user_app/android/app/src/main/AndroidManifest.xml`, `apps/user_app/android/app/src/main/kotlin/com/example/flutter_application_1/MainActivity.kt`, `apps/user_app/ios/Runner/Info.plist`
      Verify: `dart analyze` — 0 errors (these paths are analyzer-excluded, so analyze is unaffected; the `flutter build` that would exercise them is DEFERRED — see the deferred commands above).

- [ ] 13. Write the widget-test matrix (authored and kept; executed later via the deferred `flutter test`).
      One pump test per screen under `test/auth/`: `login_screen_test.dart`, `signup_screen_test.dart`, `otp_screen_test.dart`, `forgot_password_screen_test.dart`, `reset_password_screen_test.dart`, `biometric_setup_screen_test.dart` — each wraps the screen in `ProviderScope(overrides: [biometricServiceProvider.overrideWithValue(FakeBiometricService(...))])` + `MaterialApp(theme: VeriqooTheme.dark, home: <screen>)`, pumps, does a basic field interaction (enter text; for OTP enter 6 digits), and asserts `tester.takeException()` isNull (do NOT tap submit, so `Supabase.instance` is never touched). Add `test/auth/auth_guard_test.dart` reusing the `FakeAuthController` + `UncontrolledProviderScope` pattern from `app_shell_test.dart`: assert unauthenticated boot → `LoginScreen`; authenticated boot → `HomeScreen`; and a transition `authController.set(AuthState.unauthenticated)` (the signout path) redirects back to `LoginScreen`. Add the dev-bypass-gone assertion (in the login test or the guard test): pump `LoginScreen` and assert `find.text('Enter app (dev)')` findsNothing while the real sign-in / Google / create-account controls are present (the `devBypassProvider` symbol removal is additionally enforced at compile time by item 5). If item 11's splash change reads `biometricServiceProvider`, add a disabled `FakeBiometricService` override to `test/app_shell_test.dart` so that existing shell test stays green.
      Files: `apps/user_app/test/auth/login_screen_test.dart`, `apps/user_app/test/auth/signup_screen_test.dart`, `apps/user_app/test/auth/otp_screen_test.dart`, `apps/user_app/test/auth/forgot_password_screen_test.dart`, `apps/user_app/test/auth/reset_password_screen_test.dart`, `apps/user_app/test/auth/biometric_setup_screen_test.dart`, `apps/user_app/test/auth/auth_guard_test.dart`, and (if needed) `apps/user_app/test/app_shell_test.dart`
      Verify: `dart analyze` — 0 errors (every test file compiles; execution is DEFERRED to `flutter test`).

- [ ] 14. Full acceptance pass and record the deferred commands.
      Run the acceptance bar from `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app`: `dart pub get` then `dart analyze`. Fix any residual issues until analyze reports 0 errors. Confirm no edits landed outside `apps/user_app`, no `lucide` import exists in user_app (`grep` for `lucide` in `apps/user_app/lib` → none), and no `devBypass` reference remains. Record in this file / the review notes that `flutter test` and `flutter build web --dart-define=SUPABASE_URL=<url> --dart-define=SUPABASE_ANON_KEY=<anon-key>` (cwd `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app`) are DEFERRED (blocked by the `flutter` deny), with the full widget-test matrix written and kept for when the deny lifts.
      Files: none (verification only)
      Verify: `dart pub get` succeeds AND `dart analyze` → 0 errors in `apps/user_app`.

---

## Assumptions and notes (gaps filled with reasonable choices)

- Biometric SETUP is placed at top-level `/biometric-setup` (not under `/auth`) because it is a post-login action and the guard redirects authenticated users off `/auth/*`. It still renders on `AuthScaffold` for one visual language across the six screens.
- OTP uses `OtpType.signup` for both verify and resend (internally consistent: `resend` asserts email requires `signup`/`emailChange`). If the project's Supabase email template is magic-link rather than 6-digit code, the Signup "check your email" state is the graceful fallback.
- Google OAuth: only graceful not-configured handling is in scope. Web completes against the current origin; mobile OAuth additionally needs native deep-link config, which is out of Phase 3 scope and surfaced as a clean message on failure.
- Reset-password deep-link routing is intentionally minimal (documented seam). The screen itself is fully functional and route-reachable at `/auth/reset`.
- `pubspec.yaml` is expected to need no change (deps already resolved). Touch it only if an import fails to resolve.
- Sign-out UI is added to Settings so the guard's "signout → /auth/login" requirement is tangible; the guard-regression test simulates it via `AuthController.set(unauthenticated)` to stay hermetic.
