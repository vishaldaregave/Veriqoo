import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:flutter_application_1/features/home/home_strings.dart';

/// A minimal, immutable view of the signed-in user for the Home greeting.
///
/// [name] is the metadata display name (null when absent); [email] is the raw
/// account email. The greeting's final display name (including the email
/// local-part fallback) is resolved by [displayNameFor] so it stays pure and
/// unit-testable.
@immutable
class HomeUser {
  const HomeUser({this.name, this.email});

  final String? name;
  final String? email;
}

/// In-memory demo user session (used for quick local testing/fake login).
class DemoUserNotifier extends Notifier<HomeUser?> {
  @override
  HomeUser? build() => null;

  void signIn({String name = 'Demo Inspector', String email = 'demo@veriqoo.com'}) {
    state = HomeUser(name: name, email: email);
  }

  void signOut() {
    state = null;
  }
}

final demoUserProvider =
    NotifierProvider<DemoUserNotifier, HomeUser?>(DemoUserNotifier.new);

/// The current user for the greeting, read lazily and GUARDED.
///
/// This is read synchronously during Home's build, so it must never throw: if
/// Supabase is uninitialized (e.g. hermetic widget tests) or there is no
/// session, it resolves to null and the greeting degrades gracefully.
final currentUserProvider = Provider<HomeUser?>((ref) {
  final demoUser = ref.watch(demoUserProvider);
  if (demoUser != null) {
    return demoUser;
  }
  try {
    final user = Supabase.instance.client.auth.currentUser;
    if (user == null) {
      return null;
    }
    final metadata = user.userMetadata;
    final metaName = _firstNonEmpty([
      metadata?['full_name'],
      metadata?['name'],
    ]);
    return HomeUser(name: metaName, email: user.email);
  } catch (_) {
    return null;
  }
});

/// Resolves the best display name: metadata name, else the email local-part,
/// else the raw email, else null. Pure — safe to unit test.
String? displayNameFor(HomeUser? user) {
  if (user == null) {
    return null;
  }
  final name = user.name;
  if (name != null && name.trim().isNotEmpty) {
    return name.trim();
  }
  final email = user.email?.trim();
  if (email == null || email.isEmpty) {
    return null;
  }
  if (email.contains('@')) {
    final local = email.split('@').first.trim();
    if (local.isNotEmpty) {
      return local;
    }
  }
  return email;
}

/// The time-of-day greeting prefix for [now]: morning (<12:00), afternoon
/// (<17:00), otherwise evening. Pure.
String greetingFor(DateTime now) {
  final hour = now.hour;
  if (hour < 12) {
    return HomeStrings.goodMorning;
  }
  if (hour < 17) {
    return HomeStrings.goodAfternoon;
  }
  return HomeStrings.goodEvening;
}

/// Composes the full greeting line, e.g. `GOOD MORNING, Ada`. Falls back to the
/// bare prefix (`GOOD MORNING`) when no name/email is available. Pure.
String greetingLine(HomeUser? user, DateTime now) {
  final prefix = greetingFor(now);
  final name = displayNameFor(user);
  if (name == null) {
    return prefix;
  }
  return '$prefix, $name';
}

String? _firstNonEmpty(List<Object?> values) {
  for (final value in values) {
    if (value is String && value.trim().isNotEmpty) {
      return value.trim();
    }
  }
  return null;
}
