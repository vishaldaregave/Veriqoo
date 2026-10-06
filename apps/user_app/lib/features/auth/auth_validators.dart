/// Shared, dependency-free validation helpers for the auth forms.
///
/// Kept deliberately simple: the server (Supabase) is the source of truth for
/// email deliverability and password policy. These checks only catch obvious
/// client-side mistakes before a network round-trip.
abstract final class AuthValidators {
  const AuthValidators._();

  /// Minimum password length enforced on the client before submit.
  static const int minPasswordLength = 8;

  // A pragmatic "looks like an email" check: non-space run, '@', non-space run,
  // '.', non-space run. Not RFC-complete by design.
  static final RegExp _emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

  /// Whether [value] looks like a valid email address.
  static bool isValidEmail(String value) =>
      _emailPattern.hasMatch(value.trim());

  /// Whether [value] meets the minimum client-side password length.
  static bool isStrongEnough(String value) =>
      value.length >= minPasswordLength;
}
