import 'package:flutter_riverpod/flutter_riverpod.dart';
// Supabase exports its own `AuthState`; we hide it to match the rest of the
// auth feature where our three-value guard enum is the only `AuthState`.
import 'package:supabase_flutter/supabase_flutter.dart' hide AuthState;

import 'package:flutter_application_1/features/auth/auth_controller.dart';
import 'package:flutter_application_1/features/home/home_user.dart';

/// Injectable account actions used by Profile and Settings.
///
/// Sign-out is best-effort and NEVER throws (mirroring `BiometricService`):
/// on success the `onAuthStateChange` listener flips the router guard to
/// unauthenticated and the redirect returns to `/auth/login` — no manual
/// navigation needed. Extracting it behind [authActionsProvider] keeps the
/// screens testable without touching `Supabase.instance`.
class AuthActions {
  const AuthActions([this._ref]);

  final Ref? _ref;

  Future<void> signOut() async {
    try {
      _ref?.read(demoUserProvider.notifier).signOut();
      _ref?.read(authControllerProvider.notifier).set(AuthState.unauthenticated);
      await Supabase.instance.client.auth.signOut();
    } catch (_) {
      // On failure the guard simply stays as-is; nothing to surface here.
    }
  }
}

/// The account-actions seam. Override with a fake in tests to observe taps.
final authActionsProvider = Provider<AuthActions>((ref) => AuthActions(ref));
