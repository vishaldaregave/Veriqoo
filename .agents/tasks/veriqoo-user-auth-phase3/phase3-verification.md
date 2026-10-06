# VERIQOO — Phase 3 Verification Note

Six-screen authentication experience in `apps/user_app`, built on the approved
Phase 2 shell. **First iteration** (no `phase3-review.json` was present, so the
whole plan was implemented from scratch).

All work is confined to `apps/user_app`. `packages/shared_core/**` and
`apps/admin_web/**` were NOT modified. Per the hard constraints: no git
worktree, no commits, and only `dart` was used (`flutter *` is denied).

---

## Acceptance bar (dart-only) — RESULTS

Run from `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app`:

| Command | Result |
| --- | --- |
| `dart pub get` | ✅ `Got dependencies!` (no pubspec changes needed; deps already resolved) |
| `dart analyze` | ✅ `No issues found!` (0 errors, 0 warnings, 0 lints) |

`dart analyze` covers `lib/**` and `test/**` (it excludes `android/**`,
`ios/**`, `web/**` per `analysis_options.yaml`), so every screen AND every
widget-test file compiles cleanly. The Supabase auth calls (`signInWithPassword`,
`signInWithOAuth`, `signUp`, `verifyOTP`, `resend`, `resetPasswordForEmail`,
`updateUser`, `signOut`) therefore compile statically, and the removal of the
Phase 2 dev bypass is enforced at compile time (no remaining `devBypassProvider`
symbol) and asserted by tests.

## Deferred (blocked by the `flutter` deny — NOT failures)

The full widget-test matrix is authored and kept under `test/auth/`. Execution
and the web build are deferred to when the deny lifts. Exact commands a
human/CI should run (cwd `c:\WorkSpace\Ajinkya\Veriqoo\apps\user_app`):

```
flutter test
flutter build web --dart-define=SUPABASE_URL=<url> --dart-define=SUPABASE_ANON_KEY=<anon-key>
```

Note: `dart test` is not a substitute here — these are `flutter_test` widget
tests requiring the Flutter test binding. They were verified to COMPILE via
`dart analyze`; they were not executed.

---

## Files created (all under `apps/user_app/`)

Auth copy / helpers:
- `lib/features/auth/auth_strings.dart` — centralized, Phase-8-localizable copy.
- `lib/features/auth/auth_validators.dart` — client-side email/password checks.
- `lib/features/auth/auth_config.dart` — password-reset deep-link seam constant.
- `lib/features/auth/biometric_service.dart` — injectable `BiometricService` +
  `biometricServiceProvider` wrapping `local_auth` + `flutter_secure_storage`.

Shared auth widgets:
- `lib/features/auth/widgets/auth_background.dart` — `AuthBackground` cinematic
  motion backdrop + documented video-swap seam (`kVideoBackdropAvailable=false`).
- `lib/features/auth/widgets/auth_scaffold.dart` — shared hero + translucent
  glass panel (radius `lg`) + staggered entrance motion (reduced-motion aware).
- `lib/features/auth/widgets/auth_message.dart` — shared inline error/notice
  line (textPrimary, WCAG-safe).
- `lib/features/auth/widgets/otp_input.dart` — 6-cell monospace OTP input
  (single backing field → paste-aware + auto-advance).

Screen:
- `lib/features/auth/biometric_setup_screen.dart` — opt-in / unavailable /
  enabled states on `AuthScaffold`.

Tests:
- `test/auth/auth_harness.dart` — `FakeBiometricService` + `wrapScreen` helper.
- `test/auth/login_screen_test.dart`
- `test/auth/signup_screen_test.dart`
- `test/auth/otp_screen_test.dart`
- `test/auth/forgot_password_screen_test.dart`
- `test/auth/reset_password_screen_test.dart`
- `test/auth/biometric_setup_screen_test.dart`
- `test/auth/auth_guard_test.dart`

## Files changed (all under `apps/user_app/`)

- `lib/features/auth/auth_controller.dart` — removed `devBypassProvider` and its
  TODO; dropped the now-unused `flutter_riverpod/legacy.dart` import.
- `lib/app/router.dart` — removed all dev-bypass wiring (`ref.listen` + `read`,
  `loggedIn = authenticated` only); pass `?email=` into `OtpScreen`; added the
  top-level `/biometric-setup` route; imported `BiometricSetupScreen`.
- `lib/app/routes.dart` — added `biometricSetupPath` / `biometricSetupName`.
- `lib/features/auth/login_screen.dart` — full rewrite onto `AuthScaffold`:
  email+password sign-in, Google OAuth (graceful not-configured message),
  forgot-password + create-account links; **dev bypass removed**.
- `lib/features/auth/signup_screen.dart` — real signup (name/email/password/
  confirm, per-field validation) → OTP route or check-email fallback.
- `lib/features/auth/otp_screen.dart` — OTP verify + 60s resend countdown +
  change-email, on `AuthScaffold`; accepts `String? email`.
- `lib/features/auth/forgot_password_screen.dart` — `resetPasswordForEmail` with
  a neutral (no-enumeration) confirmation state.
- `lib/features/auth/reset_password_screen.dart` — `updateUser(password:)` with
  success state; reachable at `/auth/reset`.
- `lib/features/settings/settings_screen.dart` — added a Security section
  (biometric setup entry + sign-out) using only `VeriqooIcons` glyphs.
- `lib/features/splash/splash_screen.dart` — optional, non-blocking biometric
  unlock (identical to Phase 2 when biometric is off/unavailable).
- `test/app_shell_test.dart` — added a disabled `FakeBiometricService` override
  so the existing shell tests stay hermetic now that the splash reads it.

## Native config edits (analyzer-excluded; exercised only by the deferred build)

- `android/app/src/main/AndroidManifest.xml` — added
  `<uses-permission android:name="android.permission.USE_BIOMETRIC"/>`.
- `android/app/src/main/kotlin/com/example/flutter_application_1/MainActivity.kt`
  — `FlutterActivity` → `FlutterFragmentActivity` (+ import), required by
  `local_auth`.
- `ios/Runner/Info.plist` — added `NSFaceIDUsageDescription`.

---

## Dependencies

No `pubspec.yaml` change was required — the Phase 3 dependencies were already
present and resolved by the setup step. Resolved versions in use
(`pubspec.lock`):

| Package | Version |
| --- | --- |
| `supabase_flutter` | 2.17.2 |
| `gotrue` (transitive) | 2.27.2 |
| `local_auth` | 3.0.2 |
| `flutter_secure_storage` | 11.2.0 |
| `go_router` | 18.0.2 |
| `flutter_riverpod` | 3.4.3 |
| `flutter_dotenv` | 6.0.1 |

---

## Notable deviations from the plan's pinned facts (please review)

1. **`local_auth` 3.0.2 API differs from the plan's pinned signature.** The plan
   described `authenticate({required localizedReason, AuthenticationOptions
   options})` (the 2.x API). In the resolved 3.0.2:
   - `authenticate` takes options as **direct named parameters**
     (`biometricOnly`, `sensitiveTransaction`, `persistAcrossBackgrounding`),
     and `AuthenticationOptions` is **not exported** from
     `package:local_auth/local_auth.dart`.
   - `stickyAuth` no longer exists; its closest replacement
     `persistAcrossBackgrounding: true` is used.
   - `authenticate` throws **`LocalAuthException`** (not `PlatformException`).
   `BiometricService` therefore calls
   `authenticate(localizedReason:, biometricOnly: true,
   persistAcrossBackgrounding: true)` and uses a broad `catch (_)` in each
   method to honor the plan's "never throw to the UI" requirement across the
   2.x→3.x exception-type change. This is the only material API adaptation; all
   Supabase/gotrue and `flutter_secure_storage` signatures matched the plan.

2. **Password-reset deep link is intentionally minimal (documented seam).**
   `ForgotPasswordScreen` passes `redirectTo:
   AuthConfig.passwordResetRedirectUrl` (`io.veriqoo.app://auth/reset`, a
   placeholder). `ResetPasswordScreen` is fully functional and route-reachable
   at `/auth/reset`, but full recovery-link → `/auth/reset` routing
   (`AuthChangeEvent.passwordRecovery`) and the native deep-link registration
   are left as a `// TODO(phase3+)` seam. A real recovery session currently lets
   the guard route to `/home`; `updateUser` still works there.

3. **Google OAuth** ships the button and surfaces `AuthStrings.errOauthUnavailable`
   on failure (web completes against the current origin; mobile needs native
   deep-link config, out of Phase 3 scope).

4. **OTP uses `OtpType.signup`** for both verify and resend (internally
   consistent; `resend` requires `signup`/`emailChange` for email). If the
   Supabase email template is magic-link rather than a 6-digit code, the signup
   "check your email" state is the graceful fallback.

5. **Auth background ships design-system motion only.** No video asset is
   bundled; `AuthBackground` carries the video strategy behind
   `kVideoBackdropAvailable = false` with a `// TODO(phase3+)` seam. Reduced
   motion holds every effect at its static end state.

---

## Widget-test matrix (authored; executed later via `flutter test`)

Hermetic by construction: each screen test wraps the screen in a `ProviderScope`
(+ `MaterialApp(theme: VeriqooTheme.dark)`), pumps with `tester.pump(Duration)`
(never `pumpAndSettle`, since the cinematic background loops forever), does a
basic field interaction, and asserts `tester.takeException()` is null WITHOUT
tapping submit — so `Supabase.instance` is never contacted. The biometric screen
and splash resolve `biometricServiceProvider` to a `FakeBiometricService`.

- `login_screen_test.dart` — pump + enter email/password; asserts the dev bypass
  (`Enter app (dev)`) is GONE and the real sign-in / Google / create-account /
  forgot controls are present.
- `signup_screen_test.dart` — pump + fill all four fields.
- `otp_screen_test.dart` — pump + enter six digits (no auto-submit).
- `forgot_password_screen_test.dart` — pump + enter email.
- `reset_password_screen_test.dart` — pump + enter new/confirm password.
- `biometric_setup_screen_test.dart` — enable state (available) and graceful
  unavailable state, via `FakeBiometricService`.
- `auth_guard_test.dart` — unauthenticated boot → `LoginScreen`; authenticated
  boot → `HomeScreen`; sign-out transition (`set(unauthenticated)`) → back to
  `LoginScreen`; and the dev-bypass-gone assertion on the real router.

---

## Final scope confirmation

- `grep lucide` in `apps/user_app/lib` → none (icons go through `VeriqooIcons`).
- No `devBypass` reference remains in production code; the only matches are the
  test assertions that prove `Enter app (dev)` is gone.
- No files outside `apps/user_app` were created or modified.
- `google_fonts` was NOT added (fonts are bundled by shared_core).
