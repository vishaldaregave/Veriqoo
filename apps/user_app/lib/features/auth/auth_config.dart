/// Static auth configuration seams that a later phase finalizes.
abstract final class AuthConfig {
  const AuthConfig._();

  /// Deep link Supabase appends the recovery token to when a user requests a
  /// password reset.
  ///
  /// For Phase 3 this is a documented placeholder. To make recovery links fully
  /// functional a later phase must:
  /// 1. register this URL under Supabase > Auth > URL Configuration;
  /// 2. wire the matching native deep-link (Android intent filter / iOS
  ///    associated domain or custom scheme); and
  /// 3. route the resulting `AuthChangeEvent.passwordRecovery` to `/auth/reset`.
  // TODO(phase3+): finalize the scheme and complete native deep-link wiring.
  static const String passwordResetRedirectUrl = 'io.veriqoo.app://auth/reset';
}
