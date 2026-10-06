import 'package:flutter_riverpod/flutter_riverpod.dart';
// Supabase exports its own `AuthState` (event + session). We hide it so our
// three-value guard enum below is the only `AuthState` in scope; member access
// on the stream payload (`data.session`) still resolves via inference.
import 'package:supabase_flutter/supabase_flutter.dart' hide AuthState;

/// Authentication state used by the GoRouter guard.
///
/// * [unknown] — session not yet restored; the splash is shown with no login
///   flash while this is the value.
/// * [authenticated] — a Supabase session is present.
/// * [unauthenticated] — no session.
enum AuthState { unknown, authenticated, unauthenticated }

/// Exposes [AuthState] backed by `Supabase.instance.client.auth`.
///
/// Starts at [AuthState.unknown] and settles either when the first
/// `onAuthStateChange` event arrives or when the splash calls [resolve] after
/// its minimum display — whichever happens first moves the router off
/// `/splash`.
class AuthController extends Notifier<AuthState> {
  @override
  AuthState build() {
    final auth = Supabase.instance.client.auth;
    final sub = auth.onAuthStateChange.listen((data) {
      state = data.session != null
          ? AuthState.authenticated
          : AuthState.unauthenticated;
    });
    ref.onDispose(sub.cancel);
    return AuthState.unknown;
  }

  /// Settles the state from the restored session. Called by the splash after
  /// its minimum display window.
  void resolve() {
    final session = Supabase.instance.client.auth.currentSession;
    state = session != null
        ? AuthState.authenticated
        : AuthState.unauthenticated;
  }

  /// Directly sets the state. Used by tests and internal transitions.
  void set(AuthState value) => state = value;
}

/// The auth state / router-guard source.
final authControllerProvider =
    NotifierProvider<AuthController, AuthState>(AuthController.new);
