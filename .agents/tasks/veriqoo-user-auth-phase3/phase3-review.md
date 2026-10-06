# Phase 3 user_app: six-screen Supabase auth, dev bypass removed

Phase 3 replaces the Phase 2 shell's temporary dev bypass with a real six-screen Supabase authentication family (Login, Signup, OTP, Forgot password, Reset password, Biometric setup), all built on a shared cinematic `AuthScaffold`. The dev bypass is gone at the source level — the `devBypassProvider` symbol and its TODO no longer exist, the router guard keys solely on `AuthState.authenticated`, and a guard test asserts the old "Enter app (dev)" control is absent. Every screen is wired to the correct `supabase_flutter` call, copy is centralized in `AuthStrings`, the background ships design-system motion (no video asset) behind a documented video seam, and the whole change is confined to `apps/user_app`. The coder's dart-only evidence (`dart pub get` → got dependencies, `dart analyze` → no issues) is recorded; the `flutter test` / `flutter build web` gates are deferred under the `flutter` deny.

Watch for: the splash biometric unlock calls `authenticate` but does not gate access on the result, so it enforces nothing yet (confirmed, non-blocking seam); the password-reset email path can't reach `/auth/reset` because a recovery session is authenticated and the guard bounces authenticated users off `/auth/*` to `/home` (confirmed, non-blocking seam); `local_auth` resolved to 3.0.2 and its API differs from the plan's pinned 2.x signature, so the biometric code was adapted and is only compile-checked, not run (confirmed, non-blocking); and `flutter test` / `flutter build web` were not executed, so no runtime verification exists (confirmed, non-blocking per the task).

**Verdict**: APPROVED

## High-level view

The dev bypass removal is clean and self-enforcing: there is no `devBypassProvider` left for anything to reference, so the guard physically cannot short-circuit, and the guard test pins both the redirect behavior and the absence of the old control.

The six screens share one `AuthScaffold` and each calls exactly the Supabase method the plan assigns it — `signInWithPassword` and `signInWithOAuth(google)` on Login, `signUp` on Signup, `verifyOTP` + `resend` on OTP, `resetPasswordForEmail` on Forgot, `updateUser` on Reset, `signOut` from Settings. All auth calls sit inside user-triggered handlers, which is what lets the widget tests pump each screen without ever touching `Supabase.instance`.

The auth background ships monochrome design-system motion (`InspectionGrid`, `ScanningLine`, `DataTicker`) over true black, holds its static end state under reduced motion, and isolates the future video behind `kVideoBackdropAvailable = false` with a TODO seam — no placeholder asset ships.

Design-system discipline holds throughout: the read-only `design_system.dart` barrel, `VeriqooTheme.dark/.light` getters, tokens through `extension<VeriqooTokens>()`, the `VeriqooIcons` facade with no `lucide` import anywhere, no `google_fonts`, and `textTertiary` kept off body copy (the shared inline-message widget documents the WCAG reason it uses `textPrimary`).

Biometric support is real for the opt-in setup screen but intentionally non-enforcing on the splash: the unlock affordance runs but access is already granted regardless of the result. That, the password-reset deep-link routing, and mobile Google OAuth are documented `phase3+` seams, not finished behavior.

Write scope is confined to `apps/user_app`: `shared_core` (including `lib/services`) is untouched by mtime, and the only out-of-tree activity is `admin_web`, modified in a later window by the parallel admin track that the plan says owns it. No commits were made.

<details>
<summary>Issues (6)</summary>

All findings are non-blocking; the verdict is APPROVED. Items 1–3 are design seams the plan explicitly deferred, item 4 is the deferred verification gate, items 5–6 are minor observations.

1. **Splash biometric unlock enforces nothing** (confirmed) — the splash calls `authenticate` but discards the result ("access is already granted"), so an opted-in user reaches `/home` whether or not the biometric check passes. Wire real enforcement when the `phase3+` re-auth gate lands; until then treat it as a visual affordance, not access control.
2. **Password-reset email can't reach `/auth/reset`** (confirmed) — a recovery session is authenticated, and the guard sends authenticated users off `/auth/*` to `/home`, so the email-link flow doesn't complete end-to-end. Implement the documented `AuthChangeEvent.passwordRecovery` → `/auth/reset` routing in a later phase.
3. **local_auth 3.0.2 adaptation is compile-checked only** (confirmed) — the resolved API differs from the plan's pinned 2.x signature; the adapted `authenticate(...)` call and broad `catch` compile under `dart analyze` but have no runtime check. Confirm on a device via the deferred `flutter build`.
4. **Flutter gates not executed** (confirmed) — `flutter test` and `flutter build web` are deferred under the `flutter` deny, so no runtime assertion exists that screens render, the guard redirects live, or OTP paste/auto-advance works. Run both when the deny lifts; the widget-test matrix is already authored.
5. **Sign-out swallows errors silently** (confirmed) — Settings' `signOut()` is wrapped in a `catch (_)` that surfaces nothing, so a failed sign-out gives the user no feedback (though staying logged in is a safe default). Low priority; consider an inline message on failure.
6. **admin_web modified outside the Phase 3 window** (likely) — files under `apps/admin_web` changed at 02:58–03:06, just after the user_app work; attributable to the parallel admin track that owns `admin_web`, not Phase 3. Informational — confirm the parallel track, not this change, produced those edits.

</details>

<details>
<summary>Details</summary>

### The dev bypass is gone, and the guard proves it

A repo-wide search for `devBypass` finds no `devBypassProvider` declaration or reference and no `// TODO(phase3): remove dev bypass`; the only surviving matches are two test assertions that `find.text('Enter app (dev)')` resolves to `findsNothing` (confirmed). With the symbol gone, the redirect in `router.dart` computes `final loggedIn = auth == AuthState.authenticated;` with no `|| bypass` term (confirmed).

The guard matches the required topology (confirmed): `AuthState.unknown` holds on the splash to avoid a login flash, an unauthenticated user on a non-`/auth` path goes to `AppRoutes.loginPath`, and an authenticated user on splash or `/auth/*` goes to `AppRoutes.homePath`. Sign-out runs through Settings' `Supabase.instance.client.auth.signOut()`; the auth-state listener flips the controller to `unauthenticated`, the router's `refreshListenable` fires, and the redirect returns to login. `auth_guard_test.dart` exercises all three transitions — unauthenticated boot → `LoginScreen`, authenticated boot → `HomeScreen`, and `set(AuthState.unauthenticated)` → back to `LoginScreen`. One wrinkle: the sign-out handler wraps the call in `catch (_)` and surfaces nothing, so a failed sign-out is silent (confirmed) — safe-default behavior, but no user feedback.

### Six screens, one scaffold, correct Supabase calls

All six screens render on `AuthScaffold`, and each is wired to the method the plan specifies, all inside user-triggered async handlers so tests can pump without reaching the network (confirmed):

```
Login     -> signInWithPassword(email, password)
             signInWithOAuth(OAuthProvider.google)   [try/catch -> errOauthUnavailable]
Signup    -> signUp(email, password, data:{display_name})
OTP       -> verifyOTP(email, token, type: signup)
             resend(type: signup, email)
Forgot    -> resetPasswordForEmail(email, redirectTo: AuthConfig.passwordResetRedirectUrl)
Reset     -> updateUser(UserAttributes(password:))
Settings  -> signOut()
```

Every auth file imports `supabase_flutter` with `hide AuthState` so the app's own `AuthState` enum is not shadowed (confirmed). Signup validates per field (name non-empty, `AuthValidators.isValidEmail`, `AuthValidators.isStrongEnough` with `minPasswordLength = 8`) before calling `signUp`, then branches on the response: a session routes to `/home`, a user-without-session routes to `/auth/otp?email=…`, and the neither case shows the "check your email" magic-link fallback (confirmed). Forgot shows one neutral confirmation state regardless of whether the address exists, which avoids account enumeration (confirmed) — a good default to keep.

### OTP input: one field, six cells

`OtpInput` is backed by a single `TextEditingController` rendered as six monospace cells (`VeriqooType.mono`, IBM Plex Mono), restricted by `FilteringTextInputFormatter.digitsOnly` and a length cap (confirmed). The single-field design is the reason it is paste-aware and auto-advancing without per-cell focus juggling, and `onCompleted` fires at full length but deliberately does not submit — the screen owns verification (confirmed). The heading is the exact `AuthStrings.otpTitle = 'VERIFY YOUR IDENTITY'`, with a 60-second resend countdown (`Resend code in {n}s`) and a ghost "Change email" action (confirmed).

### AuthBackground ships motion, defers video

The video path is a seam, not a product: `AuthBackgroundMode.video` resolves to `_videoLayers`, which currently delegates to `_motionLayers` and is gated behind `static const bool kVideoBackdropAvailable = false` with a `// TODO(phase3+): swap in a muted, looping VideoPlayer with a static poster fallback` note (confirmed). No `VideoPlayer` is instantiated and no video asset ships — a scan for `.mp4/.mov/.webm` and `assets/video` turns up only build artifacts and an unrelated Python venv, nothing in `lib` or declared assets (confirmed). The shipping motion layers are each gated `enabled: !reduce` off `VeriqooMotion.reduceMotion(context)`, so reduced motion holds the static end state.

### Biometric setup and the non-enforcing splash unlock

The setup screen reads `biometricServiceProvider.isAvailable()` on init and renders three states — unavailable, already-enabled, and the enable prompt whose button runs `authenticate(...)` then `setEnabled(true)` on success (confirmed). `BiometricService` wraps `LocalAuthentication` (`isDeviceSupported()` AND non-empty `getAvailableBiometrics()`) plus `FlutterSecureStorage` for the opt-in flag, swallowing platform failures to a safe default per the plan's "never throw to the UI" rule (confirmed).

The splash integration deserves a close look (confirmed, non-blocking): after the session resolves, `if (await service.isEnabled())` the splash sets an unlocking flag and calls `service.authenticate(...)`, but the result is explicitly discarded — the inline comment reads "Result is intentionally not gated on: access is already granted." So the biometric "unlock" protects nothing in Phase 3; an opted-in user reaches `/home` whether or not the check succeeds. This is the plan's stated OPTIONAL / NON-BLOCKING design with a `phase3+` note that a stricter re-auth gate can build on the seam, so it is not a defect against the plan — but because it touches the app's access posture, it is worth stating plainly: the gate is cosmetic until a later phase wires enforcement.

### Password reset stops at the guard

`ResetPasswordScreen` is route-reachable at `/auth/reset` and `updateUser(password:)` works whenever a session exists (confirmed). The gap is the delivery path (confirmed, non-blocking): a real recovery email emits `AuthChangeEvent.passwordRecovery` and establishes a session, which makes the user authenticated — and the guard bounces authenticated users off `/auth/*` to `/home`. So the email-link → `/auth/reset` flow does not complete end-to-end; the screen is effectively reachable only by an unauthenticated user navigating directly. The code documents this with `// TODO(phase3+): on AuthChangeEvent.passwordRecovery, route to /auth/reset`, and the plan scopes full recovery routing out of Phase 3. Flagged so the deferred work stays visible, not as a blocking defect.

### local_auth 3.x adaptation vs the plan's pinned 2.x API

The plan pinned the `local_auth` 2.x signature (`authenticate({localizedReason, AuthenticationOptions options})`, `stickyAuth`, `PlatformException`), but `pubspec.lock` resolves 3.0.2, whose API moved options to direct named parameters, dropped `stickyAuth`, and throws `LocalAuthException` (confirmed). The coder adapted to `authenticate(localizedReason:, biometricOnly: true, persistAcrossBackgrounding: true)` with a broad `catch (_)` covering the changed exception type (confirmed). `dart analyze` proves this compiles, but the biometric path is exercised only by the deferred `flutter build` / device run, so its runtime behavior is unverified here (confirmed, non-blocking).

### Design-system discipline

Beyond what the high-level view notes, the specifics check out: `textTertiary` appears only on a decorative chevron icon in Settings and inside `auth_message.dart`'s doc comment, which deliberately uses `textPrimary` and records that `textTertiary` "would fail WCAG for this essential copy" (confirmed). Copy is centralized in `AuthStrings` as flat `static const` members referenced by every screen (confirmed).

### Write scope and the parallel admin_web track

The Phase 3 edits cluster by mtime between 02:37 and 02:57, entirely under `apps/user_app` (the full list is in the file map below). `packages/shared_core` is untouched — its newest file predates the window by hours and `lib/services/*` is older still (confirmed). The git tree is not a usable baseline — the committed state is an old single-app layout and the whole monorepo is untracked — so mtime is the right signal, as the task notes, and no commit was made (confirmed).

The one out-of-tree observation (likely): `apps/admin_web` has files modified at 02:58–03:06, just after the user_app work and around the verification note's timestamp. This points to the parallel admin track — its task doc is the file open in the editor, and the plan assigns `admin_web` to a parallel track — not to Phase 3, so it is not a scope violation. Called out only so the mtime overlap is on record.

### Test coverage: authored, compiled, not executed

The suite is one pump-test per screen (`login`, `signup`, `otp`, `forgot_password`, `reset_password`, `biometric_setup`) plus `auth_guard_test.dart` and an `auth_harness.dart` with a `FakeBiometricService`; the splash's new provider read is covered by a disabled fake override in `app_shell_test.dart` (confirmed). Tests interact with fields without tapping submit, so `Supabase.instance` is never contacted, and `auth_guard_test.dart` pins the dev-bypass-gone assertion against the real router.

Not tested (confirmed, non-blocking per the task): nothing is executed. `dart analyze` proves every test and screen compiles, but `flutter test` and `flutter build web` are deferred under the `flutter` deny, so there is no runtime assertion that any screen renders, that the guard redirects live, that OTP paste/auto-advance behaves, or that the 3.x biometric call works on a device. The matrix is authored and kept for when the deny lifts; this is the single real verification gap.

</details>

<details>
<summary>Files changed</summary>

Created (all under `apps/user_app/`):
- `lib/features/auth/auth_strings.dart` — centralized auth copy.
- `lib/features/auth/auth_validators.dart` — email regex + 8-char password check.
- `lib/features/auth/auth_config.dart` — password-reset redirect constant (seam).
- `lib/features/auth/biometric_service.dart` — injectable local_auth + secure-storage wrapper.
- `lib/features/auth/widgets/auth_background.dart` — motion backdrop + video seam.
- `lib/features/auth/widgets/auth_scaffold.dart` — shared hero + glass panel + entrance motion.
- `lib/features/auth/widgets/auth_message.dart` — shared inline notice line (WCAG-safe).
- `lib/features/auth/widgets/otp_input.dart` — single-field six-cell mono OTP input.
- `lib/features/auth/biometric_setup_screen.dart` — opt-in / unavailable / enabled states.
- `test/auth/auth_harness.dart` + 6 screen tests + `auth_guard_test.dart`.

Changed (all under `apps/user_app/`):
- `lib/features/auth/auth_controller.dart` — removed `devBypassProvider` + TODO.
- `lib/app/router.dart` — guard keys on `authenticated` only; OTP `?email=`; `/biometric-setup` route.
- `lib/app/routes.dart` — added `resetPasswordPath` (`/auth/reset`), `biometricSetupPath` (`/biometric-setup`).
- `lib/features/auth/login_screen.dart` — real sign-in + Google OAuth + forgot/create links; bypass removed.
- `lib/features/auth/signup_screen.dart` — validated signup → OTP / check-email.
- `lib/features/auth/otp_screen.dart` — verify + resend countdown + change-email.
- `lib/features/auth/forgot_password_screen.dart` — reset request + neutral confirmation.
- `lib/features/auth/reset_password_screen.dart` — `updateUser(password)` at `/auth/reset`.
- `lib/features/settings/settings_screen.dart` — Security section (biometric entry + sign-out).
- `lib/features/splash/splash_screen.dart` — optional non-blocking biometric unlock.
- `test/app_shell_test.dart` — disabled `FakeBiometricService` override.
- Native config (analyzer-excluded, exercised only by the deferred build): `android/.../AndroidManifest.xml`, `android/.../MainActivity.kt` (FragmentActivity), `ios/Runner/Info.plist` (NSFaceIDUsageDescription).

Full change set is the uncommitted working tree under `apps/user_app/` (verify by mtime, not git diff — the committed tree is an unrelated old layout).

</details>
