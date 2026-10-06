import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart' hide AuthState;

import 'package:flutter_application_1/features/home/home_user.dart';

/// An immutable view of the signed-in identity for the Profile header,
/// composed from the shared [currentUserProvider] (name/email) and the
/// verification flag. Kept small and pure so it is trivial to assert in tests.
@immutable
class ProfileIdentity {
  const ProfileIdentity({
    required this.displayName,
    required this.email,
    required this.verified,
  });

  /// Best display name (metadata → email local-part → email), or null.
  final String? displayName;

  /// Account email, or null when unknown.
  final String? email;

  /// Whether the account's email has been confirmed.
  final bool verified;

  /// The single-character avatar initial: first grapheme of the display name,
  /// else of the email, else 'V'. Always uppercased.
  String get initial {
    final source = (displayName?.trim().isNotEmpty ?? false)
        ? displayName!.trim()
        : (email?.trim().isNotEmpty ?? false)
            ? email!.trim()
            : 'V';
    return source.characters.first.toUpperCase();
  }
}

/// Whether the current account's email is confirmed. GUARDED: resolves false
/// when Supabase is uninitialized (hermetic tests) or there is no session.
/// Overridable in tests via `accountVerifiedProvider.overrideWithValue(...)`.
final accountVerifiedProvider = Provider<bool>((ref) {
  if (ref.watch(demoUserProvider) != null) {
    return true;
  }
  try {
    return Supabase.instance.client.auth.currentUser?.emailConfirmedAt != null;
  } catch (_) {
    return false;
  }
});

/// The composed [ProfileIdentity] for the Profile header. Reuses
/// [currentUserProvider]/[displayNameFor] (no second Supabase read for
/// name/email) and [accountVerifiedProvider] for the chip.
final profileIdentityProvider = Provider<ProfileIdentity>((ref) {
  final user = ref.watch(currentUserProvider);
  return ProfileIdentity(
    displayName: displayNameFor(user),
    email: user?.email,
    verified: ref.watch(accountVerifiedProvider),
  );
});
